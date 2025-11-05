"""Pydantic schemas for FastAPI request/response validation.

This package contains all Pydantic models for API contracts:
    - file_schemas: File upload and management
    - job_schemas: Job tracking and monitoring
    - artifact_schemas: Artifact query and retrieval
    - chat_schemas: RAG chat queries and responses

All schemas use Pydantic v2 with:
    - ConfigDict for configuration
    - Field() for validation and documentation
    - field_validator for custom validation
    - json_schema_extra for OpenAPI examples
"""

# File schemas
from src.api.schemas.file_schemas import (
    FileDetail,
    FileListResponse,
    FileSchema,
    FileUploadResponse,
    FileVersionSchema,
)

# Job schemas
from src.api.schemas.job_schemas import (
    JobDetail,
    JobListResponse,
    JobMetrics,
    JobRetryRequest,
    JobRunStatusEnum,
    JobStepDetail,
    JobStepLogs,
    JobStepStatusEnum,
    JobSummary,
)

# Artifact schemas
from src.api.schemas.artifact_schemas import (
    ArtifactDetail,
    ArtifactKindEnum,
    ArtifactListResponse,
    ArtifactSchema,
    ArtifactVersionContent,
    ArtifactVersionSchema,
    LinkRoleTypeEnum,
)

# Chat schemas
from src.api.schemas.chat_schemas import (
    ChatQueryRequest,
    ChatResponse,
    Citation,
    RetrievalMetadata,
    SourceTypeEnum,
)

__all__ = [
    # File schemas
    "FileSchema",
    "FileVersionSchema",
    "FileUploadResponse",
    "FileListResponse",
    "FileDetail",
    # Job schemas
    "JobSummary",
    "JobDetail",
    "JobListResponse",
    "JobMetrics",
    "JobStepDetail",
    "JobStepLogs",
    "JobRetryRequest",
    "JobRunStatusEnum",
    "JobStepStatusEnum",
    # Artifact schemas
    "ArtifactSchema",
    "ArtifactVersionSchema",
    "ArtifactListResponse",
    "ArtifactDetail",
    "ArtifactVersionContent",
    "ArtifactKindEnum",
    "LinkRoleTypeEnum",
    # Chat schemas
    "ChatQueryRequest",
    "ChatResponse",
    "Citation",
    "RetrievalMetadata",
    "SourceTypeEnum",
]
