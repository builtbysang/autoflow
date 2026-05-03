from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, Column, JSON


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Request(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str
    params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "queued"
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    finished_at: Optional[datetime] = None


class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str  # image | video | thumbnail
    uuid_media_id: Optional[str] = Field(default=None, index=True, unique=True)
    url: Optional[str] = None
    local_path: Optional[str] = None
    mime: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
