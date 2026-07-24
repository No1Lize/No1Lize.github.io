from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str | None = None
    public_origins: list[str] = Field(
        default=["https://no1lize.github.io", "http://localhost:3000"]
    )
    internal_sync_secret: str | None = None
    sec_user_agent: str = "LizeRoadOne research@example.com"
    github_token: str | None = None
    github_repository: str = "No1Lize/No1Lize.github.io"
    snapshot_path: str = "data/public/dashboard.json"
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
