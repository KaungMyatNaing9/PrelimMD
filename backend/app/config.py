# app/config.py
# Typed application settings loaded from environment / .env file.

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    max_file_size_mb: int = 25

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
