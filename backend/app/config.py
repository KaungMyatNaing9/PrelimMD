# app/config.py
# Typed application settings loaded from environment / .env file.

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "9BWtsMINqrJLrRacOk9x"  # Aria — warm, expressive
    max_file_size_mb: int = 25

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
