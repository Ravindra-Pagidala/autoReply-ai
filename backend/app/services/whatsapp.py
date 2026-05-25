from __future__ import annotations

import time
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from app.config.settings import get_settings
from app.utils.circuit_breaker import twilio_whatsapp_circuit, CircuitOpenException
from app.utils.exceptions import (
    BotInactiveException,
    BusinessProfileNotFoundException,
    DuplicateWebhookException,
    TwilioWhatsAppException,
)
from app.utils.logger import get_logger, bind_request_context, log_retry_attempt
from app.models.database import get_admin_db
from app.schemas.whatsapp import WhatsAppInbound
from app.agents.ai_brain import process_message

settings = get_settings()
logger = get_logger(__name__)


def _get_twilio_client() -> TwilioClient:
    return TwilioClient(
        settings.twilio_account_sid,
        settings.twilio_auth_token,
    )


async def handle_whatsapp_message(
    payload: dict[str, Any],
) -> str:
    """
    Handles inbound WhatsApp webhook from Twilio.
    Returns TwiML response string.

    Flow:
    1. Parse + validate payload
    2. Idempotency check (MessageSid)
    3. Load business profile
    4. Check bot active
    5. Process via AI brain
    6. Send reply via Twilio
    7. Return empty TwiML (reply already sent)
    """
    inbound = WhatsAppInbound(**payload)
    request_id = bind_request_context(
        channel="whatsapp",
        user_id=None,
    )

    logger.info(
        "whatsapp_webhook_received",
        message_sid=inbound.message_id,
        from_number=inbound.from_number,
    )

    db = get_admin_db()

    # Idempotency — Twilio can fire same webhook twice
    existing = await db.get_by_field(
        "conversations",
        "from_contact",
        inbound.from_number,
    )
    # Check by MessageSid stored in messages table
    existing_msg = await db.get_by_field(
        "messages",
        "content",
        inbound.message_id,
    )
    if existing_msg:
        logger.warning(
            "whatsapp_duplicate_webhook",
            message_sid=inbound.message_id,
        )
        raise DuplicateWebhookException(
            "Already processed",
            channel="whatsapp",
            operation="handle_whatsapp_message",
            context={"message_sid": inbound.message_id},
        )

    # Find business profile by WhatsApp number
    profile = await db.get_by_field(
        "business_profiles",
        "whatsapp_number",
        inbound.to_number,
    )
    if not profile:
        # Try sandbox — all sandbox messages go to default profile
        profile = await db.get_by_field(
            "business_profiles",
            "whatsapp_number",
            settings.twilio_whatsapp_sandbox,
        )
    if not profile:
        logger.warning(
            "whatsapp_no_business_profile",
            to_number=inbound.to_number,
        )
        raise BusinessProfileNotFoundException(
            f"No profile for {inbound.to_number}",
            channel="whatsapp",
            operation="handle_whatsapp_message",
        )

    bind_request_context(
        request_id=request_id,
        user_id=profile["user_id"],
        channel="whatsapp",
    )

    # Check bot active
    if not profile.get("bot_active", True):
        raise BotInactiveException(
            "Bot is paused",
            user_id=profile["user_id"],
            channel="whatsapp",
        )

    # Skip media messages — only handle text
    if inbound.has_media:
        reply_text = (
            "Thank you for the media. "
            "Our team will review and get back to you."
        )
        await _send_whatsapp_reply(
            to=inbound.From,
            body=reply_text,
        )
        return _empty_twiml()

    # Process via AI brain
    result = await process_message(
        user_id=profile["user_id"],
        channel="whatsapp",
        from_contact=inbound.from_number,
        message=inbound.Body,
        business_profile=profile,
    )

    # Send reply
    await _send_whatsapp_reply(
        to=inbound.From,
        body=result["reply"],
    )

    logger.info(
        "whatsapp_reply_sent",
        from_number=inbound.from_number,
        escalated=result["escalated"],
        latency_ms=result["total_latency_ms"],
    )

    return _empty_twiml()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(TwilioWhatsAppException),
    before_sleep=lambda rs: log_retry_attempt(
        "twilio_whatsapp_send",
        rs.attempt_number, 3,
        str(rs.outcome.exception()), 0,
    ),
    reraise=True,
)
async def _send_whatsapp_reply(to: str, body: str) -> None:
    """Sends WhatsApp reply via Twilio with circuit breaker + retry."""
    def _send() -> None:
        client = _get_twilio_client()
        client.messages.create(
            from_=settings.whatsapp_from_number,
            to=to,
            body=body,
        )

    try:
        await twilio_whatsapp_circuit.call(_send)
    except CircuitOpenException as e:
        logger.error("twilio_whatsapp_circuit_open", error=str(e))
        raise TwilioWhatsAppException(
            f"Twilio circuit open: {e}",
            channel="whatsapp",
            operation="send_reply",
        ) from e
    except TwilioRestException as e:
        logger.error(
            "twilio_whatsapp_send_failed",
            error=str(e),
            to=to,
        )
        raise TwilioWhatsAppException(
            f"Twilio send failed: {e}",
            channel="whatsapp",
            operation="send_reply",
        ) from e


def _empty_twiml() -> str:
    """Returns empty TwiML — reply already sent via REST API."""
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'