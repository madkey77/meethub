"""ProcessingJob model for tracking meeting processing attempts and retries."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class JobStatus(str, PyEnum):
    """Processing job status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJob(Base):
    """ProcessingJob entity for tracking transcription work and retry attempts."""

    __tablename__ = "processing_jobs"

    # Primary key
    job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to meeting
    meeting_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("meetings.meeting_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Job status
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus),
        nullable=False,
        default=JobStatus.PENDING,
    )

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Error information
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationship
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="processing_jobs")

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint("retry_count >= 0", name="retry_count_non_negative"),
        CheckConstraint("retry_count <= 3", name="retry_count_max_3"),
        Index("idx_job_status", "status"),
        Index("idx_job_next_retry", "next_retry_at"),
        Index("idx_job_meeting", "meeting_id"),
    )

    def __repr__(self) -> str:
        """String representation of ProcessingJob."""
        return f"<ProcessingJob(id={self.job_id}, meeting_id={self.meeting_id}, status={self.status}, retries={self.retry_count})>"
