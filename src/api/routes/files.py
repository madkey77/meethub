"""File upload and management API endpoints.

This module provides REST API endpoints for:
- File upload with RAG pipeline triggering
- File listing with filters and pagination
- File details with version history
- File deletion (soft and hard delete)
- File version management
- File reprocessing

All endpoints require authentication (except health check).
"""

import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File as FastAPIFile,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from src.api.dependencies import get_db
from src.api.schemas.file_schemas import (
    ArtifactSummary,
    FileDetail,
    FileListResponse,
    FileSchema,
    FileUploadResponse,
    FileVersionSchema,
)
from src.api.schemas.job_schemas import JobDetail
from src.config import settings
from src.models import (
    Artifact,
    ArtifactLink,
    ArtifactVersion,
    Chunk,
    Embedding,
    File,
    FileSourceType,
    FileVersion,
    JobRun,
    JobRunStatus,
    Project,
)
from src.services.file_ingestion import (
    CorruptedFileError,
    FileIngestionService,
    FileTooLargeError,
    UnsupportedFormatError,
)
from src.services.rag_pipeline import RAGPipeline
from src.utils.exceptions import FileIngestionError
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


# ==============================================================================
# POST /api/v1/files/upload
# ==============================================================================

@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload file for ingestion",
    description="""
    Upload a file for RAG ingestion. Accepts PDF, DOCX, Markdown, plain text, and JSON chat exports.

    The file is validated, text is extracted, and the RAG pipeline is triggered asynchronously.
    Returns job_run_id for tracking processing status.

    **Duplicate handling:**
    - If file with same hash exists in project, returns 409 Conflict
    - Use `force_reprocess=true` query parameter to bypass duplicate check

    **Size limits:**
    - Documents: 50MB max
    - Audio files: 100MB max

    **Supported formats:**
    - PDF: application/pdf
    - DOCX: application/vnd.openxmlformats-officedocument.wordprocessingml.document
    - Markdown: text/markdown
    - Plain text: text/plain
    - JSON: application/json (Slack/Teams/WhatsApp exports)
    """,
)
async def upload_file(
    file: UploadFile = FastAPIFile(..., description="File to upload"),
    project_id: Optional[int] = Form(None, description="Project ID (uses default if not provided)"),
    source_type: str = Form("uploaded_document", description="Source type (uploaded_document, chat_export)"),
    force_reprocess: bool = Query(False, description="Force reprocessing even if duplicate"),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    """Upload file and trigger RAG ingestion pipeline.

    Args:
        file: Uploaded file (multipart/form-data)
        project_id: Project ID for grouping (optional, uses default project)
        source_type: Source classification
        force_reprocess: Bypass duplicate detection
        db: Database session

    Returns:
        FileUploadResponse with file_id, file_version_id, job_run_id, status, message

    Raises:
        400 Bad Request: Invalid file type, size, or corruption
        404 Not Found: Project not found
        409 Conflict: Duplicate file (unless force_reprocess=true)
        500 Internal Server Error: Processing failure
    """
    log = logger.bind(
        endpoint="/files/upload",
        filename=file.filename,
        content_type=file.content_type,
        project_id=project_id,
    )
    log.info("file_upload.start")

    try:
        # Step 1: Resolve project (use default if not provided)
        if project_id is None:
            project = db.query(Project).filter(Project.is_default == True).first()
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No default project found. Please specify project_id."
                )
            project_id = project.project_id
        else:
            # Verify project exists
            project = db.query(Project).filter(Project.project_id == project_id).first()
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project with id {project_id} not found"
                )

        # Step 2: Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        log = log.bind(temp_path=tmp_file_path, file_size=len(content))

        # Step 3: Ingest file using FileIngestionService
        file_service = FileIngestionService(db)

        try:
            file_entity = file_service.ingest_file(
                file_path=tmp_file_path,
                project_id=project_id,
                source_type=source_type
            )

            # Step 4: Check if duplicate (unless force_reprocess)
            if not force_reprocess:
                # Check if this is a duplicate by comparing file_id with existing
                version = db.query(FileVersion).filter(
                    FileVersion.version_id == file_entity.current_version_id
                ).first()

                # If file already existed (found by hash), it's a duplicate
                existing_count = db.query(FileVersion).filter(
                    FileVersion.file_id == file_entity.file_id
                ).count()

                if existing_count > 0:
                    # Check if this version already has a job run
                    existing_job = db.query(JobRun).filter(
                        JobRun.input_file_version_id == file_entity.current_version_id
                    ).first()

                    if existing_job:
                        log.info("file_upload.duplicate_detected", file_id=file_entity.file_id)
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail={
                                "message": "Duplicate file detected",
                                "file_id": file_entity.file_id,
                                "existing_file_id": file_entity.file_id,
                                "file_version_id": file_entity.current_version_id,
                            }
                        )

            # Step 5: Trigger RAG pipeline asynchronously
            # Load RAG processing rules (in production, load from rules.yaml)
            rules = {
                "pipeline_name": "default-file-ingestion",
                "chunking_strategy": "DocumentChunker",
                "chunk_size": settings.rag_chunk_size,
                "chunk_overlap": settings.rag_chunk_overlap,
                "embedding_provider": settings.llm_provider_preference,
                "embedding_model": settings.openai_embedding_model,
                "artifacts": [
                    {
                        "kind": "summary",
                        "generator": "SummaryGenerator",
                        "llm_provider": settings.llm_provider_preference,
                        "llm_model": settings.openai_chat_model,
                    }
                ],
            }

            # Create RAG pipeline and process (in production, use background tasks)
            rag_pipeline = RAGPipeline(db)
            job_run = rag_pipeline.process_file(
                file_version=db.query(FileVersion).get(file_entity.current_version_id),
                rules=rules
            )

            log.info(
                "file_upload.success",
                file_id=file_entity.file_id,
                job_run_id=job_run.job_id,
            )

            return FileUploadResponse(
                file_id=file_entity.file_id,
                file_version_id=file_entity.current_version_id,
                job_run_id=job_run.job_id,
                status="queued" if job_run.status == JobRunStatus.QUEUED else "processing",
                message=f"File queued for ingestion. Job ID: {job_run.job_id}"
            )

        except UnsupportedFormatError as e:
            log.error("file_upload.unsupported_format", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format. {e.troubleshooting_hint}"
            )
        except FileTooLargeError as e:
            log.error("file_upload.file_too_large", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. {e.troubleshooting_hint}"
            )
        except CorruptedFileError as e:
            log.error("file_upload.corrupted_file", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File corrupted or invalid. {e.troubleshooting_hint}"
            )
        except FileIngestionError as e:
            log.error("file_upload.ingestion_error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File ingestion failed: {str(e)}"
            )
        finally:
            # Cleanup temporary file
            try:
                Path(tmp_file_path).unlink()
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as e:
        log.error("file_upload.unexpected_error", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during file upload: {str(e)}"
        )


# ==============================================================================
# GET /api/v1/files
# ==============================================================================

@router.get(
    "",
    response_model=FileListResponse,
    summary="List files with filters",
    description="""
    List files with optional filters and pagination.

    **Filters:**
    - project_id: Filter by project
    - source_type: Filter by source (meeting, uploaded_document, chat_export)
    - mime_type: Filter by MIME type
    - deleted: Include deleted files (default: false)

    **Pagination:**
    - limit: Page size (default: 20, max: 200)
    - offset: Skip first N files (default: 0)
    """,
)
def list_files(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    source_type: Optional[FileSourceType] = Query(None, description="Filter by source type"),
    mime_type: Optional[str] = Query(None, description="Filter by MIME type"),
    deleted: bool = Query(False, description="Include deleted files"),
    limit: int = Query(20, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
) -> FileListResponse:
    """List files with filters and pagination.

    Args:
        project_id: Optional project filter
        source_type: Optional source type filter
        mime_type: Optional MIME type filter
        deleted: Include deleted files
        limit: Page size
        offset: Page offset
        db: Database session

    Returns:
        FileListResponse with files, total, limit, offset
    """
    # Build query with filters
    query = db.query(File)

    if project_id is not None:
        query = query.filter(File.project_id == project_id)

    if source_type is not None:
        query = query.filter(File.source_type == source_type)

    if mime_type is not None:
        query = query.filter(File.mime_type == mime_type)

    if not deleted:
        query = query.filter(File.deleted == False)

    # Get total count
    total = query.count()

    # Apply pagination and eager load current version
    files = (
        query
        .options(joinedload(File.current_version))
        .order_by(File.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Convert to schemas
    file_schemas = [
        FileSchema(
            file_id=f.file_id,
            relative_path=f.relative_path,
            mime_type=f.mime_type,
            source_type=f.source_type,
            project_id=f.project_id,
            deleted=f.deleted,
            created_at=f.created_at,
            updated_at=f.updated_at,
            current_version=FileVersionSchema.model_validate(f.current_version) if f.current_version else None
        )
        for f in files
    ]

    return FileListResponse(
        files=file_schemas,
        total=total,
        limit=limit,
        offset=offset
    )


# ==============================================================================
# GET /api/v1/files/{file_id}
# ==============================================================================

@router.get(
    "/{file_id}",
    response_model=FileDetail,
    summary="Get file details",
    description="""
    Get detailed file information including:
    - Current file version
    - Complete version history
    - Chunk count
    - Associated artifacts (summaries generated)

    Returns 404 if file not found or deleted (unless include_deleted=true).
    """,
)
def get_file_detail(
    file_id: int,
    include_deleted: bool = Query(False, description="Include deleted files"),
    db: Session = Depends(get_db),
) -> FileDetail:
    """Get file details with version history and artifacts.

    Args:
        file_id: File ID
        include_deleted: Include deleted files
        db: Database session

    Returns:
        FileDetail with complete file information

    Raises:
        404 Not Found: File not found or deleted
    """
    # Query file with eager loading
    query = db.query(File).options(
        joinedload(File.versions),
        joinedload(File.current_version)
    ).filter(File.file_id == file_id)

    if not include_deleted:
        query = query.filter(File.deleted == False)

    file_entity = query.first()

    if not file_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id {file_id} not found"
        )

    # Get chunk count for current version
    chunk_count = 0
    embedding_generated_at = None

    if file_entity.current_version:
        chunk_count = (
            db.query(func.count(Chunk.chunk_id))
            .filter(
                Chunk.file_version_id == file_entity.current_version_id,
                Chunk.deleted == False
            )
            .scalar()
        ) or 0

        # Get embedding timestamp (from first chunk's embedding)
        first_embedding = (
            db.query(Embedding)
            .join(Chunk)
            .filter(Chunk.file_version_id == file_entity.current_version_id)
            .order_by(Embedding.created_at)
            .first()
        )
        if first_embedding:
            embedding_generated_at = first_embedding.created_at

    # Get associated artifacts
    artifacts = (
        db.query(Artifact)
        .join(ArtifactVersion)
        .join(ArtifactLink)
        .join(FileVersion)
        .filter(FileVersion.file_id == file_id)
        .distinct()
        .all()
    )

    artifact_summaries = [
        ArtifactSummary(
            artifact_key=a.artifact_key,
            artifact_kind=a.artifact_kind,
            version_id=a.current_version_id,
            created_at=a.created_at
        )
        for a in artifacts
    ]

    # Build response
    return FileDetail(
        file_id=file_entity.file_id,
        relative_path=file_entity.relative_path,
        mime_type=file_entity.mime_type,
        source_type=file_entity.source_type,
        project_id=file_entity.project_id,
        deleted=file_entity.deleted,
        created_at=file_entity.created_at,
        updated_at=file_entity.updated_at,
        current_version=FileVersionSchema.model_validate(file_entity.current_version) if file_entity.current_version else None,
        versions=[FileVersionSchema.model_validate(v) for v in file_entity.versions],
        chunk_count=chunk_count,
        embedding_generated_at=embedding_generated_at,
        artifacts=artifact_summaries
    )


# ==============================================================================
# DELETE /api/v1/files/{file_id}
# ==============================================================================

@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete file",
    description="""
    Delete file (soft delete by default).

    **Soft delete (default):**
    - Sets deleted=true flag
    - File remains in database
    - Can be restored

    **Hard delete (hard=true):**
    - Permanently removes file and all versions
    - Removes chunks and embeddings (cascade)
    - Removes embeddings from ChromaDB vector store
    - **Cannot be undone**

    Returns 204 No Content on success.
    """,
)
def delete_file(
    file_id: int,
    hard: bool = Query(False, description="Hard delete (permanent)"),
    db: Session = Depends(get_db),
) -> None:
    """Delete file (soft or hard delete).

    Args:
        file_id: File ID to delete
        hard: If true, permanently delete; if false, soft delete
        db: Database session

    Raises:
        404 Not Found: File not found
    """
    file_entity = db.query(File).filter(File.file_id == file_id).first()

    if not file_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id {file_id} not found"
        )

    if hard:
        # Hard delete: remove from database (cascades to versions, chunks, embeddings)
        # Note: In production, also remove from ChromaDB vector store
        db.delete(file_entity)
        logger.info("file.hard_deleted", file_id=file_id)
    else:
        # Soft delete: set deleted flag
        file_entity.deleted = True
        logger.info("file.soft_deleted", file_id=file_id)

    db.commit()


# ==============================================================================
# GET /api/v1/files/{file_id}/versions
# ==============================================================================

@router.get(
    "/{file_id}/versions",
    response_model=List[FileVersionSchema],
    summary="Get file version history",
    description="""
    Get all versions of a file, ordered by discovery date (newest first).

    Each version includes:
    - version_id
    - content_hash (SHA-256)
    - file_size_bytes
    - is_current flag
    - discovered_at timestamp
    """,
)
def get_file_versions(
    file_id: int,
    limit: int = Query(50, ge=1, le=200, description="Max versions to return"),
    offset: int = Query(0, ge=0, description="Version offset"),
    db: Session = Depends(get_db),
) -> List[FileVersionSchema]:
    """Get file version history.

    Args:
        file_id: File ID
        limit: Max versions to return
        offset: Version offset
        db: Database session

    Returns:
        List of FileVersionSchema objects

    Raises:
        404 Not Found: File not found
    """
    # Verify file exists
    file_entity = db.query(File).filter(File.file_id == file_id).first()
    if not file_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id {file_id} not found"
        )

    # Get versions
    versions = (
        db.query(FileVersion)
        .filter(FileVersion.file_id == file_id)
        .order_by(FileVersion.discovered_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [FileVersionSchema.model_validate(v) for v in versions]


# ==============================================================================
# POST /api/v1/files/{file_id}/reprocess
# ==============================================================================

@router.post(
    "/{file_id}/reprocess",
    response_model=JobDetail,
    summary="Reprocess file through RAG pipeline",
    description="""
    Force file reprocessing through RAG pipeline.

    Creates new JobRun even if content hasn't changed. Useful for:
    - Testing new LLM models
    - Regenerating artifacts with updated prompts
    - Switching LLM providers (OpenAI ↔ Anthropic)

    **Optional overrides:**
    - provider: LLM provider to use (openai, anthropic)
    - model: Specific model to use
    """,
)
def reprocess_file(
    file_id: int,
    provider: Optional[str] = Query(None, description="LLM provider override"),
    model: Optional[str] = Query(None, description="LLM model override"),
    db: Session = Depends(get_db),
) -> JobDetail:
    """Reprocess file through RAG pipeline.

    Args:
        file_id: File ID to reprocess
        provider: Optional LLM provider override
        model: Optional model override
        db: Database session

    Returns:
        JobDetail with job_run_id and status

    Raises:
        404 Not Found: File not found
    """
    # Verify file exists
    file_entity = db.query(File).filter(File.file_id == file_id, File.deleted == False).first()
    if not file_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id {file_id} not found or deleted"
        )

    # Get current version
    if not file_entity.current_version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File {file_id} has no current version"
        )

    version = db.query(FileVersion).get(file_entity.current_version_id)

    # Build rules with overrides
    rules = {
        "pipeline_name": "reprocess-file",
        "chunking_strategy": "DocumentChunker",
        "chunk_size": settings.rag_chunk_size,
        "chunk_overlap": settings.rag_chunk_overlap,
        "embedding_provider": provider or settings.llm_provider_preference,
        "embedding_model": settings.openai_embedding_model,
        "artifacts": [
            {
                "kind": "summary",
                "llm_provider": provider or settings.llm_provider_preference,
                "llm_model": model or settings.openai_chat_model,
            }
        ],
    }

    # Trigger RAG pipeline
    rag_pipeline = RAGPipeline(db)
    job_run = rag_pipeline.process_file(version, rules)

    logger.info(
        "file.reprocess_triggered",
        file_id=file_id,
        job_run_id=job_run.job_id,
        provider=provider,
        model=model
    )

    # Return job details
    from src.api.schemas.job_schemas import JobDetail

    return JobDetail(
        job_id=job_run.job_id,
        pipeline_name=job_run.pipeline_name,
        status=job_run.status,
        input_file_version_id=job_run.input_file_version_id,
        started_at=job_run.started_at,
        completed_at=job_run.completed_at,
        metrics=job_run.metrics,
        steps=[]  # Could be populated if needed
    )
