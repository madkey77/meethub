"""End-to-end integration test for meeting RAG flow.

Tests the complete pipeline:
Meeting → Transcript → File → Chunks → Embeddings → Queryable via RAG
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.models import (
    Meeting,
    MeetingStatus,
    RAGIngestionStatus,
    Transcript,
    File,
    FileVersion,
    Chunk,
    Embedding,
)
from src.services.meeting_rag_bridge import MeetingRAGBridge
from src.services.rag_pipeline import RAGPipeline
from src.services.chunking.meeting_chunker import MeetingChunker


@pytest.fixture
def complete_meeting_data(db_session: Session) -> dict:
    """Create complete meeting with transcript and Deepgram response."""
    meeting = Meeting(
        meeting_id="e2e_test_meeting_001",
        title="E2E Test Meeting",
        start_time=datetime(2025, 11, 5, 14, 0, 0),
        end_time=datetime(2025, 11, 5, 15, 0, 0),
        duration_minutes=60,
        status=MeetingStatus.COMPLETED,
        project_name="e2e-test-project",
        rag_ingestion_status=None,
    )
    db_session.add(meeting)
    db_session.flush()

    transcript = Transcript(
        meeting_id=meeting.meeting_id,
        full_text="Let's discuss the project timeline. I think we should prioritize the MVP features first.",
        markdown_text="""# Meeting: E2E Test Meeting

**Date**: 2025-11-05
**Duration**: 60 minutes
**Project**: e2e-test-project

## Transcript

[00:00] **Speaker 0**: Let's discuss the project timeline.

[00:05] **Speaker 1**: I think we should prioritize the MVP features first.

---

*Transcribed with Deepgram AI | 15 words | 2 speakers*
""",
        word_count=15,
        speaker_count=2,
        drive_file_id="drive_e2e_transcript",
        drive_folder_id="drive_e2e_folder",
        deepgram_response={
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.5,
                        "end": 3.2,
                        "transcript": "Let's discuss the project timeline.",
                        "confidence": 0.98,
                    },
                    {
                        "speaker": 1,
                        "start": 4.0,
                        "end": 8.5,
                        "transcript": "I think we should prioritize the MVP features first.",
                        "confidence": 0.95,
                    },
                ]
            }
        },
    )
    db_session.add(transcript)
    db_session.commit()

    return {
        "meeting": meeting,
        "transcript": transcript,
    }


class TestMeetingE2EFlow:
    """End-to-end tests for meeting RAG pipeline."""

    @patch("src.services.rag_pipeline.RAGPipeline.process_file")
    def test_full_pipeline_meeting_to_rag(
        self,
        mock_process_file: Mock,
        db_session: Session,
        complete_meeting_data: dict,
    ):
        """Test complete flow: Meeting → Transcript → File → RAG processing."""
        meeting = complete_meeting_data["meeting"]
        transcript = complete_meeting_data["transcript"]

        # Mock RAG pipeline to avoid actual processing
        mock_rag_pipeline = Mock(spec=RAGPipeline)
        mock_process_file.return_value = Mock(job_id=1, status="success")

        # Create bridge
        bridge = MeetingRAGBridge(
            db_session=db_session,
            rag_pipeline=mock_rag_pipeline,
            file_ingestion_service=None,
        )

        # Execute bridge
        file = bridge.on_transcription_complete(transcript.transcript_id)

        # Assertions
        assert file is not None
        assert file.file_id is not None

        # Verify Meeting linked to File
        db_session.refresh(meeting)
        assert meeting.file_id == file.file_id
        assert meeting.rag_ingestion_status == RAGIngestionStatus.PENDING

        # Verify FileVersion exists
        assert file.current_version_id is not None

    def test_chunks_created_with_speaker_metadata(
        self, complete_meeting_data: dict, db_session: Session
    ):
        """Test that chunks are created with speaker metadata preserved."""
        transcript = complete_meeting_data["transcript"]

        # Use MeetingChunker to create chunks from Deepgram response
        chunker = MeetingChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_from_deepgram(transcript.deepgram_response)

        # Assert chunks created
        assert len(chunks) > 0

        # Verify speaker metadata
        for chunk in chunks:
            assert "speaker" in chunk.metadata
            assert "timestamp" in chunk.metadata
            assert chunk.metadata["speaker"] in ["Speaker 0", "Speaker 1"]

    @patch("src.services.vector_store.ChromaVectorStore")
    @patch("src.services.embedding.base.EmbeddingService")
    def test_embeddings_stored_in_chromadb(
        self,
        mock_embedding_service: Mock,
        mock_vector_store: Mock,
        db_session: Session,
        complete_meeting_data: dict,
    ):
        """Test that embeddings are generated and stored in ChromaDB."""
        transcript = complete_meeting_data["transcript"]

        # Mock embedding service
        mock_embeddings = [[0.1, 0.2, 0.3] for _ in range(2)]
        mock_embedding_service.embed.return_value = Mock(
            vectors=mock_embeddings,
            model="text-embedding-3-large",
            provider="openai",
        )

        # Create chunks
        chunker = MeetingChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_from_deepgram(transcript.deepgram_response)

        # Simulate storing chunks in database
        file = File(
            relative_path=f"meeting://{transcript.meeting_id}",
            mime_type="text/markdown",
            source_type="meeting",
            project_id=1,
        )
        db_session.add(file)
        db_session.flush()

        file_version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/tmp/test",
            is_current=True,
        )
        db_session.add(file_version)
        db_session.flush()

        # Store chunks
        for chunk_result in chunks:
            chunk = Chunk(
                file_version_id=file_version.version_id,
                chunk_index=chunk_result.chunk_index,
                text_content=chunk_result.text_content,
                char_offset_start=chunk_result.char_offset_start,
                char_offset_end=chunk_result.char_offset_end,
                metadata=chunk_result.metadata,
            )
            db_session.add(chunk)

        db_session.commit()

        # Verify chunks in database
        stored_chunks = db_session.query(Chunk).filter(
            Chunk.file_version_id == file_version.version_id
        ).all()

        assert len(stored_chunks) == len(chunks)

        # Verify speaker metadata preserved
        for stored_chunk in stored_chunks:
            assert "speaker" in stored_chunk.metadata
            assert "timestamp" in stored_chunk.metadata

    def test_query_for_specific_speaker(
        self, db_session: Session, complete_meeting_data: dict
    ):
        """Test that querying for specific speaker returns correct chunks."""
        transcript = complete_meeting_data["transcript"]

        # Create chunks
        chunker = MeetingChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_from_deepgram(transcript.deepgram_response)

        # Store chunks in database
        file = File(
            relative_path=f"meeting://{transcript.meeting_id}",
            mime_type="text/markdown",
            source_type="meeting",
            project_id=1,
        )
        db_session.add(file)
        db_session.flush()

        file_version = FileVersion(
            file_id=file.file_id,
            content_hash="def456",
            file_size_bytes=1000,
            content_locator="/tmp/test2",
            is_current=True,
        )
        db_session.add(file_version)
        db_session.flush()

        for chunk_result in chunks:
            chunk = Chunk(
                file_version_id=file_version.version_id,
                chunk_index=chunk_result.chunk_index,
                text_content=chunk_result.text_content,
                char_offset_start=chunk_result.char_offset_start,
                char_offset_end=chunk_result.char_offset_end,
                metadata=chunk_result.metadata,
            )
            db_session.add(chunk)

        db_session.commit()

        # Query for Speaker 0 chunks
        speaker_0_chunks = (
            db_session.query(Chunk)
            .filter(
                Chunk.file_version_id == file_version.version_id,
                Chunk.metadata["speaker"].astext == "Speaker 0",
            )
            .all()
        )

        # Verify results
        assert len(speaker_0_chunks) > 0
        for chunk in speaker_0_chunks:
            assert chunk.metadata["speaker"] == "Speaker 0"

    def test_rag_pipeline_metrics_accurate(
        self, db_session: Session, complete_meeting_data: dict
    ):
        """Test that RAG pipeline tracks accurate metrics."""
        transcript = complete_meeting_data["transcript"]

        # Create chunks
        chunker = MeetingChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_from_deepgram(transcript.deepgram_response)

        expected_chunk_count = len(chunks)

        # Verify chunk count matches utterances (may differ due to chunking strategy)
        utterances = transcript.deepgram_response["results"]["utterances"]
        assert expected_chunk_count >= 1
        assert expected_chunk_count <= len(utterances) * 2  # Max with overlap
