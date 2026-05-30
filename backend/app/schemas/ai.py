from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import field_validator

from app.schemas.base import AutoReplyBaseModel


# ─────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────

class ChannelType(str, Enum):
    WHATSAPP = "whatsapp"
    VOICE = "voice"
    EMAIL = "email"


class IntentType(str, Enum):
    PRICING_INQUIRY = "pricing_inquiry"
    PRODUCT_INFO = "product_info"
    BOOKING_REQUEST = "booking_request"
    COMPLAINT = "complaint"
    GENERAL_QUERY = "general_query"
    HUMAN_REQUEST = "human_request"
    GREETING = "greeting"
    UNKNOWN = "unknown"


class TrainingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    TRAINED = "trained"
    FAILED = "failed"


class LeadStatus(str, Enum):
    NEW = "new"
    FOLLOW_UP = "follow_up"
    RESOLVED = "resolved"
    LOST = "lost"


class EscalationStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"


class ConversationStatus(str, Enum):
    AI_HANDLED = "ai_handled"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class MemberRole(str, Enum):
    OWNER = "owner"
    AGENT = "agent"
    VIEWER = "viewer"


class MemberStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# ─────────────────────────────────────────────────────────────────────────
# LangGraph Agent State
# Single source of truth between all graph nodes
# Serialisable — LangGraph can checkpoint and resume
# ─────────────────────────────────────────────────────────────────────────

class AgentState(AutoReplyBaseModel):
    """
    Shared state passed between all LangGraph nodes.
    Every node reads from and writes to this.
    Never store raw LLM response objects — extract what you need.

    Saved to conversations table after processing:
    - intent → conversations.intent
    - confidence → conversations.confidence
    - reasoning_trace → conversations.reasoning_trace
    """

    # ── Input ─────────────────────────────────────────────────────────
    user_id: str
    channel: ChannelType
    from_contact: str
    message: str
    business_profile: dict[str, Any]

    # ── RAG context ───────────────────────────────────────────────────
    rag_context: str = ""
    rag_chunks_found: int = 0
    rag_retrieval_failed: bool = False

    # ── Conversation history (last 5 turns) ───────────────────────────
    conversation_history: list[dict[str, str]] = []
    conversation_id: str | None = None

    # ── LLM output ────────────────────────────────────────────────────
    ai_reply: str = ""
    intent: IntentType = IntentType.UNKNOWN
    confidence: float = 0.0
    escalate: bool = False
    escalation_reason: str = ""

    # ── Extracted lead info ───────────────────────────────────────────
    lead_name: str | None = None
    lead_phone: str | None = None
    lead_email: str | None = None

    # ── Idempotency key (MessageSid for WhatsApp) ─────────────────────
    message_sid: str | None = None

    # ── Agent control ─────────────────────────────────────────────────
    retry_count: int = 0
    max_retries: int = 3
    error_message: str = ""

    # ── Observability — saved to conversations table ───────────────────
    reasoning_trace: list[dict[str, Any]] = []
    llm_latency_ms: int = 0
    rag_latency_ms: int = 0
    total_latency_ms: int = 0


# ─────────────────────────────────────────────────────────────────────────
# Structured LLM Output
# LLM MUST return exactly this shape via .with_structured_output()
# Never parse free text — always use this Pydantic model
# ─────────────────────────────────────────────────────────────────────────

class AIResponse(AutoReplyBaseModel):
    """
    Structured output from Groq LLM.
    Enforced via langchain's .with_structured_output(AIResponse).

    If LLM returns anything not matching this → Pydantic raises
    ValidationError → retry with clarifying prompt → escalate after 3.
    """

    reply: str
    escalate: bool = False
    escalation_reason: str = ""
    confidence: float = 1.0
    intent: IntentType = IntentType.GENERAL_QUERY
    lead_name: str | None = None
    lead_phone: str | None = None
    lead_email: str | None = None

    @field_validator("reply")
    @classmethod
    def validate_reply(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "LLM returned empty reply — triggers retry"
            )
        # Cap at 1500 chars for WhatsApp/SMS friendliness
        if len(v) > 1500:
            v = v[:1500] + "..."
        return v.strip()

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("lead_phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        import re
        cleaned = re.sub(r"[^\d+]", "", v)
        return cleaned if len(cleaned) >= 10 else None

    @field_validator("lead_email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        return v if "@" in v and "." in v else None