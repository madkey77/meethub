"""Meeting RAG Bridge service for connecting transcription pipeline to RAG.

This module bridges the existing meeting transcription pipeline (Google Meet API →
Deepgram transcription) with the RAG pipeline for intelligent querying. It creates
File and FileVersion entities from completed transcripts and triggers RAG ingestion.

The bridge pattern maintains separation between transcription and RAG pipelines,
allowing them to evolve independently while enabling automatic RAG ingestion of
meeting transcripts.
"""

import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.models import (
    File,
    FileSourceType,
    FileVersion,
    Meeting,
    RAGIngestionStatus,
    Transcript,
)
from src.services.file_ingestion import FileIngestionService
from src.services.rag_pipeline import RAGPipeline
from src.utils.exceptions import RAGError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MeetingRAGBridge:
    """Bridge service connecting meeting transcription to RAG pipeline.

    This service acts as the integration point between the existing transcription
    pipeline and the new RAG capabilities. It:

    1. Monitors completed transcripts
    2. Creates File/FileVersion entities for RAG ingestion
    3. Triggers RAG pipeline processing
    4. Tracks ingestion status on Meeting entity
    5. Handles change detection for re-transcribed meetings

    Example:
        >>> from src.models import SessionLocal
        >>> from src.services.meeting_rag_bridge import MeetingRAGBridge
        >>>
        >>> db = SessionLocal()
        >>> bridge = MeetingRAGBridge(db_session=db)
        >>>
        >>> # Called after transcription completes
        >>> file = bridge.on_transcription_complete(transcript_id=123)
        >>> print(f"Created File {file.file_id} for Meeting")
    """

    def __init__(
        self,
        db_session: Session,
        rag_pipeline: Optional[RAGPipeline] = None,
        file_ingestion_service: Optional[FileIngestionService] = None,
    ):
        """Initialize Meeting RAG Bridge.

        Args:
            db_session: SQLAlchemy database session
            rag_pipeline: RAG pipeline instance (optional, created if not provided)
            file_ingestion_service: File ingestion service (optional)
        """
        self._db = db_session
        self._rag_pipeline = rag_pipeline
        self._file_ingestion_service = file_ingestion_service
        self._logger = logger.bind(service="meeting_rag_bridge")

    def on_transcription_complete(self, transcript_id: int) -> Optional[File]:
        """Handle transcription completion and trigger RAG ingestion.

        This is the main entry point called after a meeting transcript is complete.
        It creates the File/FileVersion entities and queues RAG processing.

        Workflow:
            1. Load Transcript and Meeting
            2. Validate transcript has content
            3. Check if File already exists (via Meeting.file_id)
            4. Compare content hash to detect changes
            5. Create or update File/FileVersion
            6. Update Meeting.file_id and rag_ingestion_status
            7. Trigger RAG pipeline (if configured)

        Args:
            transcript_id: ID of completed Transcript entity

        Returns:
            File entity created/updated, or None if skipped

        Raises:
            ValueError: If transcript not found
            RAGError: If file creation or RAG ingestion fails

        Example:
            >>> file = bridge.on_transcription_complete(transcript_id=456)
            >>> if file:
            ...     print(f"RAG ingestion queued for meeting {file.file_id}")
        """
        self._logger.info(
            "meeting_rag_bridge.transcription_complete",
            transcript_id=transcript_id,
        )

        # Load transcript and meeting
        transcript = (
            self._db.query(Transcript)
            .filter(Transcript.transcript_id == transcript_id)
            .first()
        )

        if not transcript:
            raise ValueError(f"Transcript not found: {transcript_id}")

        meeting = (
            self._db.query(Meeting)
            .filter(Meeting.meeting_id == transcript.meeting_id)
            .first()
        )

        if not meeting:
            raise ValueError(f"Meeting not found for transcript: {transcript.meeting_id}")

        self._logger = self._logger.bind(meeting_id=meeting.meeting_id)

        # Check if transcript is empty
        if not transcript.markdown_text or not transcript.markdown_text.strip():
            self._logger.warning(
                "meeting_rag_bridge.empty_transcript",
                transcript_id=transcript_id,
                meeting_id=meeting.meeting_id,
            )
            meeting.rag_ingestion_status = RAGIngestionStatus.SKIPPED
            self._db.commit()
            return None

        # Calculate content hash
        content_hash = self._calculate_content_hash(transcript.markdown_text)

        # Check if File already exists for this meeting
        existing_file = None
        if meeting.file_id:
            existing_file = (
                self._db.query(File).filter(File.file_id == meeting.file_id).first()
            )

        # If file exists, check if content changed
        if existing_file and existing_file.current_version_id:
            current_version = (
                self._db.query(FileVersion)
                .filter(FileVersion.version_id == existing_file.current_version_id)
                .first()
            )

            if current_version and current_version.content_hash == content_hash:
                self._logger.info(
                    "meeting_rag_bridge.no_changes",
                    meeting_id=meeting.meeting_id,
                    file_id=existing_file.file_id,
                    content_hash=content_hash[:16],
                )
                return existing_file

            # Content changed - create new version
            self._logger.info(
                "meeting_rag_bridge.content_changed",
                meeting_id=meeting.meeting_id,
                old_hash=current_version.content_hash[:16] if current_version else None,
                new_hash=content_hash[:16],
            )
            return self._create_new_version(existing_file, transcript, content_hash, meeting)

        # No existing file - create new
        return self._create_file_and_version(transcript, content_hash, meeting)

    def _create_file_and_version(
        self, transcript: Transcript, content_hash: str, meeting: Meeting
    ) -> File:
        """Create new File and FileVersion for transcript.

        Args:
            transcript: Transcript entity
            content_hash: SHA-256 hash of transcript content
            meeting: Meeting entity

        Returns:
            Created File entity
        """
        # Create File entity
        file = File(
            relative_path=f"meeting://{meeting.meeting_id}",
            mime_type="text/markdown",
            source_type=FileSourceType.MEETING,
            project_id=self._get_or_create_project_id(meeting.project_name),
            deleted=False,
        )
        self._db.add(file)
        self._db.flush()  # Get file_id

        # Create FileVersion
        file_size = len(transcript.markdown_text.encode("utf-8"))
        file_version = FileVersion(
            file_id=file.file_id,
            content_hash=content_hash,
            file_size_bytes=file_size,
            content_locator=f"transcript://{transcript.transcript_id}",
            is_current=True,
        )
        self._db.add(file_version)
        self._db.flush()  # Get version_id

        # Update File.current_version_id
        file.current_version_id = file_version.version_id

        # Link Meeting to File
        meeting.file_id = file.file_id
        meeting.rag_ingestion_status = RAGIngestionStatus.PENDING

        # Update Transcript metadata
        transcript.chunk_count = None  # Will be set after chunking
        transcript.embedding_generated_at = None

        self._db.commit()

        self._logger.info(
            "meeting_rag_bridge.file_created",
            meeting_id=meeting.meeting_id,
            file_id=file.file_id,
            version_id=file_version.version_id,
            content_hash=content_hash[:16],
            file_size_bytes=file_size,
        )

        # Trigger RAG pipeline if configured
        if self._rag_pipeline:
            self._trigger_rag_pipeline(file_version, transcript, meeting)

        return file

    def _create_new_version(
        self, file: File, transcript: Transcript, content_hash: str, meeting: Meeting
    ) -> File:
        """Create new FileVersion for changed transcript.

        Args:
            file: Existing File entity
            transcript: Updated Transcript entity
            content_hash: New content hash
            meeting: Meeting entity

        Returns:
            Updated File entity
        """
        # Mark old version as not current
        if file.current_version_id:
            old_version = (
                self._db.query(FileVersion)
                .filter(FileVersion.version_id == file.current_version_id)
                .first()
            )
            if old_version:
                old_version.is_current = False

        # Create new version
        file_size = len(transcript.markdown_text.encode("utf-8"))
        new_version = FileVersion(
            file_id=file.file_id,
            content_hash=content_hash,
            file_size_bytes=file_size,
            content_locator=f"transcript://{transcript.transcript_id}",
            is_current=True,
        )
        self._db.add(new_version)
        self._db.flush()

        # Update File
        file.current_version_id = new_version.version_id

        # Update Meeting status
        meeting.rag_ingestion_status = RAGIngestionStatus.PENDING

        # Reset Transcript RAG metadata
        transcript.chunk_count = None
        transcript.embedding_generated_at = None

        self._db.commit()

        self._logger.info(
            "meeting_rag_bridge.version_created",
            meeting_id=meeting.meeting_id,
            file_id=file.file_id,
            version_id=new_version.version_id,
            content_hash=content_hash[:16],
        )

        # Trigger RAG pipeline if configured
        if self._rag_pipeline:
            self._trigger_rag_pipeline(new_version, transcript, meeting)

        return file

    def _trigger_rag_pipeline(
        self, file_version: FileVersion, transcript: Transcript, meeting: Meeting
    ) -> None:
        """Trigger RAG pipeline processing for file version.

        Args:
            file_version: FileVersion to process
            transcript: Source Transcript
            meeting: Source Meeting
        """
        try:
            self._logger.info(
                "meeting_rag_bridge.triggering_rag",
                meeting_id=meeting.meeting_id,
                file_version_id=file_version.version_id,
            )

            # Update status to IN_PROGRESS
            meeting.rag_ingestion_status = RAGIngestionStatus.IN_PROGRESS
            self._db.commit()

            # Build processing rules for meeting transcript
            rules = {
                "pipeline_name": "meeting-rag-ingestion",
                "chunking_strategy": "MeetingChunker",
                "chunk_size": 1200,
                "chunk_overlap": 200,
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-large",
                "deepgram_response": transcript.deepgram_response,
                "artifacts": [
                    {
                        "kind": "summary",
                        "generator": "SummaryGenerator",
                        "llm_provider": "openai",
                        "llm_model": "gpt-4o",
                    }
                ],
            }

            # Execute RAG pipeline
            job_run = self._rag_pipeline.process_file(file_version, rules)

            # Update status based on result
            if job_run.status.value in ["success", "partial"]:
                meeting.rag_ingestion_status = RAGIngestionStatus.COMPLETED
                transcript.chunk_count = job_run.metrics.get("chunks_created", 0)
                transcript.embedding_generated_at = datetime.utcnow()
            else:
                meeting.rag_ingestion_status = RAGIngestionStatus.FAILED

            self._db.commit()

            self._logger.info(
                "meeting_rag_bridge.rag_complete",
                meeting_id=meeting.meeting_id,
                job_id=job_run.job_id,
                status=job_run.status.value,
                chunks_created=job_run.metrics.get("chunks_created", 0),
            )

        except Exception as e:
            self._logger.error(
                "meeting_rag_bridge.rag_failed",
                meeting_id=meeting.meeting_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            meeting.rag_ingestion_status = RAGIngestionStatus.FAILED
            self._db.commit()

    def update_rag_status(self, meeting_id: str, status: RAGIngestionStatus) -> None:
        """Update RAG ingestion status for meeting.

        This method allows external callers (e.g., RAG pipeline) to update
        the meeting's RAG status.

        Args:
            meeting_id: Meeting ID to update
            status: New RAG ingestion status

        Example:
            >>> bridge.update_rag_status("meeting_123", RAGIngestionStatus.COMPLETED)
        """
        meeting = (
            self._db.query(Meeting).filter(Meeting.meeting_id == meeting_id).first()
        )

        if not meeting:
            self._logger.warning(
                "meeting_rag_bridge.meeting_not_found",
                meeting_id=meeting_id,
            )
            return

        old_status = meeting.rag_ingestion_status
        meeting.rag_ingestion_status = status
        self._db.commit()

        self._logger.info(
            "meeting_rag_bridge.status_updated",
            meeting_id=meeting_id,
            old_status=old_status.value if old_status else None,
            new_status=status.value,
        )

    def _calculate_content_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content.

        Args:
            content: Content string to hash

        Returns:
            Hex-encoded SHA-256 hash (64 characters)
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_or_create_project_id(self, project_name: str) -> int:
        """Get or create project ID for project name.

        Args:
            project_name: Project name from meeting

        Returns:
            Project ID

        Note:
            This is a simplified implementation. In production, this would
            look up the Project entity by name and create if not exists.
            For now, returns a default project ID of 1.
        """
        # TODO: Implement proper Project lookup/creation
        # For now, return default project ID
        return 1
