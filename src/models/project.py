"""Project model for meeting classification categories."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class Project(Base):
    """Project entity for meeting classification and organization."""

    __tablename__ = "projects"

    # Primary key
    project_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Project information
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    drive_folder_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Classification rules (JSON array)
    classification_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)

    # Default project flag (exactly one must be true)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # NEW: RAG-specific fields
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Human-readable project name for UI display",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Project description",
    )
    ingestion_folder_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Local filesystem path for document ingestion",
    )
    artifact_retention_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Retention policy for artifacts (null = indefinite)",
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Custom metadata (team, client, domain tags)",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    files: Mapped[list["File"]] = relationship(
        "File",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_project_is_default", "is_default"),
        Index("idx_project_ingestion_folder", "ingestion_folder_path"),
    )

    def __repr__(self) -> str:
        """String representation of Project."""
        return f"<Project(id={self.project_id}, name='{self.name}', default={self.is_default})>"
