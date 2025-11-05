"""File model for RAG-enhanced document management."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class FileSourceType(str, PyEnum):
    """File source type enumeration."""

    MEETING = "meeting"
    UPLOADED_DOCUMENT = "uploaded_document"
    CHAT_EXPORT = "chat_export"


class File(Base):
    """File entity representing a document in the RAG system."""

    __tablename__ = "files"

    # Primary key
    file_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # File metadata
    relative_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Relative path from project root or identifier",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME type (e.g., application/pdf, text/markdown)",
    )
    source_type: Mapped[FileSourceType] = mapped_column(
        Enum(FileSourceType),
        nullable=False,
        comment="Source classification (meeting, uploaded_document, chat_export)",
    )

    # Foreign keys
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        comment="Project this file belongs to",
    )
    current_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("file_versions.version_id", ondelete="SET NULL"),
        nullable=True,
        comment="Current active version of this file",
    )

    # Soft delete
    deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Soft delete flag",
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
    versions: Mapped[list["FileVersion"]] = relationship(
        "FileVersion",
        back_populates="file",
        foreign_keys="FileVersion.file_id",
        cascade="all, delete-orphan",
    )
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="files",
    )
    source_meetings: Mapped[list["Meeting"]] = relationship(
        "Meeting",
        foreign_keys="Meeting.file_id",
        back_populates="file",
    )

    # Indexes
    __table_args__ = (
        Index("idx_file_project", "project_id"),
        Index("idx_file_relative_path", "relative_path"),
        Index("idx_file_source_type", "source_type"),
        Index("idx_file_deleted", "deleted"),
        Index("idx_file_current_version", "current_version_id"),
    )

    def __repr__(self) -> str:
        """String representation of File."""
        return f"<File(id={self.file_id}, path={self.relative_path}, source={self.source_type})>"
