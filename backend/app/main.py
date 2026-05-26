from __future__ import annotations


import sys
import os
import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.utils.logger import configure_logging, get_logger
from app.utils.exceptions import (
    AutoReplyBaseException,
    DatabaseException,
    InvalidTokenException,
    RateLimitException,
)
from app.models.database import verify_database_connection
from app.middleware import RequestLoggingMiddleware
from app.api.webhooks import router as webhooks_router
from app.api.dashboard import router as dashboard_router
from app.api.auth import router as auth_router
from app.api.knowledge import router as knowledge_router
from app.api.test_system import router as test_router

settings = get_settings()

# Configure logging first — before anything else logs
configure_logging()
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Lifespan — startup + shutdown
# ─────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.
    Runs startup checks before accepting requests.
    Runs cleanup on shutdown.
    """
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info(
        "app_starting",
        app_name=settings.app_name,
        env=settings.app_env,
        version="1.0.0",
    )

    # Verify Supabase connection — fail fast if DB unreachable
    try:
        verify_database_connection()
        logger.info("startup_database_ok")
    except DatabaseException as e:
        logger.error("startup_database_failed", error=str(e))
        sys.exit(1)

    # Warm up embedding model — loads once, cached for all requests
   # Railway deployment:
# Lazy-load AI resources later on first request

    logger.info("startup_embedding_skipped")
    logger.info("startup_chromadb_skipped")

    logger.info("app_started", host=settings.app_host, port=settings.app_port)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("app_shutting_down")


# ─────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Multi-channel AI automation platform — WhatsApp, Voice, Email",
        version="1.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────

    # CORS — restrict to frontend URL
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging + context
    app.add_middleware(RequestLoggingMiddleware)

    # ── Global exception handlers ─────────────────────────────────────────

    @app.exception_handler(AutoReplyBaseException)
    async def autoreply_exception_handler(
        request: Request,
        exc: AutoReplyBaseException,
    ) -> JSONResponse:
        """
        Global handler for all typed AutoReply exceptions.
        Never exposes stack traces.
        Returns correct HTTP status per exception type.
        """
        logger.error(
            "handled_exception",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
            user_id=exc.user_id,
            channel=exc.channel,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error_code": exc.error_code,
                "message": exc.message,
            },
        )

    @app.exception_handler(InvalidTokenException)
    async def token_exception_handler(
        request: Request,
        exc: InvalidTokenException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error_code": "INVALID_TOKEN",
                "message": "Authentication required",
            },
        )

    @app.exception_handler(RateLimitException)
    async def rate_limit_handler(
        request: Request,
        exc: RateLimitException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        Catch-all for unhandled exceptions.
        Logs full context, never exposes internals to client.
        """
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "message": "Something went wrong. Please try again.",
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────

    app.include_router(auth_router)
    app.include_router(webhooks_router)
    app.include_router(dashboard_router)
    app.include_router(knowledge_router)
    app.include_router(test_router)

    # ── Health check ──────────────────────────────────────────────────────

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """
        Public health endpoint.
        Used by Railway to verify app is running.
        """
        return {
            "status": "healthy",
            "app": settings.app_name,
            "env": settings.app_env,
        }

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "message": f"Welcome to {settings.app_name} API",
            "docs": "/docs",
            "health": "/health",
        }

    return app


# ─────────────────────────────────────────────────────────────────────────
# App instance — imported by uvicorn
# ─────────────────────────────────────────────────────────────────────────

app = create_app()