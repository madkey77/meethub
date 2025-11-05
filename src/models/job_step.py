"""JobStep model for detailed job execution tracking."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class JobStepStatus(str, PyEnum):
    """Job step execution status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class JobStep(Base):
    """JobStep entity representing individual steps within a job execution."""

    __tablename__ = "job_steps"

    # Primary key
    step_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    job_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_runs.job_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Step metadata
    step_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Step identifier (normalize, chunk, embed, generate_{artifact_kind})",
    )
    status: Mapped[JobStepStatus] = mapped_column(
        Enum(JobStepStatus),
        nullable=False,
        default=JobStepStatus.PENDING,
    )

    # Execution details
    log_output: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured log output with key execution details",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if step failed",
    )
    error_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Error type/class name for categorization",
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
    job_run: Mapped["JobRun"] = relationship(
        "JobRun",
        back_populates="job_steps",
    )

    # Indexes
    __table_args__ = (
        Index("idx_job_step_job_run", "job_run_id"),
        Index("idx_job_step_status", "status"),
        Index("idx_job_step_name", "step_name"),
    )

    def __repr__(self) -> str:
        """String representation of JobStep."""
        return f"<JobStep(id={self.step_id}, name={self.step_name}, status={self.status})>"
