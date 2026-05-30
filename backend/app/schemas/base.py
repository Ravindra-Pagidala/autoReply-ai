from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


# ─────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────

class AutoReplyBaseModel(BaseModel):
    """
    Base model for all schemas.
    Strips whitespace, validates on assignment, ignores extra fields.
    """
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class TimestampedModel(AutoReplyBaseModel):
    """Base for DB response models that have timestamps."""
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────
# Standard API Responses
# ─────────────────────────────────────────────────────────────────────────

class PaginatedResponse(AutoReplyBaseModel):
    """Standard paginated response wrapper for all list endpoints."""
    data: list[Any]
    total: int
    page: int
    page_size: int
    has_more: bool

    @classmethod
    def build(
        cls,
        data: list[Any],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse":
        return cls(
            data=data,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total,
        )


class SuccessResponse(AutoReplyBaseModel):
    """Standard success response."""
    success: bool = True
    message: str


class ErrorResponse(AutoReplyBaseModel):
    """Standard error response. Never exposes stack traces."""
    success: bool = False
    error_code: str
    message: str


# ─────────────────────────────────────────────────────────────────────────
# Business Profile Schemas
# Matches: business_profiles table exactly
# ─────────────────────────────────────────────────────────────────────────

class BusinessProfileCreate(AutoReplyBaseModel):
    """Used when user completes onboarding step 1."""
    business_name: str
    industry: str
    description: str | None = None
    whatsapp_number: str | None = None
    phone_number: str | None = None
    business_email: str | None = None


class BusinessProfileUpdate(AutoReplyBaseModel):
    """Used for settings page updates. All fields optional."""
    business_name: str | None = None
    industry: str | None = None
    description: str | None = None
    whatsapp_number: str | None = None
    phone_number: str | None = None
    business_email: str | None = None
    bot_active: bool | None = None
    bot_tone: str | None = None
    bot_language: str | None = None
    fallback_message: str | None = None
    working_hours_start: str | None = None
    working_hours_end: str | None = None
    working_days: str | None = None
    escalation_threshold: int | None = None
    timezone: str | None = None
    onboarding_step: int | None = None
    onboarding_completed: bool | None = None


class BusinessProfileResponse(AutoReplyBaseModel):
    """
    Full business profile response.
    Matches every column in business_profiles table.
    """
    id: str
    user_id: str
    business_name: str | None = None
    industry: str | None = None
    description: str | None = None
    whatsapp_number: str | None = None
    phone_number: str | None = None
    business_email: str | None = None
    bot_active: bool = True
    bot_tone: str = "professional"
    bot_language: str = "english"
    fallback_message: str | None = None
    working_hours_start: str | None = None
    working_hours_end: str | None = None
    working_days: str = "Mon-Sat"
    escalation_threshold: int = 2
    timezone: str = "Asia/Kolkata"         
    onboarding_completed: bool = False
    onboarding_step: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None      


# ─────────────────────────────────────────────────────────────────────────
# Team Member Schemas
# Matches: team_members table exactly
# Was COMPLETELY MISSING before
# ─────────────────────────────────────────────────────────────────────────

class TeamMemberInvite(AutoReplyBaseModel):
    """Used when owner invites a team member."""
    member_email: str
    role: str = "agent"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"owner", "agent", "viewer"}
        if v not in allowed:
            raise ValueError(
                f"Role must be one of: {', '.join(allowed)}"
            )
        return v

    @field_validator("member_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v.lower().strip()


class TeamMemberUpdate(AutoReplyBaseModel):
    """Used to change a team member's role."""
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"agent", "viewer"}
        if v not in allowed:
            raise ValueError(
                f"Role must be one of: {', '.join(allowed)}"
            )
        return v


class TeamMemberResponse(AutoReplyBaseModel):
    """
    Full team member response.
    Matches every column in team_members table.
    """
    id: str
    owner_id: str
    member_email: str
    member_user_id: str | None = None
    role: str = "agent"
    status: str = "pending"
    invited_at: datetime | None = None
    accepted_at: datetime | None = None
    created_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────
# Conversation Schemas
# Matches: conversations table exactly
# ─────────────────────────────────────────────────────────────────────────

class ConversationCreate(AutoReplyBaseModel):
    """Used by webhook handlers to create a new conversation thread."""
    user_id: str
    channel: str
    from_contact: str
    status: str = "ai_handled"
    escalated: bool = False
    response_time_ms: int | None = None
    intent: str | None = None       
    confidence: float | None = None       
    reasoning_trace: list[Any] = []      


class ConversationUpdate(AutoReplyBaseModel):
    """Used to update conversation after AI processes it."""
    status: str | None = None
    escalated: bool | None = None
    resolved: bool | None = None
    response_time_ms: int | None = None
    intent: str | None = None
    confidence: float | None = None
    reasoning_trace: list[Any] | None = None
    updated_at: str | None = None


class ConversationResponse(AutoReplyBaseModel):
    """
    Full conversation response.
    Matches every column in conversations table.
    """
    id: str
    user_id: str
    channel: str
    from_contact: str
    status: str = "ai_handled"
    escalated: bool = False
    resolved: bool = False
    response_time_ms: int | None = None
    intent: str | None = None
    confidence: float | None = None
    sentiment: str | None = None
    sentiment_score: float | None = None
    reasoning_trace: list[Any] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────
# Message Schemas
# Matches: messages table exactly — was already correct
# ─────────────────────────────────────────────────────────────────────────

class MessageCreate(AutoReplyBaseModel):
    """Used to save each turn in a conversation."""
    conversation_id: str
    user_id: str
    direction: str   # inbound / outbound
    content: str
    sent_by: str = "ai"   # ai / human


class MessageResponse(AutoReplyBaseModel):
    """
    Full message response.
    Matches every column in messages table.
    """
    id: str
    conversation_id: str
    user_id: str
    direction: str
    content: str
    sent_by: str = "ai"
    created_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────
# Lead Schemas
# Matches: leads table exactly
# ─────────────────────────────────────────────────────────────────────────

class LeadCreate(AutoReplyBaseModel):
    """Used by lead_service to save extracted lead."""
    user_id: str
    conversation_id: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    channel: str
    query: str | None = None
    status: str = "new"


class LeadUpdate(AutoReplyBaseModel):
    """Used from dashboard to update lead status."""
    status: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class LeadResponse(AutoReplyBaseModel):
    """
    Full lead response.
    Matches every column in leads table.
    """
    id: str
    user_id: str
    conversation_id: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    channel: str
    query: str | None = None
    status: str = "new"
    lead_score: int | None = None
    lead_temperature: str | None = None
    score_reason: str | None = None
    recommendation: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────
# Knowledge Base Schemas
# Matches: knowledge_base table exactly
# ─────────────────────────────────────────────────────────────────────────

class KnowledgeBaseUpload(AutoReplyBaseModel):
    """Metadata saved when user uploads a document."""
    user_id: str
    filename: str
    file_type: str
    file_size: int


class KnowledgeBaseResponse(AutoReplyBaseModel):
    """
    Full knowledge base document response.
    content field excluded — too large to return in API.
    Matches every other column in knowledge_base table.
    """
    id: str
    user_id: str
    filename: str
    file_type: str | None = None
    file_size: int | None = None
    chunk_count: int = 0
    training_status: str = "pending"
    training_error: str | None = None
    trained: bool = False
    created_at: datetime | None = None   
    updated_at: datetime | None = None    


# ─────────────────────────────────────────────────────────────────────────
# Escalation Schemas
# Matches: escalations table exactly
# ─────────────────────────────────────────────────────────────────────────

class EscalationCreate(AutoReplyBaseModel):
    """Created when AI confidence is too low or retries exhausted."""
    user_id: str
    conversation_id: str
    channel: str
    from_contact: str
    reason: str
    status: str = "open"


class EscalationResolve(AutoReplyBaseModel):
    """Used when owner/agent manually resolves an escalation."""
    human_reply: str
    assigned_to: str | None = None


class EscalationResponse(AutoReplyBaseModel):
    """
    Full escalation response.
    Matches every column in escalations table.
    """
    id: str
    user_id: str
    conversation_id: str
    channel: str
    from_contact: str
    reason: str
    status: str = "open"
    assigned_to: str | None = None
    human_reply: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None    


# ─────────────────────────────────────────────────────────────────────────
# Notification Schemas
# Matches: notifications table exactly
# ─────────────────────────────────────────────────────────────────────────

class NotificationCreate(AutoReplyBaseModel):
    """Created whenever a notable event happens."""
    user_id: str
    type: str    # escalation / new_lead / invite / system
    title: str
    message: str
    reference_id: str | None = None
    reference_type: str | None = None    # escalation / lead / conversation


class NotificationMarkRead(AutoReplyBaseModel):
    """Used to mark notification as read."""
    read: bool = True


class NotificationResponse(AutoReplyBaseModel):
    """
    Full notification response.
    Matches every column in notifications table.
    """
    id: str
    user_id: str
    type: str
    title: str
    message: str
    read: bool = False                  
    reference_id: str | None = None
    reference_type: str | None = None
    created_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────
# Appointment Schemas
# Matches: appointments table exactly
# ─────────────────────────────────────────────────────────────────────────

class AppointmentCreate(AutoReplyBaseModel):
    """Created when AI detects booking_request intent."""
    user_id: str
    conversation_id: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    channel: str
    service_type: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None
    notes: str | None = None
    status: str = "pending"


class AppointmentUpdate(AutoReplyBaseModel):
    """Used from dashboard to update appointment status or details."""
    status: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None
    service_type: str | None = None
    notes: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None


class AppointmentResponse(AutoReplyBaseModel):
    """Full appointment response. Matches every column in appointments table."""
    id: str
    user_id: str
    conversation_id: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    channel: str
    service_type: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None
    notes: str | None = None
    status: str = "pending"
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────
# Dashboard Stats Schema
# ─────────────────────────────────────────────────────────────────────────

class DashboardStats(AutoReplyBaseModel):
    """Aggregated stats for dashboard home screen."""
    messages_today: int = 0
    leads_today: int = 0
    calls_today: int = 0
    emails_today: int = 0
    escalations_open: int = 0
    avg_response_ms: int = 0
    total_conversations: int = 0
    total_leads: int = 0
    unread_notifications: int = 0


# ─────────────────────────────────────────────────────────────────────────
# Test Run Schemas
# Matches: test_runs + test_results tables exactly
# ─────────────────────────────────────────────────────────────────────────

class TestRunRequest(AutoReplyBaseModel):
    """Request body to start an automated test run."""
    test_type: str = "all"   # all / whatsapp / voice / email
    whatsapp_count: int = 10
    voice_count: int = 5
    email_count: int = 10

    @field_validator("test_type")
    @classmethod
    def validate_test_type(cls, v: str) -> str:
        allowed = {"all", "whatsapp", "voice", "email"}
        if v not in allowed:
            raise ValueError(
                f"test_type must be one of: {', '.join(allowed)}"
            )
        return v

    @field_validator("whatsapp_count", "voice_count", "email_count")
    @classmethod
    def validate_counts(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError("Count must be between 1 and 50")
        return v


class TestRunResponse(AutoReplyBaseModel):
    """
    Full test run response.
    Matches every column in test_runs table.
    """
    id: str                           
    user_id: str                      
    test_type: str
    triggered_by: str = "manual"         
    total_sent: int = 0
    total_success: int = 0
    total_failed: int = 0
    whatsapp_sent: int = 0
    whatsapp_success: int = 0
    voice_sent: int = 0
    voice_success: int = 0
    email_sent: int = 0
    email_success: int = 0
    avg_response_ms: int = 0
    leads_captured: int = 0
    status: str = "running"
    created_at: datetime | None = None   
    completed_at: datetime | None = None


class TestResultResponse(AutoReplyBaseModel):
    """
    Individual message result within a test run.
    Matches every column in test_results table.
    """
    id: str
    test_run_id: str
    user_id: str                         
    channel: str
    message_sent: str
    reply_received: str | None = None
    response_time_ms: int | None = None
    success: bool = False
    error_reason: str | None = None
    created_at: datetime | None = None   