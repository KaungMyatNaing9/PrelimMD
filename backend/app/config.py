# app/config.py
# Typed application settings loaded from environment / .env file.

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://prelimmd:prelimmd@localhost:5432/prelimmd"

    # ── AI ──────────────────────────────────────────────────────────────────────
    openai_api_key: str = ""

    # ── Voice / STT ─────────────────────────────────────────────────────────────
    deepgram_api_key: str = ""

    # ── Voice / TTS ─────────────────────────────────────────────────────────────
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # default: Rachel
    public_base_url: str = ""
    backend_public_url: str = ""

    # ── Twilio ─────────────────────────────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # ── CORS ────────────────────────────────────────────────────────────────────
    # Comma-separated origins allowed to call the API.
    # Example in .env: ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
    allowed_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:3001,"
        "http://127.0.0.1:3001"
    )

    # ── App ─────────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "info"
    max_file_size_mb: int = 25

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origins(self) -> List[str]:
        """Return ALLOWED_ORIGINS as a clean list of strings."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def resolved_public_base_url(self) -> str:
        return (self.public_base_url or self.backend_public_url).rstrip("/")


settings = Settings()
