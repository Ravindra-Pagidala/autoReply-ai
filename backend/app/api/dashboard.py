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
    BroadcastResult,
    BroadcastSendRequest,
    BroadcastSendResponse,
    DashboardStats,
    EscalationResolve,
    EscalationResponse,
    LeadResponse,
    LeadUpdate,
    ConversationResponse,
    MessageResponse,
    NotificationResponse,
    PaginatedResponse,
    SalesAgentGenerateRequest,
    SalesAgentPreview,
    SalesAgentResult,
    SalesAgentSendRequest,
    SalesAgentSendResponse,
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

        # For WhatsApp: always use conversation.from_contact (actual WhatsApp number with
        # country code). customer_phone is the stated phone — may lack country code and
        # is not guaranteed to be a WhatsApp number.
        if channel == "whatsapp":
            conv_id = appointment.get("conversation_id")
            if conv_id:
                try:
                    conv = await db.get_by_id("conversations", conv_id)
                    if conv and conv.get("from_contact"):
                        customer_phone = conv.get("from_contact")
                except Exception:
                    pass  # keep customer_phone as fallback
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


@router.get("/broadcast/contacts")
async def get_broadcast_contacts(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get all unique WhatsApp contacts (from_contact) for broadcast."""
    import asyncio
    from app.models.database import get_admin_client

    user_id = user["id"]
    client = get_admin_client()

    def _fetch() -> list[dict[str, Any]]:
        result = (
            client.table("conversations")
            .select("from_contact,created_at")
            .eq("user_id", user_id)
            .eq("channel", "whatsapp")
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        return result.data or []

    rows = await asyncio.to_thread(_fetch)

    seen: dict[str, str | None] = {}
    for r in rows:
        phone = (r.get("from_contact") or "").strip()
        if not phone or phone in seen:
            continue
        seen[phone] = r.get("created_at")

    return [{"phone": p, "last_seen": ts} for p, ts in seen.items()]


@router.post("/broadcast/send", response_model=BroadcastSendResponse)
async def send_broadcast(
    body: BroadcastSendRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> BroadcastSendResponse:
    """Send a WhatsApp broadcast message to selected contacts."""
    import asyncio
    from app.services.whatsapp import _send_whatsapp_reply

    async def _send_one(phone: str) -> BroadcastResult:
        wa_to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        try:
            await _send_whatsapp_reply(to=wa_to, body=body.message)
            return BroadcastResult(phone=phone, success=True)
        except Exception as e:
            return BroadcastResult(phone=phone, success=False, error=str(e)[:200])

    results = list(await asyncio.gather(*[_send_one(p) for p in body.contacts]))
    sent = sum(1 for r in results if r.success)
    failed = len(results) - sent

    logger.info(
        "broadcast_sent",
        user_id=user["id"],
        total=len(results),
        sent=sent,
        failed=failed,
    )
    return BroadcastSendResponse(sent=sent, failed=failed, results=results)


@router.post("/sales-agent/generate", response_model=list[SalesAgentPreview])
async def generate_sales_messages(
    body: SalesAgentGenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[SalesAgentPreview]:
    """
    Generate personalised AI outreach messages for selected leads.
    Looks up conversation.from_contact for WhatsApp leads so the
    number has a valid country code.
    """
    import asyncio
    from groq import Groq
    from app.models.database import get_admin_client

    user_id = user["id"]
    client = get_admin_client()
    settings_obj = __import__("app.config.settings", fromlist=["get_settings"]).get_settings()

    # Fetch business profile for business name
    db = get_admin_db()
    profile = await db.get_by_field("business_profiles", "user_id", user_id)
    business_name = (profile or {}).get("business_name") or "Our Business"

    # Fetch all selected leads in one query using Supabase .in_()
    def _fetch_leads() -> list[dict[str, Any]]:
        result = (
            client.table("leads")
            .select("*")
            .eq("user_id", user_id)
            .in_("id", body.lead_ids)
            .execute()
        )
        return result.data or []

    leads = await asyncio.to_thread(_fetch_leads)

    async def _build_preview(lead: dict[str, Any]) -> SalesAgentPreview:
        channel = lead.get("channel", "whatsapp")
        name = lead.get("name")
        query = lead.get("query")
        lead_id = lead["id"]

        # Resolve contact — prefer conversation.from_contact for WhatsApp
        to: str | None = None
        if channel == "whatsapp":
            conv_id = lead.get("conversation_id")
            if conv_id:
                try:
                    conv = await db.get_by_id("conversations", conv_id)
                    to = (conv or {}).get("from_contact") or lead.get("phone")
                except Exception:
                    to = lead.get("phone")
            else:
                to = lead.get("phone")
        elif channel == "email":
            to = lead.get("email")
        else:
            to = lead.get("phone") or lead.get("email")

        can_send = bool(to and str(to).strip())

        # Generate personalised message
        name_str = name or "there"
        query_ctx = f'They previously asked about: "{query}".' if query else ""
        medium = "WhatsApp message" if channel == "whatsapp" else "email"
        prompt = (
            f"Write a short, friendly {medium} for {business_name}.\n"
            f"Customer name: {name_str}\n"
            f"{query_ctx}\n"
            f"Campaign goal: {body.goal}\n\n"
            f"Requirements:\n"
            f"- Max 60 words\n"
            f"- Start with 'Hi {name_str}!'\n"
            f"- Warm and personal tone\n"
            f"- End with a clear call-to-action\n"
            f"- At most 2 emojis\n"
            f"Write only the message text, nothing else."
        )

        def _call_groq() -> str:
            groq_client = Groq(api_key=settings_obj.groq_api_key)
            resp = groq_client.chat.completions.create(
                model=settings_obj.groq_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()

        try:
            message = await asyncio.to_thread(_call_groq)
        except Exception as e:
            logger.error("sales_agent_generate_failed", lead_id=lead_id, error=str(e))
            message = (
                f"Hi {name_str}! This is {business_name}. "
                f"{body.goal}. Reply to learn more!"
            )

        return SalesAgentPreview(
            lead_id=lead_id,
            name=name,
            to=to,
            channel=channel,
            message=message,
            can_send=can_send,
        )

    previews = list(await asyncio.gather(*[_build_preview(l) for l in leads]))
    logger.info(
        "sales_agent_previews_generated",
        user_id=user_id,
        count=len(previews),
    )
    return previews


@router.post("/sales-agent/send", response_model=SalesAgentSendResponse)
async def send_sales_campaign(
    body: SalesAgentSendRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> SalesAgentSendResponse:
    """Send personalised sales messages to selected leads."""
    import asyncio
    from app.services.whatsapp import _send_whatsapp_reply
    from app.services.email_handler import _send_email_reply

    db = get_admin_db()
    profile = await db.get_by_field("business_profiles", "user_id", user["id"])
    business_name = (profile or {}).get("business_name") or "Our Business"

    async def _send_one(item: Any) -> SalesAgentResult:
        try:
            if item.channel == "whatsapp":
                wa_to = item.to if item.to.startswith("whatsapp:") else f"whatsapp:{item.to}"
                await _send_whatsapp_reply(to=wa_to, body=item.message)
            elif item.channel == "email":
                await _send_email_reply(
                    to_email=item.to,
                    subject=f"A message from {business_name}",
                    body=item.message,
                    business_name=business_name,
                )
            else:
                raise ValueError(f"Unsupported channel: {item.channel}")
            return SalesAgentResult(lead_id=item.lead_id, to=item.to, success=True)
        except Exception as e:
            return SalesAgentResult(
                lead_id=item.lead_id, to=item.to, success=False, error=str(e)[:200]
            )

    results = list(await asyncio.gather(*[_send_one(i) for i in body.items]))
    sent = sum(1 for r in results if r.success)
    failed = len(results) - sent

    logger.info(
        "sales_campaign_sent",
        user_id=user["id"],
        total=len(results),
        sent=sent,
        failed=failed,
    )
    return SalesAgentSendResponse(sent=sent, failed=failed, results=results)


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