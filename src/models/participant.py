"""Participant model for meeting attendees."""

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class Participant(Base):
    """Participant entity for meeting attendees."""

    __tablename__ = "participants"

    # Primary key
    participant_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to meeting
    meeting_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("meetings.meeting_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Participant information
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown Participant")
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    speaker_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    attendance_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationship
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="participants")

    # Indexes
    __table_args__ = (
        Index("idx_participant_meeting", "meeting_id"),
        Index("idx_participant_email", "email"),
    )

    def __repr__(self) -> str:
        """String representation of Participant."""
        return f"<Participant(id={self.participant_id}, name='{self.name}', meeting_id={self.meeting_id})>"
