from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Form, Request, HTTPException
from fastapi.responses import PlainTextResponse

from app.utils.exceptions import (
    BotInactiveException,
    BusinessProfileNotFoundException,
    DuplicateWebhookException,
)
from app.utils.logger import get_logger, bind_request_context, clear_request_context
from app.services.whatsapp import handle_whatsapp_message
from app.services.voice import handle_inbound_call, handle_voice_gather

logger = get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhooks"])


@router.post("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> str:
    """
    Twilio WhatsApp inbound webhook.
    Returns 200 immediately — processing in background.
    Twilio requires response within 15s or retries.
    """
    try:
        form_data = await request.form()
        payload = dict(form_data)
        bind_request_context(channel="whatsapp")
        logger.info("whatsapp_webhook_received", message_sid=payload.get("MessageSid"))
        background_tasks.add_task(handle_whatsapp_message, payload)
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    except Exception as e:
        logger.error("whatsapp_webhook_error", error=str(e))
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    finally:
        clear_request_context()


@router.post("/voice/inbound", response_class=PlainTextResponse)
async def voice_inbound_webhook(request: Request) -> str:
    """Twilio inbound voice call webhook. Returns TwiML greeting + Gather."""
    try:
        form_data = await request.form()
        payload = dict(form_data)
        bind_request_context(channel="voice")
        logger.info("voice_inbound_received", call_sid=payload.get("CallSid"))
        twiml = await handle_inbound_call(payload)
        return twiml
    except BusinessProfileNotFoundException:
        return _voice_error_twiml("Sorry, this number is not registered.")
    except BotInactiveException:
        return _voice_error_twiml("Our automated system is currently offline. Please try later.")
    except Exception as e:
        logger.error("voice_inbound_error", error=str(e))
        return _voice_error_twiml("Sorry, something went wrong. Please try again.")
    finally:
        clear_request_context()


@router.post("/voice/gather", response_class=PlainTextResponse)
async def voice_gather_webhook(request: Request) -> str:
    """Twilio voice gather webhook. Processes speech and returns AI reply via TTS."""
    try:
        form_data = await request.form()
        payload = dict(form_data)
        bind_request_context(channel="voice")
        logger.info("voice_gather_received", call_sid=payload.get("CallSid"))
        twiml = await handle_voice_gather(payload)
        return twiml
    except Exception as e:
        logger.error("voice_gather_error", error=str(e))
        return _voice_error_twiml("Sorry, something went wrong.")
    finally:
        clear_request_context()


@router.post("/email")
async def email_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    SendGrid inbound parse webhook.
    Returns 200 immediately — processing in background.
    """
    try:
        form_data = await request.form()
        payload = dict(form_data)
        bind_request_context(channel="email")
        logger.info("email_webhook_received", sender=payload.get("from"))

        from app.services.email_handler import handle_inbound_email
        background_tasks.add_task(handle_inbound_email, payload)
        return {"status": "received"}
    except Exception as e:
        logger.error("email_webhook_error", error=str(e))
        return {"status": "received"}  # Always 200 to SendGrid
    finally:
        clear_request_context()


def _voice_error_twiml(message: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Say>{message}</Say><Hangup/></Response>"
    )