"""Integration tests for Meeting→RAG bridge.

Tests that transcription completion triggers RAG ingestion correctly,
preserving the connection between Meeting and File entities.
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from src.models import (
    Meeting,
    MeetingStatus,
    RAGIngestionStatus,
    Transcript,
    File,
    FileVersion,
    FileSourceType,
)
from src.services.meeting_rag_bridge import MeetingRAGBridge
from src.services.file_ingestion import FileIngestionService
from src.services.rag_pipeline import RAGPipeline


@pytest.fixture
def meeting_with_transcript(db_session: Session) -> tuple[Meeting, Transcript]:
    """Create a meeting with completed transcript."""
    # Create meeting
    meeting = Meeting(
        meeting_id="test_meeting_001",
        title="Test Meeting for RAG Bridge",
        start_time=datetime(2025, 11, 5, 10, 0, 0),
        end_time=datetime(2025, 11, 5, 11, 0, 0),
        duration_minutes=60,
        status=MeetingStatus.COMPLETED,
        project_name="test-project",
        rag_ingestion_status=None,
    )
    db_session.add(meeting)
    db_session.flush()

    # Create transcript with Deepgram response
    transcript = Transcript(
        meeting_id=meeting.meeting_id,
        full_text="Hello everyone, let's start the meeting. Thanks for joining us today.",
        markdown_text="""# Meeting: Test Meeting for RAG Bridge

**Date**: 2025-11-05
**Duration**: 60 minutes
**Project**: test-project

## Transcript

[00:00] **Speaker 0**: Hello everyone, let's start the meeting.

[00:05] **Speaker 1**: Thanks for joining us today.

---

*Transcribed with Deepgram AI | 12 words | 2 speakers*
""",
        word_count=12,
        speaker_count=2,
        drive_file_id="drive_transcript_123",
        drive_folder_id="drive_folder_456",
        deepgram_response={
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.5,
                        "end": 5.2,
                        "transcript": "Hello everyone, let's start the meeting.",
                        "confidence": 0.98,
                    },
                    {
                        "speaker": 1,
                        "start": 5.8,
                        "end": 10.3,
                        "transcript": "Thanks for joining us today.",
                        "confidence": 0.95,
                    },
                ]
            }
        },
    )
    db_session.add(transcript)
    db_session.commit()

    return meeting, transcript


class TestMeetingRAGBridge:
    """Test suite for MeetingRAGBridge service."""

    def test_bridge_creates_file_for_transcript(
        self, db_session: Session, meeting_with_transcript: tuple[Meeting, Transcript]
    ):
        """Test that bridge creates File entity with source_type='meeting'."""
        meeting, transcript = meeting_with_transcript

        # Mock RAG pipeline (no actual processing)
        rag_pipeline = None

        # Create bridge service
        bridge = MeetingRAGBridge(
            db_session=db_session,
            rag_pipeline=rag_pipeline,
            file_ingestion_service=None,
        )

        # Execute bridge
        file = bridge.on_transcription_complete(transcript.transcript_id)

        # Assert File was created
        assert file is not None
        assert file.source_type == FileSourceType.MEETING
        assert file.mime_type == "text/markdown"
        assert file.relative_path == f"meeting://{meeting.meeting_id}"
        assert file.deleted is False

        # Assert Meeting.file_id is set
        db_session.refresh(meeting)
        assert meeting.file_id == file.file_id
        assert meeting.rag_ingestion_status == RAGIngestionStatus.PENDING

    def test_bridge_creates_file_version_with_content_hash(
        self, db_session: Session, meeting_with_transcript: tuple[Meeting, Transcript]
    ):
        """Test that FileVersion is created with transcript content hash."""
        meeting, transcript = meeting_with_transcript

        # Create bridge service
        bridge = MeetingRAGBridge(
            db_session=db_session,
            rag_pipeline=None,
            file_ingestion_service=None,
        )

        # Execute bridge
        file = bridge.on_transcription_complete(transcript.transcript_id)

        # Assert FileVersion was created
        assert file.current_version_id is not None
        file_version = (
            db_session.query(FileVersion)
            .filter(FileVersion.version_id == file.current_version_id)
            .first()
        )

        assert file_version is not None
        assert file_version.file_id == file.file_id
        assert file_version.is_current is True
        assert len(file_version.content_hash) == 64  # SHA-256 hex string
        assert file_version.file_size_bytes == len(transcript.markdown_text.encode("utf-8"))

    def test_bridge_status_transitions(
        self, db_session: Session, meeting_with_transcript: tuple[Meeting, Transcript]
    ):
        """Test RAG ingestion status transitions: pending→processing→completed."""
        meeting, transcript = meeting_with_transcript

        # Create bridge service
        bridge = MeetingRAGBridge(
            db_session=db_session,
            rag_pipeline=None,
            file_ingestion_service=None,
        )

        # Execute bridge
        file = bridge.on_transcription_complete(transcript.transcript_id)

        # Assert initial status is PENDING
        db_session.refresh(meeting)
        assert meeting.rag_ingestion_status == RAGIngestionStatus.PENDING

        # Simulate processing
        bridge.update_rag_status(meeting.meeting_id, RAGIngestionStatus.IN_PROGRESS)
        db_session.refresh(meeting)
        assert meeting.rag_ingestion_status == RAGIngestionStatus.IN_PROGRESS

        # Simulate completion
        bridge.update_rag_status(meeting.meeting_id, RAGIngestionStatus.COMPLETED)
        db_session.refresh(meeting)
        assert meeting.rag_ingestion_status == RAGIngestionStatus.COMPLETED

    def test_bridge_skips_if_file_exists_and_unchanged(
        self, db_session: Session, meeting_with_transcript: tuple[Meeting, Transcript]
    ):
        """Test that bridge skips re-ingestion if transcript hash unchanged."""
        meeting, transcript = meeting_with_transcript

        # Create bridge service
        bridge = MeetingRAGBridge(
            db_session=db_session,
            rag_pipeline=None,
            file_ingestion_service=None,
        )

        # First ingestion
        file1 = bridge.on_transcription_complete(transcript.transcript_id)
        version1_id = file1.current_version_id

        # Second ingestion (no changes to transcript)
        file2 = bridge.on_transcription_complete(transcript.transcript_id)

        # Assert same file returned
        assert file2.file_id == file1.file_id
        assert file2.current_version_id == version1_id

        # Assert only one version exists
        versions = (
            db_session.query(FileVersion)
            .filter(FileVersion.file_id == file1.file_id)
            .all()
        )
        assert len(versions) == 1

    def test_bridge_handles_transcript_not_found(self, db_session: Session):
        """Test that bridge handles missing transcript gracefully."""
        # Create bridge service
        bridge = MeetingRAGBridge(
            db_session=db_session,
            rag_pipeline=None,
            file_ingestion_service=None,
        )

        # Execute bridge with non-existent transcript
        with pytest.raises(ValueError, match="Transcript not found"):
            bridge.on_transcription_complete(999999)

    def test_bridge_handles_empty_transcript(
        self, db_session: Session, meeting_with_transcript: tuple[Meeting, Transcript]
    ):
        """Test that bridge skips transcripts with no content."""
        meeting, transcript = meeting_with_transcript

        # Set transcript to empty
        transcript.markdown_text = ""
        db_session.commit()

        # Create bridge service
        bridge = MeetingRAGBridge(
            db_session=db_session,
            rag_pipeline=None,
            file_ingestion_service=None,
        )

        # Execute bridge - should skip and return None
        file = bridge.on_transcription_complete(transcript.transcript_id)

        assert file is None
        db_session.refresh(meeting)
        assert meeting.rag_ingestion_status == RAGIngestionStatus.SKIPPED
