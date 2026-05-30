from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

from app.config.settings import get_settings
from app.models.database import get_admin_db, Filter, FilterOperator
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


FOLLOW_UP_TEMPLATES = {
    "post_escalation": (
        "Hi {name}! This is {business_name}. We wanted to check if your issue "
        "has been resolved. Please let us know if you need any further help. 🙏"
    ),
    "lead_nurture": (
        "Hi {name}! This is {business_name}. You enquired with us recently — "
        "we would love to assist you further. Do you have any questions? ✨"
    ),
}


async def schedule_follow_up(
    user_id: str,
    conversation_id: str,
    from_contact: str,
    channel: str,
    follow_up_type: str,
    customer_name: str | None,
    business_name: str,
    delay_hours: float,
) -> None:
    """Stores a scheduled follow-up message in the follow_ups table."""
    db = get_admin_db()
    name = customer_name or "there"
    template = FOLLOW_UP_TEMPLATES.get(follow_up_type, FOLLOW_UP_TEMPLATES["lead_nurture"])
    message = template.format(name=name, business_name=business_name)
    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(hours=delay_hours)
    ).isoformat()
    try:
        await db.insert("follow_ups", {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "from_contact": from_contact,
            "channel": channel,
            "follow_up_type": follow_up_type,
            "message": message,
            "scheduled_at": scheduled_at,
            "sent": False,
        })
        logger.info(
            "follow_up_scheduled",
            user_id=user_id,
            follow_up_type=follow_up_type,
            delay_hours=delay_hours,
        )
    except Exception as e:
        logger.error("follow_up_schedule_failed", error=str(e))


async def process_due_follow_ups() -> None:
    """
    Finds all unsent follow-ups whose scheduled_at is now past and sends them.
    Called every 5 minutes by APScheduler in scheduler.py.
    """
    db = get_admin_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        due = await db.list_records(
            "follow_ups",
            filters=[
                Filter("sent", FilterOperator.EQ, False),
                Filter("scheduled_at", FilterOperator.LTE, now),
            ],
            page_size=50,
            order_by="scheduled_at",
            ascending=True,
        )
        if not due:
            return
        logger.info("processing_due_follow_ups", count=len(due))
        for item in due:
            await _send_follow_up(item)
    except Exception as e:
        logger.error("follow_up_processing_error", error=str(e))


async def _send_follow_up(follow_up: dict[str, Any]) -> None:
    """Sends a single follow-up message and marks it sent in Supabase."""
    db = get_admin_db()
    fid = follow_up["id"]
    channel = follow_up["channel"]
    try:
        if channel == "whatsapp":
            await _send_whatsapp(follow_up["from_contact"], follow_up["message"])
        elif channel == "email":
            await _send_email(follow_up["from_contact"], follow_up["message"])
        await db.update("follow_ups", fid, {
            "sent": True,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("follow_up_sent", follow_up_id=fid, channel=channel)
    except Exception as e:
        await db.update("follow_ups", fid, {"error": str(e)[:500]})
        logger.error("follow_up_send_failed", follow_up_id=fid, error=str(e))


async def _send_whatsapp(to: str, message: str) -> None:
    from twilio.rest import Client as TwilioClient
    def _send() -> None:
        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            from_=settings.whatsapp_from_number,
            to=to,
            body=message,
        )
    await asyncio.to_thread(_send)


async def _send_email(to: str, message: str) -> None:
    if not settings.zapier_email_webhook_url:
        logger.warning("zapier_not_configured_skipping_email_follow_up")
        return
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(settings.zapier_email_webhook_url, json={
            "to": to,
            "message": message,
        })
