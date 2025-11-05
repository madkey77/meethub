"""Meeting model for storing Google Meet session metadata."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class MeetingStatus(str, PyEnum):
    """Meeting processing status values."""

    DETECTED = "detected"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RAGIngestionStatus(str, PyEnum):
    """RAG ingestion status for meetings."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Meeting(Base):
    """Meeting entity representing a Google Meet session."""

    __tablename__ = "meetings"

    # Primary key
    meeting_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Meeting metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Recording information
    recording_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    recording_drive_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Processing status
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus),
        nullable=False,
        default=MeetingStatus.DETECTED,
    )

    # Classification
    project_name: Mapped[str] = mapped_column(String(100), nullable=False, default="GERAL")

    # NEW: RAG Integration
    file_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("files.file_id", ondelete="SET NULL"),
        nullable=True,
        comment="Link to File entity for RAG processing",
    )
    rag_ingestion_status: Mapped[RAGIngestionStatus | None] = mapped_column(
        Enum(RAGIngestionStatus),
        nullable=True,
        comment="Status of RAG ingestion for this meeting",
    )

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

    # Relationships
    participants: Mapped[list["Participant"]] = relationship(
        "Participant",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    transcript: Mapped["Transcript | None"] = relationship(
        "Transcript",
        back_populates="meeting",
        uselist=False,
        cascade="all, delete-orphan",
    )
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(
        "ProcessingJob",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    file: Mapped["File | None"] = relationship(
        "File",
        foreign_keys=[file_id],
        back_populates="source_meetings",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("duration_minutes <= 180", name="duration_max_3_hours"),
        Index("idx_meeting_status", "status"),
        Index("idx_meeting_end_time", "end_time"),
        Index("idx_meeting_project", "project_name"),
        Index("idx_meeting_file_id", "file_id"),
        Index("idx_meeting_rag_status", "rag_ingestion_status"),
    )

    def __repr__(self) -> str:
        """String representation of Meeting."""
        return f"<Meeting(id={self.meeting_id}, title='{self.title}', status={self.status})>"
