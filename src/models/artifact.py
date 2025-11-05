"""Artifact models for LLM-generated content."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class Artifact(Base):
    """Artifact entity representing a type of generated content."""

    __tablename__ = "artifacts"

    # Primary key
    artifact_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Artifact metadata
    artifact_key: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
        comment="Composite key: {kind}:{project}:{identifier} (e.g., 'summary:project-alpha:meeting-123')",
    )
    artifact_kind: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Artifact type (summary, decisions_index, entities_index, timeline, action_items, custom)",
    )

    # Foreign keys
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    current_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("artifact_versions.version_id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to latest ArtifactVersion",
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
    versions: Mapped[list["ArtifactVersion"]] = relationship(
        "ArtifactVersion",
        back_populates="artifact",
        foreign_keys="ArtifactVersion.artifact_id",
        cascade="all, delete-orphan",
    )
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="artifacts",
    )

    # Indexes
    __table_args__ = (
        Index("idx_artifact_kind", "artifact_kind"),
        Index("idx_artifact_project", "project_id"),
        Index("idx_artifact_current_version", "current_version_id"),
    )

    def __repr__(self) -> str:
        """String representation of Artifact."""
        return f"<Artifact(id={self.artifact_id}, kind={self.artifact_kind})>"


class ArtifactVersion(Base):
    """ArtifactVersion entity representing a specific version of generated content."""

    __tablename__ = "artifact_versions"

    # Primary key
    version_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    artifact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("artifacts.artifact_id", ondelete="CASCADE"),
        nullable=False,
    )
    job_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("job_runs.job_id", ondelete="SET NULL"),
        nullable=True,
        comment="Job that created this version",
    )

    # Content
    content_locator: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Storage location (file path or database reference)",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of content (for deduplication)",
    )

    # Generation metadata (JSON contains all details)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        comment="Generation metadata (schema_version, llm_provider, model, prompt_template, tokens, cost)",
    )

    # Version tracking
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    artifact: Mapped["Artifact"] = relationship(
        "Artifact",
        back_populates="versions",
        foreign_keys=[artifact_id],
    )
    job_run: Mapped["JobRun | None"] = relationship(
        "JobRun",
        foreign_keys=[job_run_id],
        back_populates="artifact_versions",
    )
    artifact_links: Mapped[list["ArtifactLink"]] = relationship(
        "ArtifactLink",
        back_populates="artifact_version",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_artifact_version_artifact", "artifact_id"),
        Index("idx_artifact_version_job_run", "job_run_id"),
        Index("idx_artifact_version_is_current", "is_current", "artifact_id"),
        Index("idx_artifact_version_hash", "content_hash"),
    )

    def __repr__(self) -> str:
        """String representation of ArtifactVersion."""
        metadata = self.metadata_json or {}
        provider = metadata.get("llm_provider", "unknown")
        return f"<ArtifactVersion(id={self.version_id}, artifact_id={self.artifact_id}, provider={provider})>"
