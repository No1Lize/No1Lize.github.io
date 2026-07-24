from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Page(BaseModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int


class StatusResponse(BaseModel):
    status: str
    database: str
    snapshot_updated_at: str | None
    version: str = "1.0.0"


class SyncRequest(BaseModel):
    source: str | None = None
    force: bool = False


class SyncResult(BaseModel):
    status: str
    started_at: datetime
    scanned: int = Field(ge=0)
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    conflicts: int = Field(ge=0)
    errors: int = Field(ge=0)
