from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

from app.utils.logger import (
    get_logger,
    log_circuit_half_open,
    log_circuit_open,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Circuit States
# ─────────────────────────────────────────────────────────────────────────

class CircuitState(str, Enum):
    CLOSED = "closed"        # Normal — requests flow through
    OPEN = "open"            # Tripped — requests rejected immediately
    HALF_OPEN = "half_open"  # Recovery — one probe request allowed


# ─────────────────────────────────────────────────────────────────────────
# Circuit Breaker Exception
# ─────────────────────────────────────────────────────────────────────────

class CircuitOpenException(Exception):
    """
    Raised when circuit breaker is OPEN.
    Caller must handle this and return degraded response
    instead of waiting for a timeout.
    """
    def __init__(self, service: str, retry_after_seconds: float) -> None:
        self.service = service
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Circuit OPEN for {service}. "
            f"Retry after {retry_after_seconds:.0f}s."
        )


# ─────────────────────────────────────────────────────────────────────────
# Circuit Breaker
# ─────────────────────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    States:
      CLOSED     → requests flow through normally
      OPEN       → requests rejected immediately (fail fast)
      HALF_OPEN  → one probe request allowed to test recovery

    Transitions:
      CLOSED  → OPEN      after failure_threshold consecutive failures
      OPEN    → HALF_OPEN after recovery_timeout seconds
      HALF_OPEN → CLOSED  if probe request succeeds
      HALF_OPEN → OPEN    if probe request fails

    Usage:
        cb = CircuitBreaker("groq_llm")

        @cb.protect
        async def call_groq():
            ...

        # Or manual:
        async with cb:
            result = await call_groq()
    """

    def __init__(
        self,
        service: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> None:
        """
        Args:
            service: Name of the external service (for logging)
            failure_threshold: Consecutive failures before opening
            recovery_timeout: Seconds to wait before half-opening
            success_threshold: Successes in half-open before closing
        """
        self.service = service
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self._last_failure_time is None:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    async def _transition_to_open(self) -> None:
        """Circuit trips open. Fail fast from now on."""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.monotonic()
        log_circuit_open(self.service, self._failure_count)

    async def _transition_to_half_open(self) -> None:
        """Recovery attempt — allow one probe request."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        log_circuit_half_open(self.service)

    async def _transition_to_closed(self) -> None:
        """Service recovered — reset everything."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info(
            "circuit_breaker_closed",
            service=self.service,
        )

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    await self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Probe failed — back to open
                await self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    await self._transition_to_open()

    async def _check_state(self) -> None:
        """
        Check circuit state before allowing request.
        Raises CircuitOpenException if circuit is open.
        Transitions to half-open if recovery timeout elapsed.
        """
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._transition_to_half_open()
                else:
                    retry_after = (
                        self.recovery_timeout
                        - (time.monotonic() - (self._last_failure_time or 0))
                    )
                    raise CircuitOpenException(
                        self.service,
                        max(0, retry_after),
                    )

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Executes a callable through the circuit breaker.

        Handles both sync and async callables.
        Records success/failure and manages state transitions.

        Args:
            func: Callable to execute (sync or async)
            *args, **kwargs: Arguments to pass to func

        Raises:
            CircuitOpenException: If circuit is open
            Exception: Re-raises original exception on failure
        """
        await self._check_state()

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)

            await self._record_success()
            return result

        except CircuitOpenException:
            raise
        except Exception as e:
            await self._record_failure()
            logger.warning(
                "circuit_breaker_failure_recorded",
                service=self.service,
                failure_count=self._failure_count,
                threshold=self.failure_threshold,
                error=str(e),
                error_type=type(e).__name__,
                state=self._state,
            )
            raise

    def protect(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """
        Decorator that wraps a function with circuit breaker protection.

        Usage:
            cb = CircuitBreaker("groq_llm")

            @cb.protect
            async def call_groq(prompt: str) -> str:
                ...
        """
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await self.call(func, *args, **kwargs)
            return async_wrapper
        else:
            async def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await self.call(func, *args, **kwargs)
            return sync_wrapper


# ─────────────────────────────────────────────────────────────────────────
# Circuit Registry — one circuit per external service
# Singleton per service name — import and reuse
# ─────────────────────────────────────────────────────────────────────────

_registry: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    service: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> CircuitBreaker:
    """
    Returns the circuit breaker for a named service.
    Creates one if it doesn't exist.
    Singleton per service — same circuit reused across all calls.

    Usage:
        cb = get_circuit_breaker("supabase")
        cb = get_circuit_breaker("groq_llm")
        cb = get_circuit_breaker("twilio_whatsapp")
        cb = get_circuit_breaker("twilio_voice")
        cb = get_circuit_breaker("sendgrid")
    """
    if service not in _registry:
        _registry[service] = CircuitBreaker(
            service=service,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        logger.debug(
            "circuit_breaker_created",
            service=service,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
    return _registry[service]


# ─────────────────────────────────────────────────────────────────────────
# Pre-configured circuit breakers for each external service
# Import these directly — don't create new ones
# ─────────────────────────────────────────────────────────────────────────

# Supabase — 5 failures, 60s recovery
supabase_circuit = get_circuit_breaker(
    "supabase",
    failure_threshold=5,
    recovery_timeout=60.0,
)

# Groq LLM — 3 failures, 30s recovery (faster recovery for LLM)
groq_circuit = get_circuit_breaker(
    "groq_llm",
    failure_threshold=3,
    recovery_timeout=30.0,
)

# Twilio WhatsApp — 5 failures, 60s recovery
twilio_whatsapp_circuit = get_circuit_breaker(
    "twilio_whatsapp",
    failure_threshold=5,
    recovery_timeout=60.0,
)

# Twilio Voice — 5 failures, 60s recovery
twilio_voice_circuit = get_circuit_breaker(
    "twilio_voice",
    failure_threshold=5,
    recovery_timeout=60.0,
)

# SendGrid — 5 failures, 60s recovery
sendgrid_circuit = get_circuit_breaker(
    "sendgrid",
    failure_threshold=5,
    recovery_timeout=60.0,
)