"""FileVersion model for tracking file content versions."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class FileVersion(Base):
    """FileVersion entity representing a specific version of a file's content."""

    __tablename__ = "file_versions"

    # Primary key
    version_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    file_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("files.file_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Version metadata
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of file content for change detection",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes",
    )
    content_locator: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Path or URI to access file content",
    )

    # Version tracking
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is the current active version",
    )

    # Timestamps
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When this version was first discovered/created",
    )

    # Relationships
    file: Mapped["File"] = relationship(
        "File",
        back_populates="versions",
        foreign_keys=[file_id],
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="file_version",
        cascade="all, delete-orphan",
    )
    artifact_links: Mapped[list["ArtifactLink"]] = relationship(
        "ArtifactLink",
        back_populates="file_version",
        cascade="all, delete-orphan",
    )
    job_runs: Mapped[list["JobRun"]] = relationship(
        "JobRun",
        foreign_keys="JobRun.input_file_version_id",
        back_populates="input_file_version",
    )

    # Indexes
    __table_args__ = (
        CheckConstraint("file_size_bytes > 0", name="file_size_positive"),
        Index("idx_file_version_file", "file_id"),
        Index("idx_file_version_hash", "content_hash"),
        Index("idx_file_version_is_current", "is_current", "file_id"),
    )

    def __repr__(self) -> str:
        """String representation of FileVersion."""
        return f"<FileVersion(id={self.version_id}, file_id={self.file_id}, hash={self.content_hash[:8]})>"
