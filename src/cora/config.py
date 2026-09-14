from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    model_name: str = "claude-haiku-4-5-20251001"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_url: str = "http://localhost:8000"

    admin_api_key: str = "dev-admin-key"
    session_secret: str = "dev-session-secret-change-me"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "cora"
    postgres_user: str = "cora"
    postgres_password: str = "cora"

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "cora"

    @property
    def database_url(self) -> str:
        # Render (and most PaaS Postgres add-ons) hand you a single
        # DATABASE_URL rather than discrete host/user/password vars -- prefer
        # that when set, same as bootstrap/seed.py's own get_database_url().
        return os.environ.get("DATABASE_URL") or (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    # LangChain/LangGraph pick tracing up from the process environment (via the
    # `langsmith` SDK), not from this Settings object -- mirror the relevant
    # fields into os.environ so `.env`-configured tracing actually takes effect.
    # setdefault so a real env var the user already exported always wins.
    os.environ.setdefault("LANGSMITH_TRACING", "true" if settings.langsmith_tracing else "false")
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    return settings
