from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.utils.exceptions import (
    InvalidTokenException,
    RecordNotFoundException,
)
from app.utils.logger import get_logger
from app.models.database import Filter, FilterOperator, get_user_db, get_admin_db
from app.schemas.base import (
    AppointmentResponse,
    AppointmentUpdate,
    DashboardStats,
    EscalationResolve,
    EscalationResponse,
    LeadResponse,
    LeadUpdate,
    ConversationResponse,
    MessageResponse,
    NotificationResponse,
    PaginatedResponse,
    SuccessResponse,
)
from app.api.auth import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _today_iso() -> str:
    return datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    user: dict[str, Any] = Depends(get_current_user),
) -> DashboardStats:
    """Dashboard home stats — messages today, leads, calls, escalations."""
    db = get_admin_db()
    user_id = user["id"]
    today = _today_iso()

    user_filter = Filter("user_id", FilterOperator.EQ, user_id)
    today_filter = Filter("created_at", FilterOperator.GTE, today)

    # Run all counts + response time fetch concurrently
    import asyncio
    (
        messages_today,
        leads_today,
        calls_today,
        emails_today,
        escalations_open,
        total_conversations,
        total_leads,
        unread_notifications,
        response_rows,
    ) = await asyncio.gather(
        db.count("conversations", [user_filter, today_filter]),
        db.count("leads", [user_filter, today_filter]),
        db.count("conversations", [
            user_filter, today_filter,
            Filter("channel", FilterOperator.EQ, "voice"),
        ]),
        db.count("conversations", [
            user_filter, today_filter,
            Filter("channel", FilterOperator.EQ, "email"),
        ]),
        db.count("escalations", [
            user_filter,
            Filter("status", FilterOperator.EQ, "open"),
        ]),
        db.count("conversations", [user_filter]),
        db.count("leads", [user_filter]),
        db.count("notifications", [
            user_filter,
            Filter("read", FilterOperator.EQ, False),
        ]),
        db.list_records(
            "conversations",
            filters=[
                user_filter,
                Filter("response_time_ms", FilterOperator.GTE, 1),
            ],
            select="response_time_ms",
            page_size=100,
        ),
    )

    avg_response_ms = (
        int(sum(r["response_time_ms"] for r in response_rows) / len(response_rows))
        if response_rows else 0
    )

    return DashboardStats(
        messages_today=messages_today,
        leads_today=leads_today,
        calls_today=calls_today,
        emails_today=emails_today,
        escalations_open=escalations_open,
        avg_response_ms=avg_response_ms,
        total_conversations=total_conversations,
        total_leads=total_leads,
        unread_notifications=unread_notifications,
    )


@router.get("/conversations")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: str | None = Query(None),
    escalated: bool | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse:
    """Paginated conversations list with optional filters."""
    db = get_admin_db()
    user_id = user["id"]

    filters = [Filter("user_id", FilterOperator.EQ, user_id)]
    if channel:
        filters.append(Filter("channel", FilterOperator.EQ, channel))
    if escalated is not None:
        filters.append(Filter("escalated", FilterOperator.EQ, escalated))

    import asyncio
    rows, total = await asyncio.gather(
        db.list_records(
            "conversations",
            filters=filters,
            page=page,
            page_size=page_size,
        ),
        db.count("conversations", filters),
    )

    return PaginatedResponse.build(
        data=[ConversationResponse(**r).model_dump() for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get all messages for a conversation thread."""
    db = get_admin_db()
    rows = await db.list_records(
        "messages",
        filters=[
            Filter("conversation_id", FilterOperator.EQ, conversation_id),
            Filter("user_id", FilterOperator.EQ, user["id"]),
        ],
        order_by="created_at",
        ascending=True,
        page_size=100,
    )
    return [MessageResponse(**r).model_dump() for r in rows]


@router.get("/leads")
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    channel: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse:
    """Paginated leads list with optional filters."""
    db = get_admin_db()
    user_id = user["id"]

    filters = [Filter("user_id", FilterOperator.EQ, user_id)]
    if status:
        filters.append(Filter("status", FilterOperator.EQ, status))
    if channel:
        filters.append(Filter("channel", FilterOperator.EQ, channel))

    import asyncio
    rows, total = await asyncio.gather(
        db.list_records("leads", filters=filters, page=page, page_size=page_size),
        db.count("leads", filters),
    )

    from app.utils.crm import get_lead_recommendation

    def _enrich(r: dict) -> dict:
        lead = LeadResponse(**r).model_dump()
        lead["recommendation"] = get_lead_recommendation(r)
        return lead

    return PaginatedResponse.build(
        data=[_enrich(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/leads/{lead_id}", response_model=SuccessResponse)
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """Update lead status or info."""
    db = get_admin_db()
    update_data = body.model_dump(exclude_none=True)
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.update("leads", lead_id, update_data)
    return SuccessResponse(message="Lead updated")


@router.get("/escalations")
async def list_escalations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse:
    """Paginated escalations list."""
    db = get_admin_db()
    user_id = user["id"]

    filters = [Filter("user_id", FilterOperator.EQ, user_id)]
    if status:
        filters.append(Filter("status", FilterOperator.EQ, status))

    import asyncio
    rows, total = await asyncio.gather(
        db.list_records("escalations", filters=filters, page=page, page_size=page_size),
        db.count("escalations", filters),
    )

    return PaginatedResponse.build(
        data=[EscalationResponse(**r).model_dump() for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/escalations/{escalation_id}/resolve", response_model=SuccessResponse)
async def resolve_escalation(
    escalation_id: str,
    body: EscalationResolve,
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """
    Resolve an escalation with human reply.
    Sends the human reply back to customer via original channel.
    """
    db = get_admin_db()
    escalation = await db.get_by_id("escalations", escalation_id)

    await db.update("escalations", escalation_id, {
        "status": "resolved",
        "human_reply": body.human_reply,
        "assigned_to": body.assigned_to or user["id"],
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # Send human reply back to customer on their channel
    channel = escalation.get("channel", "whatsapp")
    from_contact = escalation.get("from_contact", "")

    if channel == "whatsapp" and from_contact:
        try:
            from app.services.whatsapp import _send_whatsapp_reply
            await _send_whatsapp_reply(
                to=f"whatsapp:{from_contact}",
                body=body.human_reply,
            )
        except Exception as e:
            logger.error("escalation_reply_send_failed", error=str(e))

    elif channel == "email" and from_contact:
        try:
            from app.services.email_handler import _send_email_reply
            profile = await db.get_by_field(
                "business_profiles", "user_id", user["id"]
            )
            await _send_email_reply(
                to_email=from_contact,
                subject="Re: Your enquiry",
                body=body.human_reply,
                business_name=profile.get("business_name", "Our Business") if profile else "Our Business",
            )
        except Exception as e:
            logger.error("escalation_email_reply_failed", error=str(e))

    logger.info(
        "escalation_resolved",
        escalation_id=escalation_id,
        channel=channel,
        user_id=user["id"],
    )
    return SuccessResponse(message="Escalation resolved and reply sent")


@router.get("/notifications")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse:
    """Paginated notifications list."""
    db = get_admin_db()
    filters = [Filter("user_id", FilterOperator.EQ, user["id"])]
    if unread_only:
        filters.append(Filter("read", FilterOperator.EQ, False))

    import asyncio
    rows, total = await asyncio.gather(
        db.list_records("notifications", filters=filters, page=page, page_size=page_size),
        db.count("notifications", filters),
    )

    return PaginatedResponse.build(
        data=[NotificationResponse(**r).model_dump() for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/notifications/{notification_id}/read", response_model=SuccessResponse)
async def mark_notification_read(
    notification_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """Mark a notification as read."""
    db = get_admin_db()
    await db.update("notifications", notification_id, {"read": True})
    return SuccessResponse(message="Notification marked as read")


@router.get("/appointments")
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    channel: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse:
    """Paginated appointments list with optional filters."""
    db = get_admin_db()
    filters = [Filter("user_id", FilterOperator.EQ, user["id"])]
    if status:
        filters.append(Filter("status", FilterOperator.EQ, status))
    if channel:
        filters.append(Filter("channel", FilterOperator.EQ, channel))

    import asyncio
    rows, total = await asyncio.gather(
        db.list_records("appointments", filters=filters, page=page, page_size=page_size),
        db.count("appointments", filters),
    )
    return PaginatedResponse.build(
        data=[AppointmentResponse(**r).model_dump() for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/appointments/{appointment_id}", response_model=SuccessResponse)
async def update_appointment(
    appointment_id: str,
    body: AppointmentUpdate,
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """Update appointment status or details. Notifies customer on confirm/cancel."""
    db = get_admin_db()

    appointment = await db.get_by_id("appointments", appointment_id)

    update_data = body.model_dump(exclude_none=True)
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.update("appointments", appointment_id, update_data)

    new_status = body.status
    if new_status in ("confirmed", "cancelled") and appointment:
        channel = appointment.get("channel", "whatsapp")
        customer_phone = appointment.get("customer_phone")
        customer_email = appointment.get("customer_email")
        customer_name = appointment.get("customer_name") or "there"
        service = appointment.get("service_type") or "your appointment"
        date = appointment.get("appointment_date") or ""
        time = appointment.get("appointment_time") or ""
        when = f"{date} {time}".strip() or "the scheduled time"

        profile = await db.get_by_field("business_profiles", "user_id", user["id"])
        biz_name = profile.get("business_name", "Our Team") if profile else "Our Team"

        if new_status == "confirmed":
            msg = (
                f"Hi {customer_name}! Your appointment for {service} on {when} "
                f"has been confirmed by {biz_name}. We look forward to seeing you!"
            )
        else:
            msg = (
                f"Hi {customer_name}, unfortunately your appointment for {service} "
                f"on {when} has been cancelled by {biz_name}. "
                f"Please reach out to reschedule."
            )

        try:
            if channel == "whatsapp" and customer_phone:
                from app.services.whatsapp import _send_whatsapp_reply
                wa_to = customer_phone if customer_phone.startswith("whatsapp:") else f"whatsapp:{customer_phone}"
                await _send_whatsapp_reply(to=wa_to, body=msg)
            elif channel == "email" and customer_email:
                from app.services.email_handler import _send_email_reply
                subject = "Appointment Confirmed" if new_status == "confirmed" else "Appointment Cancelled"
                await _send_email_reply(
                    to_email=customer_email,
                    subject=subject,
                    body=msg,
                    business_name=biz_name,
                )
        except Exception as e:
            logger.error("appointment_notify_failed", error=str(e), channel=channel)

    return SuccessResponse(message="Appointment updated")


@router.patch("/notifications/read-all", response_model=SuccessResponse)
async def mark_all_notifications_read(
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """Mark all notifications as read for current user."""
    db = get_admin_db()
    rows = await db.list_records(
        "notifications",
        filters=[
            Filter("user_id", FilterOperator.EQ, user["id"]),
            Filter("read", FilterOperator.EQ, False),
        ],
        page_size=100,
    )
    import asyncio
    await asyncio.gather(*[
        db.update("notifications", r["id"], {"read": True})
        for r in rows
    ])
    return SuccessResponse(message=f"Marked {len(rows)} notifications as read")