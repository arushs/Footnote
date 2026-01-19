"""FailedTask model for Dead Letter Queue."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FailedTask(Base):
    """Stores Celery tasks that have exhausted all retries.

    This table serves as a Dead Letter Queue (DLQ) for debugging and
    manual retry of failed background tasks. Tasks are captured with
    full context including arguments, exception details, and traceback.
    """

    __tablename__ = "failed_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    args: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    kwargs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exception_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    exception_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<FailedTask {self.task_name} ({self.task_id})>"

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None
