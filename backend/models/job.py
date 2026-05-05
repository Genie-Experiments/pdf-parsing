import uuid
from datetime import datetime, timezone  # timezone needed for UTC-naive conversion
from enum import Enum
from typing import List, Optional

from sqlalchemy import JSON, Column, event
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class Job(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_email: str = Field(index=True)
    filename: str
    page: Optional[int] = None  # None = full PDF; N = single page (1-indexed)

    # ── per-request pipeline options ─────────────────────────────────────────
    # Stored on the job so the worker uses exactly what the caller requested.
    # None means "use the pipeline default" (["code","fig","tab"] / False).
    segments_to_refine: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    process_code_using_llm: bool = Field(default=False)
    process_figures_using_llm: bool = Field(default=False)

    status: JobStatus = Field(default=JobStatus.queued)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Storage keys (set after pipeline completes)
    pdf_key: Optional[str] = None  # MinIO object key for original PDF
    markdown_key: Optional[str] = None  # MinIO object key for output markdown
    segments_key: Optional[str] = None  # MinIO object key for Dolphin JSON (bbox data)

    error_message: Optional[str] = None


@event.listens_for(Job, "before_update")
def _refresh_updated_at(mapper, connection, target: Job) -> None:  # noqa: ARG001
    """Automatically stamp updated_at on every ORM update."""
    target.updated_at = _now()


class JobRead(SQLModel):
    id: uuid.UUID
    user_email: str
    filename: str
    page: Optional[int] = None
    segments_to_refine: Optional[List[str]] = None
    process_code_using_llm: bool = False
    process_figures_using_llm: bool = False
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    current_step: int = 0
