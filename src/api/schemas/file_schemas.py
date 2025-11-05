"""Pydantic schemas for file upload and management endpoints.

This module defines request/response schemas for:
- File upload (multipart/form-data)
- File listing with pagination
- File details with version history
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models import FileSourceType


# ==============================================================================
# Request Schemas
# ==============================================================================

# Note: FileUploadRequest is handled by FastAPI's UploadFile, not Pydantic
# This is a reference schema for documentation


# ==============================================================================
# Response Schemas
# ==============================================================================

class FileUploadResponse(BaseModel):
    """Response after successful file upload.

    Attributes:
        file_id: Unique file identifier
        file_version_id: ID of the created file version
        job_run_id: ID of the RAG pipeline job (if queued)
        status: Upload status (queued, duplicate_skipped)
        message: Human-readable message
    """

    model_config = ConfigDict(from_attributes=True)

    file_id: int = Field(..., description="Unique file identifier", examples=[123])
    file_version_id: int = Field(..., description="File version ID", examples=[456])
    job_run_id: Optional[int] = Field(None, description="Job run ID for processing", examples=[789])
    status: str = Field(..., description="Upload status", examples=["queued", "duplicate_skipped"])
    message: str = Field(..., description="Status message", examples=["File queued for ingestion"])


class FileVersionSchema(BaseModel):
    """File version information.

    Attributes:
        version_id: Unique version identifier
        file_id: Parent file ID
        content_hash: SHA-256 hash (hex string)
        file_size_bytes: File size in bytes
        content_locator: Storage location
        is_current: True if this is the current version
        discovered_at: Version creation timestamp
    """

    model_config = ConfigDict(from_attributes=True)

    version_id: int = Field(..., description="Version identifier")
    file_id: int = Field(..., description="Parent file ID")
    content_hash: str = Field(..., description="SHA-256 hash", examples=["a1b2c3d4e5f6..."])
    file_size_bytes: int = Field(..., description="File size in bytes", examples=[1024000])
    content_locator: str = Field(..., description="Storage path", examples=["/data/uploads/file.pdf"])
    is_current: bool = Field(..., description="Current version flag")
    discovered_at: datetime = Field(..., description="Version timestamp")


class FileSchema(BaseModel):
    """Basic file information.

    Attributes:
        file_id: Unique file identifier
        relative_path: File path relative to project root
        mime_type: MIME type (e.g., application/pdf)
        source_type: Source classification (meeting, uploaded_document, chat_export)
        project_id: Parent project ID
        deleted: Soft delete flag
        created_at: File creation timestamp
        updated_at: Last update timestamp
        current_version: Current file version
    """

    model_config = ConfigDict(from_attributes=True)

    file_id: int = Field(..., description="File identifier")
    relative_path: str = Field(..., description="File path", examples=["documents/report.pdf"])
    mime_type: str = Field(..., description="MIME type", examples=["application/pdf"])
    source_type: FileSourceType = Field(..., description="Source classification")
    project_id: int = Field(..., description="Project ID")
    deleted: bool = Field(False, description="Soft delete flag")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")
    current_version: Optional[FileVersionSchema] = Field(None, description="Current version")


class FileListResponse(BaseModel):
    """Paginated file list response.

    Attributes:
        files: List of file objects
        total: Total number of files (across all pages)
        limit: Page size
        offset: Current page offset
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "files": [
                    {
                        "file_id": 123,
                        "relative_path": "documents/report.pdf",
                        "mime_type": "application/pdf",
                        "source_type": "uploaded_document",
                        "project_id": 1,
                        "deleted": False,
                        "created_at": "2025-11-04T14:30:00Z",
                        "updated_at": "2025-11-04T14:30:00Z",
                    }
                ],
                "total": 245,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    files: List[FileSchema] = Field(..., description="List of files")
    total: int = Field(..., description="Total file count", ge=0)
    limit: int = Field(..., description="Page size", ge=1, le=200)
    offset: int = Field(..., description="Page offset", ge=0)


class ArtifactSummary(BaseModel):
    """Brief artifact information for file details.

    Attributes:
        artifact_key: Unique artifact key
        artifact_kind: Artifact type (summary, decisions, entities, etc.)
        version_id: Current artifact version ID
        created_at: Artifact creation timestamp
    """

    model_config = ConfigDict(from_attributes=True)

    artifact_key: str = Field(..., description="Artifact key", examples=["summary:file:123"])
    artifact_kind: str = Field(..., description="Artifact type", examples=["summary"])
    version_id: int = Field(..., description="Current version ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class FileDetail(FileSchema):
    """Detailed file information with version history and artifacts.

    Extends FileSchema with:
        - Complete version history
        - Chunk count
        - Embedding generation timestamp
        - Associated artifacts
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "file_id": 123,
                "relative_path": "documents/report.pdf",
                "mime_type": "application/pdf",
                "source_type": "uploaded_document",
                "project_id": 1,
                "deleted": False,
                "created_at": "2025-11-04T14:30:00Z",
                "updated_at": "2025-11-04T14:32:00Z",
                "versions": [
                    {
                        "version_id": 456,
                        "file_id": 123,
                        "content_hash": "a1b2c3...",
                        "file_size_bytes": 1024000,
                        "content_locator": "/data/uploads/file.pdf",
                        "is_current": True,
                        "discovered_at": "2025-11-04T14:30:00Z",
                    }
                ],
                "chunk_count": 150,
                "embedding_generated_at": "2025-11-04T14:31:00Z",
                "artifacts": [
                    {
                        "artifact_key": "summary:file:123",
                        "artifact_kind": "summary",
                        "version_id": 789,
                        "created_at": "2025-11-04T14:32:00Z",
                    }
                ],
            }
        },
    )

    versions: List[FileVersionSchema] = Field(..., description="Version history")
    chunk_count: int = Field(0, description="Number of chunks", ge=0)
    embedding_generated_at: Optional[datetime] = Field(None, description="Embedding timestamp")
    artifacts: List[ArtifactSummary] = Field(default_factory=list, description="Associated artifacts")
