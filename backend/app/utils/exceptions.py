from __future__ import annotations

from typing import Any


# ─────────────────────────────────────────────────────────────────────────
# Base Exception
# ─────────────────────────────────────────────────────────────────────────

class AutoReplyBaseException(Exception):
    """
    Base exception for all AutoReply AI errors.
    Carries full context for structured logging.
    Never raise this directly — use a specific subclass.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        user_id: str | None = None,
        channel: str | None = None,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.user_id = user_id
        self.channel = channel
        self.operation = operation
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialise for structured logging."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "user_id": self.user_id,
            "channel": self.channel,
            "operation": self.operation,
            "context": self.context,
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"user_id={self.user_id!r}, "
            f"channel={self.channel!r}, "
            f"operation={self.operation!r}"
            f")"
        )


# ─────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────

class ConfigurationError(AutoReplyBaseException):
    """Missing or invalid env vars at startup. App refuses to start."""
    status_code = 500
    error_code = "CONFIGURATION_ERROR"


# ─────────────────────────────────────────────────────────────────────────
# LLM / AI Exceptions
# ─────────────────────────────────────────────────────────────────────────

class LLMException(AutoReplyBaseException):
    """Groq LLM call failed. Covers timeout, API error, rate limit."""
    status_code = 503
    error_code = "LLM_ERROR"


class LLMTimeoutException(LLMException):
    """LLM call exceeded groq_timeout_seconds. Retry with backoff."""
    error_code = "LLM_TIMEOUT"


class LLMRateLimitException(LLMException):
    """Groq rate limit hit. Retry with longer backoff."""
    error_code = "LLM_RATE_LIMIT"


class LLMMalformedOutputException(LLMException):
    """
    LLM returned output that fails Pydantic validation.
    Retry once with clarifying prompt before escalating.
    """
    error_code = "LLM_MALFORMED_OUTPUT"

    def __init__(
        self,
        message: str,
        *,
        raw_output: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.raw_output = raw_output
        self.context["raw_output"] = (
            raw_output[:200] if raw_output else None
        )


# ─────────────────────────────────────────────────────────────────────────
# RAG / Knowledge Base Exceptions
# ─────────────────────────────────────────────────────────────────────────

class RAGException(AutoReplyBaseException):
    """
    RAG retrieval failed.
    System degrades gracefully — LLM answers without context.
    """
    status_code = 503
    error_code = "RAG_ERROR"


class KnowledgeBaseEmptyException(RAGException):
    """No KB uploaded. Bot uses fallback_message from business_profile."""
    error_code = "KB_EMPTY"


class EmbeddingException(RAGException):
    """Document embedding failed during KB upload."""
    error_code = "EMBEDDING_ERROR"


class ChromaDBException(RAGException):
    """
    ChromaDB operation failed independently of retrieval.
    Covers: collection not found, disk full, corrupt index.
    Different from RAGException — ChromaDB infra issue, not retrieval issue.
    """
    error_code = "CHROMADB_ERROR"


# ─────────────────────────────────────────────────────────────────────────
# File Upload Exceptions
# ─────────────────────────────────────────────────────────────────────────

class FileUploadException(AutoReplyBaseException):
    """
    KB file upload failed.
    Covers: too large, wrong format, corrupt file, read error.
    """
    status_code = 400
    error_code = "FILE_UPLOAD_ERROR"


class FileTooLargeException(FileUploadException):
    """File exceeds MAX_UPLOAD_SIZE_MB."""
    error_code = "FILE_TOO_LARGE"

    def __init__(
        self,
        message: str,
        *,
        file_size_mb: float | None = None,
        max_size_mb: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.context["file_size_mb"] = file_size_mb
        self.context["max_size_mb"] = max_size_mb


class InvalidFileTypeException(FileUploadException):
    """File type not supported (only PDF, TXT, DOCX allowed)."""
    error_code = "INVALID_FILE_TYPE"

    def __init__(
        self,
        message: str,
        *,
        file_type: str | None = None,
        allowed_types: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.context["file_type"] = file_type
        self.context["allowed_types"] = allowed_types


# ─────────────────────────────────────────────────────────────────────────
# Channel / Webhook Exceptions
# ─────────────────────────────────────────────────────────────────────────

class WebhookException(AutoReplyBaseException):
    """Webhook parsing or validation failed."""
    status_code = 400
    error_code = "WEBHOOK_ERROR"


class DuplicateWebhookException(WebhookException):
    """
    Same webhook fired twice (Twilio retry).
    Idempotency check — return 200 silently, do not reprocess.
    """
    status_code = 200
    error_code = "DUPLICATE_WEBHOOK"


class WebhookSignatureException(WebhookException):
    """
    Twilio webhook signature validation failed.
    Possible spoofed request — reject immediately with 403.
    """
    status_code = 403
    error_code = "INVALID_WEBHOOK_SIGNATURE"


class RateLimitException(AutoReplyBaseException):
    """
    Our own API rate limit exceeded.
    Separate from Groq rate limit.
    Returned when webhook endpoint hammered.
    """
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"


# ─────────────────────────────────────────────────────────────────────────
# Twilio Exceptions
# ─────────────────────────────────────────────────────────────────────────

class TwilioException(AutoReplyBaseException):
    """Twilio API call failed."""
    status_code = 503
    error_code = "TWILIO_ERROR"


class TwilioWhatsAppException(TwilioException):
    """WhatsApp message send failed via Twilio."""
    error_code = "TWILIO_WHATSAPP_ERROR"


class TwilioVoiceException(TwilioException):
    """Voice call handling failed via Twilio."""
    error_code = "TWILIO_VOICE_ERROR"


# ─────────────────────────────────────────────────────────────────────────
# SendGrid Exceptions
# ─────────────────────────────────────────────────────────────────────────

class SendGridException(AutoReplyBaseException):
    """SendGrid email send failed."""
    status_code = 503
    error_code = "SENDGRID_ERROR"


# ─────────────────────────────────────────────────────────────────────────
# Database Exceptions
# ─────────────────────────────────────────────────────────────────────────

class DatabaseException(AutoReplyBaseException):
    """Supabase operation failed."""
    status_code = 503
    error_code = "DATABASE_ERROR"


class RecordNotFoundException(DatabaseException):
    """Requested record does not exist."""
    status_code = 404
    error_code = "RECORD_NOT_FOUND"


class DuplicateRecordException(DatabaseException):
    """Insert violates unique constraint."""
    status_code = 409
    error_code = "DUPLICATE_RECORD"


# ─────────────────────────────────────────────────────────────────────────
# Auth Exceptions
# ─────────────────────────────────────────────────────────────────────────

class AuthException(AutoReplyBaseException):
    """Authentication or authorisation failed."""
    status_code = 401
    error_code = "AUTH_ERROR"


class InvalidTokenException(AuthException):
    """JWT token is missing, expired, or invalid."""
    error_code = "INVALID_TOKEN"


class InsufficientPermissionsException(AuthException):
    """
    User role doesn't allow this action.
    Viewer trying to delete → 403.
    Agent trying to change settings → 403.
    """
    status_code = 403
    error_code = "INSUFFICIENT_PERMISSIONS"


# ─────────────────────────────────────────────────────────────────────────
# Team Member Exceptions
# ─────────────────────────────────────────────────────────────────────────

class TeamMemberException(AutoReplyBaseException):
    """Team member operation failed."""
    status_code = 400
    error_code = "TEAM_MEMBER_ERROR"


class MemberAlreadyInvitedException(TeamMemberException):
    """Email already invited to this workspace."""
    status_code = 409
    error_code = "MEMBER_ALREADY_INVITED"


class InvalidRoleException(TeamMemberException):
    """Role must be one of: owner, agent, viewer."""
    error_code = "INVALID_ROLE"


# ─────────────────────────────────────────────────────────────────────────
# Business Logic Exceptions
# ─────────────────────────────────────────────────────────────────────────

class BusinessProfileNotFoundException(AutoReplyBaseException):
    """
    Webhook received for number/email not registered on platform.
    Means no business_profile matches the incoming channel contact.
    """
    status_code = 404
    error_code = "BUSINESS_PROFILE_NOT_FOUND"


class OnboardingIncompleteException(AutoReplyBaseException):
    """User tries to access dashboard before completing onboarding."""
    status_code = 403
    error_code = "ONBOARDING_INCOMPLETE"


class BotInactiveException(AutoReplyBaseException):
    """
    Webhook received but bot_active = false for this business.
    Message is logged but not processed by AI.
    Return 200 to Twilio — not an error.
    """
    status_code = 200
    error_code = "BOT_INACTIVE"


# ─────────────────────────────────────────────────────────────────────────
# Escalation Exceptions
# ─────────────────────────────────────────────────────────────────────────

class EscalationRequiredException(AutoReplyBaseException):
    """
    AI confidence below threshold OR max retries exhausted.
    Triggers escalation flow — human takes over.
    Not an error — expected behaviour.
    Returns 200 to Twilio — customer gets fallback message.
    """
    status_code = 200
    error_code = "ESCALATION_REQUIRED"

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        conversation_id: str | None = None,
        ai_reply: str | None = None,
        confidence: float | None = None,
        retry_count: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.reason = reason
        self.conversation_id = conversation_id
        self.ai_reply = ai_reply
        self.confidence = confidence
        self.retry_count = retry_count
        self.context.update(
            {
                "reason": reason,
                "conversation_id": conversation_id,
                "confidence": confidence,
                "retry_count": retry_count,
            }
        )


# ─────────────────────────────────────────────────────────────────────────
# Test System Exceptions
# ─────────────────────────────────────────────────────────────────────────

class TestRunException(AutoReplyBaseException):
    """Automated test run failed to start or complete."""
    status_code = 500
    error_code = "TEST_RUN_ERROR"