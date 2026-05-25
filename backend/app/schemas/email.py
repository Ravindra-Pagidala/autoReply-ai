from __future__ import annotations

from pydantic import field_validator

from app.schemas.base import AutoReplyBaseModel


class EmailInbound(AutoReplyBaseModel):
    """
    Shape of SendGrid Inbound Parse webhook payload.
    Fired when email arrives at your SendGrid inbound address.
    """

    # Sender info
    to: str
    from_email: str = ""
    subject: str = ""
    text: str = ""
    html: str = ""

    # Headers
    headers: str | None = None
    dkim: str | None = None
    SPF: str | None = None

    # Attachments
    attachments: str = "0"

    # Envelope (JSON string from SendGrid)
    envelope: str | None = None

    # Spam scores
    spam_score: str | None = None
    spam_report: str | None = None

    @field_validator("text", "html")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """
        Sanitize email content:
        - Limit to 2000 chars (emails can be long)
        - Remove null bytes
        """
        v = v.strip().replace("\x00", "")
        if len(v) > 2000:
            v = v[:2000]
        return v

    @field_validator("subject")
    @classmethod
    def sanitize_subject(cls, v: str) -> str:
        v = v.strip().replace("\x00", "")
        if len(v) > 200:
            v = v[:200]
        return v

    @property
    def body(self) -> str:
        """
        Returns clean text body.
        Prefers plain text over HTML.
        If only HTML available, returns stripped version.
        """
        if self.text:
            return self.text
        # Strip basic HTML tags for plain text fallback
        import re
        clean = re.sub(r"<[^>]+>", " ", self.html)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    @property
    def sender_email(self) -> str:
        """
        Extracts clean email from 'Name <email@domain.com>' format.
        """
        raw = self.from_email.strip()
        if "<" in raw and ">" in raw:
            start = raw.index("<") + 1
            end = raw.index(">")
            return raw[start:end].strip().lower()
        return raw.lower()

    @property
    def sender_name(self) -> str | None:
        """
        Extracts name from 'Name <email@domain.com>' format.
        Returns None if no name present.
        """
        raw = self.from_email.strip()
        if "<" in raw:
            name = raw[:raw.index("<")].strip()
            return name if name else None
        return None

    @property
    def is_spam(self) -> bool:
        """Basic spam detection using SendGrid score."""
        try:
            score = float(self.spam_score or "0")
            return score > 5.0
        except ValueError:
            return False


class EmailOutbound(AutoReplyBaseModel):
    """
    Shape of email we send back to customer.
    Used for logging.
    """

    to_email: str
    from_email: str
    subject: str
    body: str
    message_id: str | None = None
    status: str = "sent"