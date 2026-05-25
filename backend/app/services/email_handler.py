from __future__ import annotations

from typing import Any

import sendgrid
from sendgrid.helpers.mail import Mail
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import get_settings
from app.utils.circuit_breaker import sendgrid_circuit, CircuitOpenException
from app.utils.exceptions import (
    BotInactiveException,
    BusinessProfileNotFoundException,
    SendGridException,
)
from app.utils.logger import get_logger, bind_request_context, log_retry_attempt
from app.models.database import get_admin_db
from app.schemas.email import EmailInbound
from app.agents.ai_brain import process_message

settings = get_settings()
logger = get_logger(__name__)


async def handle_inbound_email(
    payload: dict[str, Any],
) -> None:
    """
    Handles inbound email from SendGrid Inbound Parse.

    Flow:
    1. Parse payload
    2. Spam check
    3. Find business profile by to_email
    4. Process via AI brain
    5. Send reply via SendGrid
    """
    inbound = EmailInbound(**payload)
    bind_request_context(channel="email")

    logger.info(
        "email_webhook_received",
        sender=inbound.sender_email,
        subject=inbound.subject,
    )

    # Spam check
    if inbound.is_spam:
        logger.warning(
            "email_spam_detected",
            sender=inbound.sender_email,
            spam_score=inbound.spam_score,
        )
        return

    # Empty body check
    if not inbound.body.strip():
        logger.warning(
            "email_empty_body",
            sender=inbound.sender_email,
        )
        return

    db = get_admin_db()

    # Find business profile by email
    profile = await db.get_by_field(
        "business_profiles",
        "business_email",
        inbound.to.lower().strip(),
    )
    if not profile:
        logger.warning(
            "email_no_business_profile",
            to_email=inbound.to,
        )
        raise BusinessProfileNotFoundException(
            f"No profile for {inbound.to}",
            channel="email",
        )

    bind_request_context(
        user_id=profile["user_id"],
        channel="email",
    )

    if not profile.get("bot_active", True):
        raise BotInactiveException(
            "Bot paused",
            user_id=profile["user_id"],
            channel="email",
        )

    # Process via AI brain
    result = await process_message(
        user_id=profile["user_id"],
        channel="email",
        from_contact=inbound.sender_email,
        message=f"Subject: {inbound.subject}\n\n{inbound.body}",
        business_profile=profile,
    )

    # Build reply subject
    subject = inbound.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    # Send reply
    await _send_email_reply(
        to_email=inbound.sender_email,
        subject=subject,
        body=result["reply"],
        business_name=profile.get("business_name", "Our Business"),
    )

    logger.info(
        "email_reply_sent",
        to=inbound.sender_email,
        escalated=result["escalated"],
        latency_ms=result["total_latency_ms"],
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(SendGridException),
    before_sleep=lambda rs: log_retry_attempt(
        "sendgrid_send",
        rs.attempt_number, 3,
        str(rs.outcome.exception()), 0,
    ),
    reraise=True,
)
async def _send_email_reply(
    to_email: str,
    subject: str,
    body: str,
    business_name: str,
) -> None:
    """Sends email reply via SendGrid with circuit breaker + retry."""
    html_body = body.replace("\n", "<br>")

    message = Mail(
        from_email=(settings.sendgrid_from_email, business_name),
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
        html_content=f"<p>{html_body}</p>",
    )

    def _send() -> None:
        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        response = sg.send(message)
        if response.status_code not in (200, 201, 202):
            raise SendGridException(
                f"SendGrid returned {response.status_code}",
                channel="email",
                operation="send_reply",
            )

    try:
        await sendgrid_circuit.call(_send)
    except CircuitOpenException as e:
        logger.error("sendgrid_circuit_open", error=str(e))
        raise SendGridException(
            f"SendGrid circuit open: {e}",
            channel="email",
            operation="send_reply",
        ) from e
    except SendGridException:
        raise
    except Exception as e:
        logger.error("sendgrid_send_failed", error=str(e))
        raise SendGridException(
            f"SendGrid failed: {e}",
            channel="email",
            operation="send_reply",
        ) from e