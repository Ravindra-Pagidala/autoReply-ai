from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logger import get_logger, bind_request_context, clear_request_context

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Assigns request_id to every request
    2. Binds request_id to structlog context
    3. Logs request start + completion with latency
    4. Clears log context after response
    5. Never crashes — always calls next()

    Log levels:
    DEBUG → request started
    INFO  → request completed
    WARNING → 4xx responses
    ERROR → 5xx responses
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.monotonic()

        # Bind to structlog context — appears in all logs for this request
        bind_request_context(request_id=request_id)

        logger.debug(
            "request_started",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
        )

        try:
            response = await call_next(request)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Log at appropriate level based on status
            if response.status_code >= 500:
                logger.error(
                    "request_completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    latency_ms=elapsed_ms,
                    request_id=request_id,
                )
            elif response.status_code >= 400:
                logger.warning(
                    "request_completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    latency_ms=elapsed_ms,
                    request_id=request_id,
                )
            else:
                logger.info(
                    "request_completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    latency_ms=elapsed_ms,
                    request_id=request_id,
                )

            # Inject request_id into response header for tracing
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "request_unhandled_exception",
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=elapsed_ms,
                request_id=request_id,
            )
            raise
        finally:
            # Always clear context — prevents context leaking between requests
            clear_request_context()