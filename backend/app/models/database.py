from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from supabase import Client, create_client

from app.config.settings import get_settings
from app.utils.circuit_breaker import CircuitOpenException, supabase_circuit
from app.utils.exceptions import DatabaseException, RecordNotFoundException
from app.utils.logger import get_logger, log_retry_attempt

settings = get_settings()
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Client Factory
# ─────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_anon_client() -> Client:
    """
    Anon Supabase client — respects RLS.
    Use for: dashboard queries with user JWT.
    NEVER use in webhook handlers.
    """
    try:
        client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key,
        )
        logger.info("supabase_anon_client_created")
        return client
    except Exception as e:
        logger.error(
            "supabase_anon_client_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise DatabaseException(
            f"Failed to create Supabase anon client: {e}",
            operation="create_anon_client",
        ) from e


@lru_cache(maxsize=1)
def get_admin_client() -> Client:
    """
    Admin Supabase client — bypasses RLS.
    Use ONLY in: webhook handlers, background tasks, test system.
    NEVER expose to user-facing endpoints.
    """
    try:
        client = create_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )
        logger.info("supabase_admin_client_created")
        return client
    except Exception as e:
        logger.error(
            "supabase_admin_client_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise DatabaseException(
            f"Failed to create Supabase admin client: {e}",
            operation="create_admin_client",
        ) from e


# ─────────────────────────────────────────────────────────────────────────
# Startup Health Check
# ─────────────────────────────────────────────────────────────────────────

def verify_database_connection() -> None:
    """
    Tests Supabase connectivity on startup.
    Sync — Supabase Python client is synchronous.
    Called from main.py lifespan before accepting requests.
    Fails fast if Supabase unreachable.
    """
    logger.info("database_connection_check_started")
    try:
        admin = get_admin_client()
        admin.table("business_profiles").select("id").limit(1).execute()
        logger.info("database_connection_check_passed")
    except Exception as e:
        logger.error(
            "database_connection_check_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise DatabaseException(
            f"Supabase connection failed: {e}. "
            "Check SUPABASE_URL and SUPABASE_SERVICE_KEY.",
            operation="verify_connection",
        ) from e


# ─────────────────────────────────────────────────────────────────────────
# Authenticated Client
# ─────────────────────────────────────────────────────────────────────────

def get_authenticated_client(jwt_token: str) -> Client:
    """
    Anon client with user JWT injected.
    RLS scopes all queries to this user's data.
    Used in dashboard API endpoints.
    """
    try:
        client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key,
        )
        client.postgrest.auth(jwt_token)
        return client
    except Exception as e:
        logger.error(
            "authenticated_client_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise DatabaseException(
            f"Failed to create authenticated client: {e}",
            operation="get_authenticated_client",
        ) from e


# ─────────────────────────────────────────────────────────────────────────
# Filter builder
# ─────────────────────────────────────────────────────────────────────────

class FilterOperator:
    EQ = "eq"
    NEQ = "neq"
    GTE = "gte"
    LTE = "lte"
    LIKE = "like"
    IS = "is"


class Filter:
    """
    Typed filter for list_records and count.

    Usage:
        Filter("status", FilterOperator.EQ, "open")
        Filter("created_at", FilterOperator.GTE, "2026-05-26")
    """
    def __init__(
        self,
        column: str,
        operator: str,
        value: Any,
    ) -> None:
        self.column = column
        self.operator = operator
        self.value = value


# ─────────────────────────────────────────────────────────────────────────
# Retry configuration
# Circuit breaker sits OUTSIDE retry:
#   circuit_breaker → retry → actual Supabase call
# Retry handles transient failures (network blip)
# Circuit breaker handles sustained outages (Supabase down)
# ─────────────────────────────────────────────────────────────────────────

def _build_db_retry(operation: str) -> Any:
    """
    Tenacity retry decorator for DB operations.
    3 attempts, exponential backoff 1s → 10s.
    WARNING logged on each retry attempt.
    """
    def before_sleep(retry_state: Any) -> None:
        log_retry_attempt(
            operation=operation,
            attempt=retry_state.attempt_number,
            max_attempts=3,
            error=str(retry_state.outcome.exception()),
            wait_seconds=getattr(
                retry_state.next_action, "sleep", 0
            ),
        )

    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep,
        reraise=True,
    )


def _apply_filters(query: Any, filters: list[Filter]) -> Any:
    """Applies typed filters to a Supabase query."""
    for f in filters:
        if f.operator == FilterOperator.EQ:
            query = query.eq(f.column, f.value)
        elif f.operator == FilterOperator.NEQ:
            query = query.neq(f.column, f.value)
        elif f.operator == FilterOperator.GTE:
            query = query.gte(f.column, f.value)
        elif f.operator == FilterOperator.LTE:
            query = query.lte(f.column, f.value)
        elif f.operator == FilterOperator.LIKE:
            query = query.like(f.column, f.value)
        elif f.operator == FilterOperator.IS:
            query = query.is_(f.column, f.value)
    return query


# ─────────────────────────────────────────────────────────────────────────
# Database Service
# ─────────────────────────────────────────────────────────────────────────

class DatabaseService:
    """
    Generic database service.

    Every call goes through:
    1. Circuit breaker — fail fast if Supabase is down
    2. Retry — 3 attempts with exponential backoff
    3. asyncio.to_thread — Supabase is sync, don't block event loop
    4. Typed exceptions — never bare except
    5. Structured logging at correct levels

    Log levels:
      DEBUG → operation started, completed (flow)
      INFO  → state changes (record created, updated)
      WARNING → retry attempts (degraded)
      ERROR → failures after retries
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    async def _execute(
        self,
        operation: str,
        func: Any,
    ) -> Any:
        """
        Executes a sync Supabase call through:
        circuit_breaker → retry → asyncio.to_thread

        Args:
            operation: Name for logging and retry config
            func: Sync callable that performs the DB operation

        Returns:
            Result of the callable
        """
        @_build_db_retry(operation)
        def _with_retry() -> Any:
            return func()

        try:
            return await supabase_circuit.call(_with_retry)
        except CircuitOpenException as e:
            logger.error(
                "supabase_circuit_open",
                operation=operation,
                retry_after=e.retry_after_seconds,
            )
            raise DatabaseException(
                f"Supabase circuit open — {e}",
                operation=operation,
            ) from e
        except RetryError as e:
            logger.error(
                f"{operation}_failed_after_retries",
                operation=operation,
                error=str(e),
            )
            raise DatabaseException(
                f"{operation} failed after 3 retries: {e}",
                operation=operation,
            ) from e

    async def insert(
        self,
        table: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Insert a record and return created row."""
        logger.debug("db_insert_started", table=table)

        def _do() -> dict[str, Any]:
            result = (
                self._client.table(table)
                .insert(data)
                .execute()
            )
            if not result.data:
                raise DatabaseException(
                    f"Insert into {table} returned no data",
                    operation="insert",
                )
            return result.data[0]

        try:
            record = await self._execute(f"db_insert_{table}", _do)
            logger.info(
                "db_insert_completed",
                table=table,
                record_id=record.get("id"),
            )
            return record
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                "db_insert_failed",
                table=table,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to insert into {table}: {e}",
                operation="insert",
                context={"table": table},
            ) from e

    async def upsert(
        self,
        table: str,
        data: dict[str, Any],
        on_conflict: str = "user_id",
    ) -> dict[str, Any]:
        """
        Insert or update on conflict.
        Used for business_profiles — one profile per user.
        """
        logger.debug("db_upsert_started", table=table)

        def _do() -> dict[str, Any]:
            result = (
                self._client.table(table)
                .upsert(data, on_conflict=on_conflict)
                .execute()
            )
            if not result.data:
                raise DatabaseException(
                    f"Upsert into {table} returned no data",
                    operation="upsert",
                )
            return result.data[0]

        try:
            record = await self._execute(f"db_upsert_{table}", _do)
            logger.info(
                "db_upsert_completed",
                table=table,
                record_id=record.get("id"),
            )
            return record
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                "db_upsert_failed",
                table=table,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to upsert into {table}: {e}",
                operation="upsert",
                context={"table": table},
            ) from e

    async def bulk_insert(
        self,
        table: str,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Batch insert multiple records in one DB call.
        Used for test_results — 25 rows in 1 call.
        """
        if not records:
            return []

        logger.debug(
            "db_bulk_insert_started",
            table=table,
            count=len(records),
        )

        def _do() -> list[dict[str, Any]]:
            result = (
                self._client.table(table)
                .insert(records)
                .execute()
            )
            return result.data or []

        try:
            rows = await self._execute(f"db_bulk_insert_{table}", _do)
            logger.info(
                "db_bulk_insert_completed",
                table=table,
                count=len(rows),
            )
            return rows
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                "db_bulk_insert_failed",
                table=table,
                count=len(records),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to bulk insert into {table}: {e}",
                operation="bulk_insert",
                context={"table": table, "count": len(records)},
            ) from e

    async def get_by_id(
        self,
        table: str,
        record_id: str,
    ) -> dict[str, Any]:
        """Fetch single record by id. Raises RecordNotFoundException if missing."""
        logger.debug(
            "db_get_by_id_started",
            table=table,
            record_id=record_id,
        )

        def _do() -> Any:
            result = (
                self._client.table(table)
                .select("*")
                .eq("id", record_id)
                .single()
                .execute()
            )
            return result.data

        try:
            data = await self._execute(f"db_get_{table}", _do)
            if not data:
                raise RecordNotFoundException(
                    f"Record {record_id} not found in {table}",
                    operation="get_by_id",
                    context={"table": table, "id": record_id},
                )
            logger.debug(
                "db_get_by_id_completed",
                table=table,
                record_id=record_id,
            )
            return data
        except (RecordNotFoundException, DatabaseException):
            raise
        except Exception as e:
            logger.error(
                "db_get_by_id_failed",
                table=table,
                record_id=record_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to get record from {table}: {e}",
                operation="get_by_id",
                context={"table": table, "id": record_id},
            ) from e

    async def get_by_field(
        self,
        table: str,
        field: str,
        value: Any,
    ) -> dict[str, Any] | None:
        """
        Fetch single record by any field.
        Returns None if not found — does NOT raise.
        Used for idempotency checks and profile lookups.
        """
        def _do() -> list[dict[str, Any]]:
            result = (
                self._client.table(table)
                .select("*")
                .eq(field, value)
                .limit(1)
                .execute()
            )
            return result.data or []

        try:
            rows = await self._execute(f"db_get_by_field_{table}", _do)
            return rows[0] if rows else None
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                "db_get_by_field_failed",
                table=table,
                field=field,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to get from {table} by {field}: {e}",
                operation="get_by_field",
                context={"table": table, "field": field},
            ) from e

    async def update(
        self,
        table: str,
        record_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a record by id and return updated row."""
        logger.debug(
            "db_update_started",
            table=table,
            record_id=record_id,
        )

        def _do() -> dict[str, Any]:
            result = (
                self._client.table(table)
                .update(data)
                .eq("id", record_id)
                .execute()
            )
            if not result.data:
                raise RecordNotFoundException(
                    f"Record {record_id} not found in {table}",
                    operation="update",
                    context={"table": table, "id": record_id},
                )
            return result.data[0]

        try:
            record = await self._execute(f"db_update_{table}", _do)
            logger.info(
                "db_update_completed",
                table=table,
                record_id=record_id,
            )
            return record
        except (DatabaseException, RecordNotFoundException):
            raise
        except Exception as e:
            logger.error(
                "db_update_failed",
                table=table,
                record_id=record_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to update {table}: {e}",
                operation="update",
                context={"table": table, "id": record_id},
            ) from e

    async def list_records(
        self,
        table: str,
        *,
        filters: list[Filter] | None = None,
        order_by: str = "created_at",
        ascending: bool = False,
        page: int = 1,
        page_size: int | None = None,
        select: str = "*",
    ) -> list[dict[str, Any]]:
        """
        Paginated list with typed filters.
        Never unbounded — always paginated.
        """
        if page_size is None:
            page_size = settings.default_page_size
        page_size = min(page_size, settings.max_page_size)
        offset = (page - 1) * page_size

        logger.debug(
            "db_list_started",
            table=table,
            page=page,
            page_size=page_size,
        )

        def _do() -> list[dict[str, Any]]:
            query = (
                self._client.table(table)
                .select(select)
                .order(order_by, desc=not ascending)
                .range(offset, offset + page_size - 1)
            )
            if filters:
                query = _apply_filters(query, filters)
            result = query.execute()
            return result.data or []

        try:
            rows = await self._execute(f"db_list_{table}", _do)
            logger.debug(
                "db_list_completed",
                table=table,
                count=len(rows),
            )
            return rows
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                "db_list_failed",
                table=table,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to list from {table}: {e}",
                operation="list_records",
                context={"table": table},
            ) from e

    async def delete(
        self,
        table: str,
        record_id: str,
    ) -> None:
        """Delete a record by id."""
        logger.debug(
            "db_delete_started",
            table=table,
            record_id=record_id,
        )

        def _do() -> None:
            self._client.table(table).delete().eq(
                "id", record_id
            ).execute()

        try:
            await self._execute(f"db_delete_{table}", _do)
            logger.info(
                "db_delete_completed",
                table=table,
                record_id=record_id,
            )
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                "db_delete_failed",
                table=table,
                record_id=record_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to delete from {table}: {e}",
                operation="delete",
                context={"table": table, "id": record_id},
            ) from e

    async def count(
        self,
        table: str,
        filters: list[Filter] | None = None,
    ) -> int:
        """Count records matching filters. Used for analytics."""
        def _do() -> int:
            query = self._client.table(table).select(
                "*", count="exact"
            )
            if filters:
                query = _apply_filters(query, filters)
            result = query.execute()
            return result.count or 0

        try:
            cnt = await self._execute(f"db_count_{table}", _do)
            logger.debug(
                "db_count_completed",
                table=table,
                count=cnt,
            )
            return cnt
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                "db_count_failed",
                table=table,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"Failed to count {table}: {e}",
                operation="count",
                context={"table": table},
            ) from e

    async def raw_query(
        self,
        rpc_function: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute Supabase RPC stored procedure.
        Used for complex analytics: GROUP BY, date truncation.
        """
        logger.debug(
            "db_raw_query_started",
            rpc_function=rpc_function,
        )

        def _do() -> list[dict[str, Any]]:
            result = self._client.rpc(
                rpc_function,
                params or {},
            ).execute()
            return result.data or []

        try:
            rows = await self._execute(
                f"db_rpc_{rpc_function}", _do
            )
            logger.info(
                "db_raw_query_completed",
                rpc_function=rpc_function,
                count=len(rows),
            )
            return rows
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                "db_raw_query_failed",
                rpc_function=rpc_function,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseException(
                f"RPC {rpc_function} failed: {e}",
                operation="raw_query",
                context={"rpc_function": rpc_function},
            ) from e

    async def atomic_save(
        self,
        operations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Executes multiple operations sequentially.
        As close to atomic as Supabase REST allows.
        Logs partial failures with full context.

        Used for: conversation + message + lead saves.

        operations format:
        [
            {"op": "insert", "table": "conversations", "data": {...}},
            {"op": "insert", "table": "messages", "data": {...}},
            {"op": "insert", "table": "leads", "data": {...}},
        ]
        """
        results: list[dict[str, Any]] = []
        completed: list[str] = []

        logger.debug(
            "atomic_save_started",
            operation_count=len(operations),
        )

        for op in operations:
            operation = op.get("op", "insert")
            table = op["table"]
            data = op["data"]

            try:
                if operation == "insert":
                    record = await self.insert(table, data)
                elif operation == "upsert":
                    record = await self.upsert(
                        table,
                        data,
                        on_conflict=op.get("on_conflict", "user_id"),
                    )
                elif operation == "update":
                    record = await self.update(
                        table,
                        op["record_id"],
                        data,
                    )
                else:
                    raise DatabaseException(
                        f"Unknown operation: {operation}",
                        operation="atomic_save",
                    )

                results.append(record)
                completed.append(table)

            except Exception as e:
                logger.error(
                    "atomic_save_partial_failure",
                    failed_table=table,
                    completed_tables=completed,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise DatabaseException(
                    f"Atomic save failed at {table} "
                    f"after completing {completed}: {e}",
                    operation="atomic_save",
                    context={
                        "failed_table": table,
                        "completed": completed,
                    },
                ) from e

        logger.info(
            "atomic_save_completed",
            tables=[op["table"] for op in operations],
        )
        return results


# ─────────────────────────────────────────────────────────────────────────
# Convenience factories
# ─────────────────────────────────────────────────────────────────────────

def get_admin_db() -> DatabaseService:
    """
    DatabaseService with admin client.
    Bypasses RLS.
    Use in: webhooks, background tasks, test system.
    """
    return DatabaseService(get_admin_client())


def get_user_db(jwt_token: str) -> DatabaseService:
    """
    DatabaseService with user-scoped client.
    RLS enforced — user sees only their own data.
    Use in: dashboard endpoints, auth endpoints.
    """
    return DatabaseService(get_authenticated_client(jwt_token))