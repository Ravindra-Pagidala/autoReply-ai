from __future__ import annotations

from pydantic import field_validator

from app.schemas.base import AutoReplyBaseModel


class WhatsAppInbound(AutoReplyBaseModel):
    """
    Exact shape of Twilio WhatsApp webhook payload.
    Every field matches Twilio's documentation exactly.
    """

    # Message identifiers
    MessageSid: str
    SmsSid: str | None = None
    AccountSid: str

    # Message content
    Body: str = ""
    NumMedia: str = "0"

    # From/To
    From: str
    To: str
    WaId: str | None = None

    # Profile info Twilio sometimes sends
    ProfileName: str | None = None

    # Location (if customer sends location)
    Latitude: str | None = None
    Longitude: str | None = None
    Address: str | None = None

    @field_validator("From", "To")
    @classmethod
    def validate_whatsapp_number(cls, v: str) -> str:
        """
        Twilio sends WhatsApp numbers as 'whatsapp:+1XXXXXXXXXX'.
        Strip the prefix for storage, keep raw for sending.
        """
        return v.strip()

    @field_validator("Body")
    @classmethod
    def sanitize_body(cls, v: str) -> str:
        """
        Sanitize message body:
        - Strip leading/trailing whitespace
        - Limit to 1000 chars (prevent prompt injection flooding)
        - Remove null bytes
        """
        v = v.strip().replace("\x00", "")
        if len(v) > 1000:
            v = v[:1000]
        return v

    @property
    def from_number(self) -> str:
        """Clean phone number without whatsapp: prefix."""
        return self.From.replace("whatsapp:", "")

    @property
    def to_number(self) -> str:
        """Clean to number without whatsapp: prefix."""
        return self.To.replace("whatsapp:", "")

    @property
    def has_media(self) -> bool:
        """True if message contains media (image, document etc.)"""
        return int(self.NumMedia) > 0

    @property
    def message_id(self) -> str:
        """Idempotency key — use MessageSid to detect duplicates."""
        return self.MessageSid


class WhatsAppOutbound(AutoReplyBaseModel):
    """
    Shape of WhatsApp message we send back to customer.
    Used for logging and audit trail.
    """

    to: str
    body: str
    from_number: str
    message_sid: str | None = None
    status: str = "sent"