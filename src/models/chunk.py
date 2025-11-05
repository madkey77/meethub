"""Chunk model for text segmentation in RAG system."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class Chunk(Base):
    """Chunk entity representing a text segment for RAG retrieval."""

    __tablename__ = "chunks"

    # Primary key
    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    file_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("file_versions.version_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Chunk metadata
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential index within the file version",
    )
    text_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The actual text content of this chunk",
    )

    # Position tracking
    char_offset_start: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Character offset start in original document",
    )
    char_offset_end: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Character offset end in original document",
    )

    # Metadata (JSON for flexibility)
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Additional metadata (speaker, timestamp, page number, etc.)",
    )

    # Soft delete
    deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Soft delete flag for audit trail",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    file_version: Mapped["FileVersion"] = relationship(
        "FileVersion",
        back_populates="chunks",
    )
    embedding: Mapped["Embedding | None"] = relationship(
        "Embedding",
        back_populates="chunk",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Indexes and constraints
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
        CheckConstraint("char_offset_start >= 0", name="char_offset_start_non_negative"),
        CheckConstraint("char_offset_end > char_offset_start", name="valid_offsets"),
        Index("idx_chunk_file_version", "file_version_id"),
        Index("idx_chunk_index", "file_version_id", "chunk_index"),
        Index("idx_chunk_deleted", "deleted"),
    )

    def __repr__(self) -> str:
        """String representation of Chunk."""
        preview = self.text_content[:50] + "..." if len(self.text_content) > 50 else self.text_content
        return f"<Chunk(id={self.chunk_id}, index={self.chunk_index}, preview='{preview}')>"
