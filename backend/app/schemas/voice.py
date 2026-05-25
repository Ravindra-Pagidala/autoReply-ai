from __future__ import annotations

from pydantic import field_validator

from app.schemas.base import AutoReplyBaseModel


class VoiceInbound(AutoReplyBaseModel):
    """
    Shape of Twilio Voice webhook on inbound call.
    Fired when customer calls your Twilio number.
    """

    CallSid: str
    AccountSid: str
    From: str
    To: str
    CallStatus: str
    Direction: str = "inbound"
    CallerName: str | None = None

    @property
    def caller_number(self) -> str:
        return self.From.strip()

    @property
    def called_number(self) -> str:
        return self.To.strip()

    @property
    def call_id(self) -> str:
        """Idempotency key for voice calls."""
        return self.CallSid


class VoiceGather(AutoReplyBaseModel):
    """
    Shape of Twilio webhook after customer speaks.
    Fired after <Gather> TwiML collects speech.
    """

    CallSid: str
    AccountSid: str
    From: str
    To: str
    CallStatus: str

    # Speech recognition result
    SpeechResult: str | None = None
    Confidence: str | None = None

    # Digits if customer pressed keypad
    Digits: str | None = None

    @field_validator("SpeechResult")
    @classmethod
    def sanitize_speech(cls, v: str | None) -> str | None:
        """Sanitize speech input before sending to LLM."""
        if v is None:
            return None
        v = v.strip().replace("\x00", "")
        if len(v) > 1000:
            v = v[:1000]
        return v

    @property
    def spoken_text(self) -> str:
        """What the customer said. Empty string if nothing captured."""
        return self.SpeechResult or ""

    @property
    def confidence_score(self) -> float:
        """Speech recognition confidence 0.0 - 1.0."""
        try:
            return float(self.Confidence or "0.0")
        except ValueError:
            return 0.0

    @property
    def caller_number(self) -> str:
        return self.From.strip()


class VoiceStatusCallback(AutoReplyBaseModel):
    """
    Shape of Twilio call status callback.
    Fired when call ends — used to log final call status.
    """

    CallSid: str
    CallStatus: str
    CallDuration: str | None = None
    From: str
    To: str

    @property
    def duration_seconds(self) -> int:
        try:
            return int(self.CallDuration or "0")
        except ValueError:
            return 0