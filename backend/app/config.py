# app/config.py
# Typed application settings loaded from environment / .env file.

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    deepgram_api_key: str = ""
    max_file_size_mb: int = 25  # maximum audio upload size in megabytes

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
