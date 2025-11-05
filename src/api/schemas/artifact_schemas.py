"""Pydantic schemas for artifact query and retrieval endpoints.

This module defines request/response schemas for:
- Artifact listing with filtering
- Artifact details with version history
- Artifact version content retrieval
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# Enums
# ==============================================================================

class ArtifactKindEnum(str, Enum):
    """Artifact type classification."""

    SUMMARY = "summary"
    DECISIONS_INDEX = "decisions_index"
    ENTITIES_INDEX = "entities_index"
    TIMELINE = "timeline"
    ACTION_ITEMS = "action_items"
    CUSTOM = "custom"


class LinkRoleTypeEnum(str, Enum):
    """Artifact-File relationship type."""

    SOURCE = "source"
    DERIVED = "derived"
    REFERENCE = "reference"


# ==============================================================================
# Response Schemas
# ==============================================================================

class ArtifactVersionSchema(BaseModel):
    """Artifact version information.

    Attributes:
        version_id: Unique version identifier
        artifact_id: Parent artifact ID
        job_run_id: Job that generated this version
        content_locator: Storage location
        content_hash: SHA-256 hash of content
        is_current: True if this is the current version
        metadata: Generation metadata (LLM provider, model, tokens, cost, etc.)
        created_at: Version creation timestamp
    """

    model_config = ConfigDict(from_attributes=True)

    version_id: int = Field(..., description="Version identifier")
    artifact_id: int = Field(..., description="Parent artifact ID")
    job_run_id: Optional[int] = Field(None, description="Job run ID")
    content_locator: str = Field(..., description="Storage path")
    content_hash: str = Field(..., description="SHA-256 hash")
    is_current: bool = Field(..., description="Current version flag")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Generation metadata")
    created_at: datetime = Field(..., description="Creation timestamp")


class ArtifactSchema(BaseModel):
    """Basic artifact information.

    Attributes:
        artifact_id: Unique artifact identifier
        artifact_key: Composite key (format: {kind}:{project}:{identifier})
        artifact_kind: Artifact type
        project_id: Parent project ID
        created_at: Artifact creation timestamp
        updated_at: Last update timestamp
        current_version: Current artifact version
    """

    model_config = ConfigDict(from_attributes=True)

    artifact_id: int = Field(..., description="Artifact identifier")
    artifact_key: str = Field(
        ...,
        description="Composite key",
        examples=["summary:project-alpha:meeting-123"],
    )
    artifact_kind: ArtifactKindEnum = Field(..., description="Artifact type")
    project_id: Optional[int] = Field(None, description="Project ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")
    current_version: Optional[ArtifactVersionSchema] = Field(None, description="Current version")


class ArtifactListResponse(BaseModel):
    """Paginated artifact list response.

    Attributes:
        artifacts: List of artifact objects
        total: Total number of artifacts (across all pages)
        limit: Page size
        offset: Current page offset
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "artifacts": [
                    {
                        "artifact_id": 10,
                        "artifact_key": "summary:project-alpha:meeting-123",
                        "artifact_kind": "summary",
                        "project_id": 1,
                        "created_at": "2025-11-04T14:32:00Z",
                        "updated_at": "2025-11-04T14:32:00Z",
                    }
                ],
                "total": 89,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    artifacts: List[ArtifactSchema] = Field(..., description="List of artifacts")
    total: int = Field(..., description="Total artifact count", ge=0)
    limit: int = Field(..., description="Page size", ge=1, le=200)
    offset: int = Field(..., description="Page offset", ge=0)


class SourceFileLink(BaseModel):
    """Source file link for artifact details.

    Attributes:
        file_id: File identifier
        file_version_id: File version ID
        relative_path: File path
        role_type: Link role (source, derived, reference)
        contribution_weight: Contribution weight (0.0-1.0)
    """

    model_config = ConfigDict(from_attributes=True)

    file_id: int = Field(..., description="File ID")
    file_version_id: int = Field(..., description="File version ID")
    relative_path: str = Field(..., description="File path")
    role_type: LinkRoleTypeEnum = Field(..., description="Link role")
    contribution_weight: Optional[float] = Field(None, description="Contribution weight", ge=0.0, le=1.0)


class ArtifactDetail(ArtifactSchema):
    """Detailed artifact information with version history and source files.

    Extends ArtifactSchema with:
        - Complete version history
        - Source file links
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "artifact_id": 10,
                "artifact_key": "summary:project-alpha:meeting-123",
                "artifact_kind": "summary",
                "project_id": 1,
                "created_at": "2025-11-04T14:32:00Z",
                "updated_at": "2025-11-04T14:32:00Z",
                "versions": [
                    {
                        "version_id": 20,
                        "artifact_id": 10,
                        "job_run_id": 789,
                        "content_locator": "artifact_10_v1.json",
                        "content_hash": "abc123...",
                        "is_current": True,
                        "metadata": {
                            "llm_provider": "openai",
                            "llm_model": "gpt-4o",
                            "prompt_tokens": 2500,
                            "completion_tokens": 800,
                            "cost_estimate": 0.05,
                        },
                        "created_at": "2025-11-04T14:32:00Z",
                    }
                ],
                "source_files": [
                    {
                        "file_id": 123,
                        "file_version_id": 456,
                        "relative_path": "meetings/standup.md",
                        "role_type": "source",
                        "contribution_weight": 1.0,
                    }
                ],
            }
        },
    )

    versions: List[ArtifactVersionSchema] = Field(default_factory=list, description="Version history")
    source_files: List[SourceFileLink] = Field(default_factory=list, description="Source files")


class ArtifactVersionContent(BaseModel):
    """Artifact version content response.

    Attributes:
        version_id: Version identifier
        content: Artifact content (structure varies by kind)
        metadata: Generation metadata
        created_at: Creation timestamp
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "version_id": 20,
                    "content": {
                        "title": "Weekly Standup Summary",
                        "key_points": [
                            "Team decided to use Kubernetes for deployment",
                            "Alice raised concerns about database performance",
                        ],
                        "participants": ["Alice", "Bob", "Carol"],
                        "meeting_date": "2025-11-04",
                    },
                    "metadata": {
                        "llm_provider": "openai",
                        "llm_model": "gpt-4o",
                        "prompt_tokens": 2500,
                        "completion_tokens": 800,
                        "cost_estimate": 0.05,
                    },
                    "created_at": "2025-11-04T14:32:00Z",
                },
                {
                    "version_id": 21,
                    "content": {
                        "decisions": [
                            {
                                "decisor": "Alice Smith",
                                "decision": "Use Kubernetes for container orchestration",
                                "date": "2025-11-04",
                                "justification": "Better scalability and ecosystem support",
                                "confidence": "high",
                            }
                        ]
                    },
                    "metadata": {
                        "llm_provider": "anthropic",
                        "llm_model": "claude-3-5-sonnet",
                        "prompt_tokens": 2000,
                        "completion_tokens": 600,
                        "cost_estimate": 0.03,
                    },
                    "created_at": "2025-11-04T14:32:10Z",
                },
            ]
        }
    )

    version_id: int = Field(..., description="Version identifier")
    content: Dict[str, Any] = Field(..., description="Artifact content (structure varies)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Generation metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
