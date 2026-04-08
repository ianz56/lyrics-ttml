from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    DATABASE_URL: str = "postgresql+asyncpg://lyrics:lyrics@localhost:5432/lyrics_ttml"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://lyrics:lyrics@localhost:5432/lyrics_ttml"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
