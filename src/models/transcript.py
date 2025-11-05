"""Transcript model for storing transcription results."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class Transcript(Base):
    """Transcript entity for audio transcription results."""

    __tablename__ = "transcripts"

    # Primary key
    transcript_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to meeting
    meeting_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("meetings.meeting_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Transcription content
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Transcription metadata
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speaker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Google Drive storage
    drive_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_folder_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # NEW: RAG Integration
    deepgram_response: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Raw Deepgram API response with utterances and speaker metadata",
    )
    chunk_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of chunks created from this transcript",
    )
    embedding_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Timestamp when embeddings were generated",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationship
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="transcript")

    # Constraints
    __table_args__ = (
        CheckConstraint("word_count >= 0", name="word_count_non_negative"),
        CheckConstraint("speaker_count >= 0", name="speaker_count_non_negative"),
        Index("idx_transcript_embedding_generated", "embedding_generated_at"),
    )

    def __repr__(self) -> str:
        """String representation of Transcript."""
        return f"<Transcript(id={self.transcript_id}, meeting_id={self.meeting_id}, words={self.word_count})>"
