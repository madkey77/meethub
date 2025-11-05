"""Pydantic schemas for job tracking and monitoring endpoints.

This module defines request/response schemas for:
- Job listing with pagination and filtering
- Job details with steps and metrics
- Job retry requests
- Job step logs
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models import JobRunStatus, JobStepStatus


# ==============================================================================
# Enums
# ==============================================================================

class JobRunStatusEnum(str, Enum):
    """Job execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class JobStepStatusEnum(str, Enum):
    """Job step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


# ==============================================================================
# Request Schemas
# ==============================================================================

class JobRetryRequest(BaseModel):
    """Request to retry a failed job.

    Attributes:
        retry_steps: Specific steps to retry (empty = retry all failed steps)
        switch_provider: Switch to alternative LLM provider for retry
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "retry_steps": ["generate_summary", "generate_decisions"],
                "switch_provider": "anthropic",
            }
        }
    )

    retry_steps: Optional[List[str]] = Field(
        default=None,
        description="Specific steps to retry (null = all failed steps)",
        examples=[["generate_summary", "generate_decisions"]],
    )
    switch_provider: Optional[str] = Field(
        None,
        description="Switch to alternative LLM provider",
        examples=["anthropic", "openai"],
    )


# ==============================================================================
# Response Schemas
# ==============================================================================

class JobMetrics(BaseModel):
    """Job execution metrics.

    Attributes:
        chunks_created: Number of chunks created
        embeddings_generated: Number of embeddings generated
        artifacts_produced: Number of artifacts generated
        duration_seconds: Total job duration
        llm_tokens_used: Total LLM tokens consumed
        llm_cost_estimate: Estimated LLM cost in USD
    """

    model_config = ConfigDict(from_attributes=True)

    chunks_created: Optional[int] = Field(0, description="Chunks created", ge=0)
    embeddings_generated: Optional[int] = Field(0, description="Embeddings generated", ge=0)
    artifacts_produced: Optional[int] = Field(0, description="Artifacts produced", ge=0)
    duration_seconds: Optional[float] = Field(None, description="Duration in seconds", ge=0)
    llm_tokens_used: Optional[int] = Field(None, description="LLM tokens used", ge=0)
    llm_cost_estimate: Optional[float] = Field(None, description="Estimated cost (USD)", ge=0)


class JobSummary(BaseModel):
    """Summary job information for list responses.

    Attributes:
        job_id: Unique job identifier
        pipeline_name: Pipeline/rule name
        status: Job status
        input_file_version_id: Source file version ID
        backfill_job_id: Parent backfill job ID (if part of backfill)
        retry_count: Number of retries attempted
        started_at: Job start timestamp
        completed_at: Job completion timestamp
        metrics: Job metrics summary
    """

    model_config = ConfigDict(from_attributes=True)

    job_id: int = Field(..., description="Job identifier")
    pipeline_name: str = Field(..., description="Pipeline name", examples=["meeting-rag-ingestion"])
    status: JobRunStatusEnum = Field(..., description="Job status")
    input_file_version_id: Optional[int] = Field(None, description="Input file version ID")
    backfill_job_id: Optional[int] = Field(None, description="Backfill job ID")
    retry_count: int = Field(0, description="Retry count", ge=0)
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    metrics: Optional[JobMetrics] = Field(None, description="Job metrics")


class JobListResponse(BaseModel):
    """Paginated job list response.

    Attributes:
        jobs: List of job summaries
        total: Total number of jobs (across all pages)
        limit: Page size
        offset: Current page offset
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jobs": [
                    {
                        "job_id": 789,
                        "pipeline_name": "meeting-rag-ingestion",
                        "status": "success",
                        "started_at": "2025-11-04T14:30:00Z",
                        "completed_at": "2025-11-04T14:32:15Z",
                        "metrics": {
                            "chunks_created": 150,
                            "embeddings_generated": 150,
                            "artifacts_produced": 3,
                            "llm_cost_estimate": 0.15,
                        },
                    }
                ],
                "total": 245,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    jobs: List[JobSummary] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total job count", ge=0)
    limit: int = Field(..., description="Page size", ge=1, le=200)
    offset: int = Field(..., description="Page offset", ge=0)


class JobStepDetail(BaseModel):
    """Detailed job step information.

    Attributes:
        step_id: Unique step identifier
        job_run_id: Parent job ID
        step_name: Step name (normalize, chunk, embed, generate_{kind})
        status: Step status
        error_message: Error message (if failed)
        error_type: Error type (if failed)
        log_output: Structured log output (JSON)
        started_at: Step start timestamp
        completed_at: Step completion timestamp
    """

    model_config = ConfigDict(from_attributes=True)

    step_id: int = Field(..., description="Step identifier")
    job_run_id: int = Field(..., description="Parent job ID")
    step_name: str = Field(..., description="Step name", examples=["chunk", "embed"])
    status: JobStepStatusEnum = Field(..., description="Step status")
    error_message: Optional[str] = Field(None, description="Error message")
    error_type: Optional[str] = Field(None, description="Error type")
    log_output: Optional[Dict[str, Any]] = Field(None, description="Structured logs")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")


class ArtifactSummaryForJob(BaseModel):
    """Brief artifact information for job details.

    Attributes:
        artifact_key: Unique artifact key
        artifact_kind: Artifact type
        version_id: Artifact version ID
        created_at: Creation timestamp
    """

    model_config = ConfigDict(from_attributes=True)

    artifact_key: str = Field(..., description="Artifact key")
    artifact_kind: str = Field(..., description="Artifact type")
    version_id: int = Field(..., description="Version ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class JobDetail(JobSummary):
    """Detailed job information with steps and artifacts.

    Extends JobSummary with:
        - Complete step history with logs
        - Associated artifacts
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "job_id": 789,
                "pipeline_name": "meeting-rag-ingestion",
                "status": "success",
                "started_at": "2025-11-04T14:30:00Z",
                "completed_at": "2025-11-04T14:32:15Z",
                "metrics": {
                    "chunks_created": 150,
                    "embeddings_generated": 150,
                    "artifacts_produced": 3,
                    "duration_seconds": 135,
                    "llm_tokens_used": 4500,
                    "llm_cost_estimate": 0.15,
                },
                "steps": [
                    {
                        "step_id": 1,
                        "step_name": "normalize",
                        "status": "success",
                        "started_at": "2025-11-04T14:30:01Z",
                        "completed_at": "2025-11-04T14:30:05Z",
                    }
                ],
                "artifacts": [
                    {
                        "artifact_key": "summary:file:123",
                        "artifact_kind": "summary",
                        "version_id": 10,
                        "created_at": "2025-11-04T14:32:10Z",
                    }
                ],
            }
        },
    )

    steps: List[JobStepDetail] = Field(default_factory=list, description="Job steps")
    artifacts: List[ArtifactSummaryForJob] = Field(default_factory=list, description="Generated artifacts")


class JobStepLogEntry(BaseModel):
    """Individual log entry from job step.

    Attributes:
        timestamp: Log timestamp
        level: Log level (DEBUG, INFO, WARN, ERROR)
        message: Log message
        context: Additional context (JSON)
    """

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level", examples=["INFO", "ERROR"])
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(None, description="Context data")


class JobStepLogs(BaseModel):
    """Complete log output for a job step.

    Attributes:
        step_id: Step identifier
        step_name: Step name
        entries: List of log entries
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "step_id": 1,
                "step_name": "chunk",
                "entries": [
                    {
                        "timestamp": "2025-11-04T14:30:05Z",
                        "level": "INFO",
                        "message": "Chunking started",
                        "context": {"chunk_size": 1200, "chunk_overlap": 200},
                    },
                    {
                        "timestamp": "2025-11-04T14:30:20Z",
                        "level": "INFO",
                        "message": "Chunking completed",
                        "context": {"chunks_created": 150},
                    },
                ],
            }
        }
    )

    step_id: int = Field(..., description="Step identifier")
    step_name: str = Field(..., description="Step name")
    entries: List[JobStepLogEntry] = Field(default_factory=list, description="Log entries")
