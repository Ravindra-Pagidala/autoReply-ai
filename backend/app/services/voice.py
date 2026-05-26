from __future__ import annotations

from typing import Any

from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import get_settings
from app.utils.circuit_breaker import twilio_voice_circuit, CircuitOpenException
from app.utils.exceptions import (
    BotInactiveException,
    BusinessProfileNotFoundException,
    TwilioVoiceException,
)
from app.utils.logger import get_logger, bind_request_context, log_retry_attempt
from app.models.database import get_admin_db
from app.schemas.voice import VoiceInbound, VoiceGather
from app.agents.ai_brain import process_message

settings = get_settings()
logger = get_logger(__name__)


async def handle_inbound_call(
    payload: dict[str, Any],
) -> str:
    """
    Handles inbound voice call webhook.
    Returns TwiML that greets customer and starts speech gathering.
    """
    inbound = VoiceInbound(**payload)
    bind_request_context(channel="voice")

    logger.info(
        "voice_call_received",
        call_sid=inbound.CallSid,
        from_number=inbound.caller_number,
    )

    # Find business profile
    db = get_admin_db()
    profile = await db.get_by_field(
        "business_profiles",
        "phone_number",
        inbound.called_number,
    )
    if not profile:
        logger.warning(
            "voice_no_business_profile",
            called=inbound.called_number,
        )
        raise BusinessProfileNotFoundException(
            f"No profile for {inbound.called_number}",
            channel="voice",
        )

    if not profile.get("bot_active", True):
        raise BotInactiveException(
            "Bot paused", user_id=profile["user_id"], channel="voice"
        )

    business_name = profile.get("business_name", "our business")
    bot_language = profile.get("bot_language", "english")

    # Map language to Twilio language code
    lang_map = {
        "english": "en-IN",
        "hindi": "hi-IN",
        "telugu": "te-IN",
    }
    lang_code = lang_map.get(bot_language, "en-IN")

    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"{settings.public_base_url}/webhook/voice/gather",
        method="POST",
        language=lang_code,
        speech_timeout="auto",
        action_on_empty_result=True,
    )
    gather.say(
        f"Hello! Thank you for calling {business_name}. "
        f"How can I help you today?",
        language=lang_code,
    )
    response.append(gather)
    response.say(
        "I didn't catch that. Please call back and try again.",
        language=lang_code,
    )

    return str(response)


async def handle_voice_gather(
    payload: dict[str, Any],
) -> str:
    """
    Handles speech input after Gather TwiML.
    Processes spoken text through AI brain and responds via TTS.
    """
    gather = VoiceGather(**payload)
    bind_request_context(channel="voice")

    logger.info(
        "voice_gather_received",
        call_sid=gather.CallSid,
        confidence=gather.confidence_score,
        has_speech=bool(gather.spoken_text),
    )

    db = get_admin_db()
    profile = await db.get_by_field(
        "business_profiles",
        "phone_number",
        gather.To,
    )
    if not profile:
        return _fallback_twiml("Our team will get back to you shortly.")

    bot_language = profile.get("bot_language", "english")
    lang_map = {"english": "en-IN", "hindi": "hi-IN", "telugu": "te-IN"}
    lang_code = lang_map.get(bot_language, "en-IN")

    spoken = gather.spoken_text
    if not spoken:
        response = VoiceResponse()
        response.say(
            "I didn't catch what you said. "
            "Please try again or call back later.",
            language=lang_code,
        )
        return str(response)

    # Low confidence speech — ask to repeat
    if gather.confidence_score < 0.5:
        logger.warning(
            "voice_low_confidence_speech",
            confidence=gather.confidence_score,
        )
        response = VoiceResponse()
        gather_again = Gather(
            input="speech",
            action=f"{settings.public_base_url}/webhook/voice/gather",
            method="POST",
            language=lang_code,
            speech_timeout="auto",
        )
        gather_again.say(
            "Sorry, I couldn't understand clearly. "
            "Could you please repeat that?",
            language=lang_code,
        )
        response.append(gather_again)
        return str(response)

    # Process via AI brain
    result = await process_message(
        user_id=profile["user_id"],
        channel="voice",
        from_contact=gather.caller_number,
        message=spoken,
        business_profile=profile,
    )

    # Clean reply for voice output
    reply = result["reply"]

    # Remove markdown + footer for voice
    reply = reply.split("_(")[0]
    reply = reply.replace("*", "")
    reply = reply.replace("_", "")
    reply = reply.replace("\n", " ").strip()

    # Limit voice length
    if len(reply) > 250:
        reply = reply[:250]

    response = VoiceResponse()

    if result["escalated"]:
        response.say(reply, language=lang_code)
        response.hangup()
    else:
        # Continue conversation with clean structure
        next_gather = Gather(
            input="speech",
            action=f"{settings.public_base_url}/webhook/voice/gather",
            method="POST",
            language=lang_code,
            speech_timeout="auto",
            action_on_empty_result=True,
        )
        next_gather.say(reply, language=lang_code)
        response.append(next_gather)

    logger.info(
        "voice_reply_sent",
        call_sid=gather.CallSid,
        escalated=result["escalated"],
        latency_ms=result["total_latency_ms"],
    )

    return str(response)


def _fallback_twiml(message: str) -> str:
    response = VoiceResponse()
    response.say(message)
    response.hangup()
    return str(response)