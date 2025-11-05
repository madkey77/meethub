"""JobRun model for RAG pipeline execution tracking."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class JobRunStatus(str, PyEnum):
    """Job execution status enumeration."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class JobRun(Base):
    """JobRun entity representing a RAG pipeline execution."""

    __tablename__ = "job_runs"

    # Primary key
    job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Job metadata
    pipeline_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Rule name that triggered this job",
    )
    status: Mapped[JobRunStatus] = mapped_column(
        Enum(JobRunStatus),
        nullable=False,
        default=JobRunStatus.QUEUED,
    )

    # Foreign keys
    input_file_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("file_versions.version_id", ondelete="SET NULL"),
        nullable=True,
        comment="Source file version (null for backfill aggregates)",
    )
    backfill_job_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("backfill_jobs.backfill_job_id", ondelete="CASCADE"),
        nullable=True,
        comment="Parent backfill job if part of batch",
    )

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )

    # Metrics (JSON for flexibility)
    metrics: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Job metrics (chunks_created, embeddings_generated, artifacts_produced, llm_tokens, cost)",
    )

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(
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
    job_steps: Mapped[list["JobStep"]] = relationship(
        "JobStep",
        back_populates="job_run",
        cascade="all, delete-orphan",
        order_by="JobStep.created_at",
    )
    input_file_version: Mapped["FileVersion | None"] = relationship(
        "FileVersion",
        foreign_keys=[input_file_version_id],
        back_populates="job_runs",
    )
    backfill_job: Mapped["BackfillJob | None"] = relationship(
        "BackfillJob",
        foreign_keys=[backfill_job_id],
        back_populates="job_runs",
    )
    artifact_versions: Mapped[list["ArtifactVersion"]] = relationship(
        "ArtifactVersion",
        back_populates="job_run",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        CheckConstraint("retry_count >= 0", name="retry_count_non_negative"),
        Index("idx_job_run_status", "status"),
        Index("idx_job_run_file_version", "input_file_version_id"),
        Index("idx_job_run_backfill", "backfill_job_id"),
        Index("idx_job_run_pipeline", "pipeline_name"),
        Index("idx_job_run_started", "started_at"),
    )

    def __repr__(self) -> str:
        """String representation of JobRun."""
        return f"<JobRun(id={self.job_id}, pipeline={self.pipeline_name}, status={self.status})>"
