"""ArtifactLink model for tracking artifact-file relationships."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class LinkRoleType(str, PyEnum):
    """Role type for artifact-file links."""

    SOURCE = "source"  # File was primary input for artifact
    DERIVED = "derived"  # Artifact was derived from this file but not primary
    REFERENCE = "reference"  # File is cited or referenced but not directly used


class ArtifactLink(Base):
    """ArtifactLink entity connecting artifacts to source files."""

    __tablename__ = "artifact_links"

    # Primary key
    link_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    artifact_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("artifact_versions.version_id", ondelete="CASCADE"),
        nullable=False,
    )
    file_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("file_versions.version_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Link metadata
    role_type: Mapped[LinkRoleType] = mapped_column(
        Enum(LinkRoleType),
        nullable=False,
        default=LinkRoleType.SOURCE,
        comment="Relationship type between artifact and file",
    )
    contribution_weight: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Weight of this file's contribution to the artifact (0.0-1.0)",
    )
    link_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional link metadata (chunks used, relevance scores, etc.)",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    artifact_version: Mapped["ArtifactVersion"] = relationship(
        "ArtifactVersion",
        back_populates="artifact_links",
    )
    file_version: Mapped["FileVersion"] = relationship(
        "FileVersion",
        back_populates="artifact_links",
    )

    # Indexes and constraints
    __table_args__ = (
        CheckConstraint(
            "contribution_weight IS NULL OR (contribution_weight >= 0.0 AND contribution_weight <= 1.0)",
            name="valid_weight"
        ),
        Index("idx_artifact_link_artifact", "artifact_version_id"),
        Index("idx_artifact_link_file", "file_version_id"),
        Index("idx_artifact_link_role", "role_type"),
        Index("idx_artifact_link_unique", "artifact_version_id", "file_version_id", unique=True),
    )

    def __repr__(self) -> str:
        """String representation of ArtifactLink."""
        return f"<ArtifactLink(id={self.link_id}, artifact={self.artifact_version_id}, file={self.file_version_id})>"
