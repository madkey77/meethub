"""BackfillJob model for bulk processing operations."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class BackfillStatus(str, PyEnum):
    """Backfill job status enumeration."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BackfillJob(Base):
    """BackfillJob entity for tracking bulk reprocessing operations."""

    __tablename__ = "backfill_jobs"

    # Primary key
    backfill_job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Target specification
    target_folder_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Folder path for bulk processing",
    )
    target_file_list: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of specific file IDs to process",
    )

    # Progress tracking
    total_file_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    processed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Status
    status: Mapped[BackfillStatus] = mapped_column(
        Enum(BackfillStatus),
        nullable=False,
        default=BackfillStatus.QUEUED,
    )

    # Progress percentage (0.0-100.0)
    progress_percentage: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Results summary
    summary_report: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Success/failure breakdown, artifacts created, cost estimates",
    )

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    resumed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    job_runs: Mapped[list["JobRun"]] = relationship(
        "JobRun",
        foreign_keys="JobRun.backfill_job_id",
        back_populates="backfill_job",
        cascade="all, delete-orphan",
    )

    # Indexes and constraints
    __table_args__ = (
        CheckConstraint("total_file_count >= 0", name="total_count_non_negative"),
        CheckConstraint("processed_count >= 0", name="processed_count_non_negative"),
        CheckConstraint("failed_count >= 0", name="failed_count_non_negative"),
        CheckConstraint(
            "progress_percentage IS NULL OR (progress_percentage >= 0.0 AND progress_percentage <= 100.0)",
            name="valid_progress"
        ),
        Index("idx_backfill_status", "status"),
        Index("idx_backfill_started", "started_at"),
    )

    def __repr__(self) -> str:
        """String representation of BackfillJob."""
        return f"<BackfillJob(id={self.backfill_job_id}, status={self.status}, progress={self.progress_percentage}%)>"
