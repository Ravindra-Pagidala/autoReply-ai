from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from collections.abc import Callable
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.config.settings import get_settings

settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────
# Sensitive fields — values scrubbed before logging
# ─────────────────────────────────────────────────────────────────────────

_SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "api_key",
        "groq_api_key",
        "supabase_service_key",
        "supabase_anon_key",
        "twilio_auth_token",
        "sendgrid_api_key",
        "secret_key",
        "password",
        "token",
        "authorization",
        "access_token",
        "refresh_token",
        "service_key",
        "auth_token",
    }
)

_MAX_MESSAGE_LENGTH = 200

# ─────────────────────────────────────────────────────────────────────────
# Log level enforcement guide
# DEBUG   → flow tracing, db queries, RAG retrieval steps
# INFO    → state changes: webhook received, lead saved, reply sent
# WARNING → retries, degraded mode, RAG miss, KB empty
# ERROR   → failures, exceptions, escalation triggers
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
# Custom processors
# ─────────────────────────────────────────────────────────────────────────

def scrub_sensitive_fields(
    logger: WrappedLogger,
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """Scrubs sensitive fields. API keys NEVER appear in logs."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_FIELDS:
            event_dict[key] = "***REDACTED***"
    return event_dict


def truncate_long_values(
    logger: WrappedLogger,
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """Truncates long strings to avoid log flooding."""
    truncatable = {
        "message", "prompt", "response",
        "content", "reply", "body", "text",
        "rag_context", "speech_result",
    }
    for key in truncatable:
        if key in event_dict and isinstance(event_dict[key], str):
            value = event_dict[key]
            if len(value) > _MAX_MESSAGE_LENGTH:
                event_dict[key] = (
                    value[:_MAX_MESSAGE_LENGTH] + "...[truncated]"
                )
    return event_dict


def add_app_context(
    logger: WrappedLogger,
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """Adds app-level context to every log entry."""
    event_dict["app"] = settings.app_name
    event_dict["env"] = settings.app_env
    return event_dict


# ─────────────────────────────────────────────────────────────────────────
# Configure structlog
# ─────────────────────────────────────────────────────────────────────────

def configure_logging() -> None:
    """
    Configures structlog. Call once at startup in main.py.

    Log level enforcement:
    DEBUG   → flow tracing (db queries, RAG steps, agent nodes)
    INFO    → meaningful state changes (webhook received, lead saved)
    WARNING → retries, degraded mode, RAG miss, KB empty
    ERROR   → failures, unhandled exceptions, escalations

    Development → colored, human-readable.
    Production  → JSON for log aggregators (Datadog, Loki etc.)
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_app_context,
        scrub_sensitive_fields,
        truncate_long_values,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level)

    # Silence noisy third-party loggers
    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "chromadb",
        "sentence_transformers",
        "twilio",
        "sendgrid",
        "hpack",
        "h2",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


# ─────────────────────────────────────────────────────────────────────────
# Logger factory
# ─────────────────────────────────────────────────────────────────────────

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Returns a bound logger for a module.

    Usage:
        from app.utils.logger import get_logger
        logger = get_logger(__name__)

    Log level guide:
        logger.debug()   → flow: "db_query_started", "rag_retrieving"
        logger.info()    → state: "webhook_received", "lead_saved"
        logger.warning() → retries: "llm_retry_attempt", "rag_miss"
        logger.error()   → failures: "llm_failed", "db_insert_failed"
    """
    return structlog.get_logger(name)


# ─────────────────────────────────────────────────────────────────────────
# Context binding helpers
# ─────────────────────────────────────────────────────────────────────────

def bind_request_context(
    request_id: str | None = None,
    user_id: str | None = None,
    channel: str | None = None,
) -> str:
    """
    Binds context to ALL subsequent logs in current async context.
    Auto-generates request_id if not provided.
    Returns the request_id for reference.
    Call at start of every webhook handler.
    """
    rid = request_id or str(uuid.uuid4())[:8]
    ctx: dict[str, Any] = {"request_id": rid}
    if user_id:
        ctx["user_id"] = user_id
    if channel:
        ctx["channel"] = channel
    structlog.contextvars.bind_contextvars(**ctx)
    return rid


def clear_request_context() -> None:
    """Clears bound context at end of request."""
    structlog.contextvars.clear_contextvars()


# ─────────────────────────────────────────────────────────────────────────
# Latency decorator — handles both sync and async
# ─────────────────────────────────────────────────────────────────────────

def log_latency(operation: str) -> Callable[..., Any]:
    """
    Decorator that logs execution time of sync or async functions.
    Use on LLM calls, Twilio calls, Supabase calls, embeddings.

    Log levels:
    - DEBUG: operation started
    - INFO:  operation completed with latency_ms
    - ERROR: operation failed with latency_ms and error

    Usage:
        @log_latency("groq_llm_call")
        async def call_groq(...): ...

        @log_latency("embed_document")
        def embed_sync(...): ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _logger = get_logger(__name__)
                start = time.monotonic()
                try:
                    _logger.debug(
                        f"{operation}_started",
                        operation=operation,
                    )
                    result = await func(*args, **kwargs)
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    _logger.info(
                        f"{operation}_completed",
                        operation=operation,
                        latency_ms=elapsed_ms,
                    )
                    return result
                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    _logger.error(
                        f"{operation}_failed",
                        operation=operation,
                        latency_ms=elapsed_ms,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    raise
            return async_wrapper
        else:
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                _logger = get_logger(__name__)
                start = time.monotonic()
                try:
                    _logger.debug(
                        f"{operation}_started",
                        operation=operation,
                    )
                    result = func(*args, **kwargs)
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    _logger.info(
                        f"{operation}_completed",
                        operation=operation,
                        latency_ms=elapsed_ms,
                    )
                    return result
                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    _logger.error(
                        f"{operation}_failed",
                        operation=operation,
                        latency_ms=elapsed_ms,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    raise
            return sync_wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────
# Retry logging helpers
# Called by retry.py to log retry attempts at WARNING level
# ─────────────────────────────────────────────────────────────────────────

def log_retry_attempt(
    operation: str,
    attempt: int,
    max_attempts: int,
    error: str,
    wait_seconds: float,
) -> None:
    """
    Logs a retry attempt at WARNING level.
    Called from tenacity before_sleep callbacks.

    WARNING level — retries are degraded state, not normal flow.
    """
    logger = get_logger(__name__)
    logger.warning(
        "retry_attempt",
        operation=operation,
        attempt=attempt,
        max_attempts=max_attempts,
        error=error,
        wait_seconds=wait_seconds,
    )


def log_circuit_open(operation: str, failure_count: int) -> None:
    """
    Logs when circuit breaker opens.
    ERROR level — circuit open means service is down.
    """
    logger = get_logger(__name__)
    logger.error(
        "circuit_breaker_opened",
        operation=operation,
        failure_count=failure_count,
    )


def log_circuit_half_open(operation: str) -> None:
    """
    Logs when circuit breaker moves to half-open.
    WARNING level — attempting recovery.
    """
    logger = get_logger(__name__)
    logger.warning(
        "circuit_breaker_half_open",
        operation=operation,
    )