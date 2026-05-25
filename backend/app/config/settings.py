from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralised configuration loaded from environment variables.
    Every field is typed. Missing required fields → app refuses to start.
    Validated on import — fail fast, never at 3AM on first request.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────
    app_name: str = "AutoReply AI"
    app_env: Literal["development", "production", "test"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str

    # ── Groq (LLM) ────────────────────────────────────────────────────────
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.1
    groq_max_tokens: int = 1024
    groq_timeout_seconds: int = 30

    # ── Supabase ──────────────────────────────────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # ── Twilio ────────────────────────────────────────────────────────────
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    twilio_whatsapp_sandbox: str = "+14155238886"

    # ── SendGrid ──────────────────────────────────────────────────────────
    sendgrid_api_key: str
    sendgrid_from_email: str

    # ── ChromaDB ──────────────────────────────────────────────────────────
    chroma_persist_directory: str = "./chroma_db"
    chroma_collection_name: str = "knowledge_base"

    # ── Embeddings ────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_chunk_size: int = 512
    embedding_chunk_overlap: int = 50
    rag_similarity_threshold: float = 0.7
    rag_top_k: int = 3

    # ── Agent ─────────────────────────────────────────────────────────────
    agent_max_retries: int = 3
    agent_max_iterations: int = 10
    escalation_confidence_threshold: float = 0.6

    # ── File Upload ───────────────────────────────────────────────────────
    max_upload_size_mb: int = 10

    # ── CORS ──────────────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # ── Pagination ────────────────────────────────────────────────────────
    default_page_size: int = 20
    max_page_size: int = 100

    # ── Development ───────────────────────────────────────────────────────
    ngrok_url: str = ""

    # ─────────────────────────────────────────────────────────────────────
    # Validators
    # ─────────────────────────────────────────────────────────────────────

    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_api_key(cls, v: str) -> str:
        if not v or not v.startswith("gsk_"):
            raise ValueError(
                "GROQ_API_KEY is missing or invalid. "
                "Get your free key at console.groq.com"
            )
        return v

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        if not v or not v.startswith("https://"):
            raise ValueError(
                "SUPABASE_URL is missing or invalid. "
                "Must start with https://"
            )
        return v.rstrip("/")

    @field_validator("supabase_anon_key", "supabase_service_key")
    @classmethod
    def validate_supabase_keys(cls, v: str) -> str:
        if not v or not v.startswith("eyJ"):
            raise ValueError(
                "Supabase key is missing or invalid. "
                "Keys must start with eyJ"
            )
        return v

    @field_validator("twilio_account_sid")
    @classmethod
    def validate_twilio_sid(cls, v: str) -> str:
        if not v or not v.startswith("AC"):
            raise ValueError(
                "TWILIO_ACCOUNT_SID is missing or invalid. "
                "Must start with AC"
            )
        return v

    @field_validator("sendgrid_api_key")
    @classmethod
    def validate_sendgrid_key(cls, v: str) -> str:
        if not v or not v.startswith("SG."):
            raise ValueError(
                "SENDGRID_API_KEY is missing or invalid. "
                "Must start with SG."
            )
        return v

    @field_validator("sendgrid_from_email")
    @classmethod
    def validate_from_email(cls, v: str) -> str:
        if not v or "@" not in v:
            raise ValueError(
                "SENDGRID_FROM_EMAIL is missing or invalid."
            )
        return v.lower()

    @field_validator("groq_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(
                "groq_temperature must be between 0.0 and 1.0"
            )
        if v > 0.3:
            import warnings
            warnings.warn(
                f"groq_temperature={v} is above 0.3. "
                "Agentic systems should use 0.0-0.1 for determinism.",
                stacklevel=2,
            )
        return v

    @field_validator("max_upload_size_mb")
    @classmethod
    def validate_upload_size(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError(
                "MAX_UPLOAD_SIZE_MB must be between 1 and 50"
            )
        return v

    @model_validator(mode="after")
    def validate_whatsapp_sandbox(self) -> "Settings":
        if not self.twilio_whatsapp_sandbox.startswith("+"):
            raise ValueError(
                "TWILIO_WHATSAPP_SANDBOX must start with + "
                "(e.g. +14155238886)"
            )
        return self

    # ─────────────────────────────────────────────────────────────────────
    # Computed properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def whatsapp_from_number(self) -> str:
        """Twilio WhatsApp requires 'whatsapp:+1XXXXXXXXXX' format."""
        number = self.twilio_whatsapp_sandbox
        if not number.startswith("whatsapp:"):
            return f"whatsapp:{number}"
        return number

    @property
    def log_level(self) -> str:
        return "DEBUG" if self.is_development else "INFO"

    @property
    def cors_origins(self) -> list[str]:
        """
        Builds CORS origins list.
        Always includes frontend_url — critical for deployed app.
        In dev, ngrok_url is also added if set.
        """
        origins = set(self.allowed_origins)
        origins.add(self.frontend_url)
        if self.ngrok_url:
            origins.add(self.ngrok_url)
        return list(origins)

    @property
    def max_upload_size_bytes(self) -> int:
        """Upload size limit in bytes for file validation."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def public_base_url(self) -> str:
        """
        The public-facing URL of the backend.
        Used for webhook URL construction.
        In dev: ngrok_url if set, else localhost.
        In prod: set via FRONTEND_URL equivalent for backend.
        """
        if self.ngrok_url:
            return self.ngrok_url.rstrip("/")
        return f"http://{self.app_host}:{self.app_port}"


# ─────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the singleton Settings instance.
    Cached after first call — .env read exactly once.

    Usage:
        from app.config.settings import get_settings
        settings = get_settings()
    """
    try:
        return Settings()
    except Exception as e:
        print(f"\n❌ STARTUP FAILED — Configuration Error:\n{e}\n")
        print("Fix your .env file and restart.\n")
        sys.exit(1)


# Trigger validation immediately on import
_settings = get_settings()