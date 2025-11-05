"""End-to-end tests for the complete meeting processing pipeline."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from src.models import Meeting, MeetingStatus
from src.services.meeting_processor import MeetingProcessor


@pytest.mark.e2e
class TestMeetingPipeline:
    """End-to-end tests for meeting processing pipeline."""

    @pytest.mark.asyncio
    async def test_complete_pipeline_with_mocks(self, test_db, sample_meeting_data, sample_transcription_data):
        """Test complete meeting processing pipeline with mocked external services.

        This test validates the entire workflow without requiring actual API access:
        1. Meeting detection (mocked)
        2. Recording download (mocked)
        3. Transcription (mocked)
        4. Drive upload (mocked)
        5. Database updates
        """
        # Create meeting in database
        meeting = Meeting(**sample_meeting_data)
        test_db.add(meeting)
        test_db.commit()

        # Mock external services
        with patch("src.services.meeting_processor.GoogleMeetService") as mock_meet, \
             patch("src.services.meeting_processor.TranscriptionService") as mock_transcription, \
             patch("src.services.meeting_processor.GoogleDriveService") as mock_drive:

            # Configure mocks
            mock_meet_instance = MagicMock()
            mock_meet_instance.check_recording_exists.return_value = {
                "drive_id": "test-drive-id",
                "url": "https://drive.google.com/file/test",
                "size_bytes": 1024 * 1024 * 10,  # 10 MB
            }
            mock_meet_instance.download_recording.return_value = Path("/tmp/test-audio.mp4")
            mock_meet.return_value = mock_meet_instance

            mock_transcription_instance = MagicMock()
            mock_transcription_instance.transcribe = AsyncMock(return_value=sample_transcription_data)
            mock_transcription_instance.format_as_markdown.return_value = "# Test Transcript\n\nContent here"
            mock_transcription_instance.cleanup_audio_file = MagicMock()
            mock_transcription.return_value = mock_transcription_instance

            mock_drive_instance = MagicMock()
            mock_drive_instance.upload_transcript.return_value = "test-transcript-drive-id"
            mock_drive.return_value = mock_drive_instance

            # Process meeting
            processor = MeetingProcessor()
            result = await processor.process_meeting(sample_meeting_data["meeting_id"], test_db)

            # Verify result
            assert result["success"] is True
            assert result["status"] == "completed"
            assert result["meeting_id"] == sample_meeting_data["meeting_id"]
            assert result["word_count"] == sample_transcription_data["word_count"]
            assert result["speaker_count"] == sample_transcription_data["speaker_count"]

            # Verify database state
            meeting = test_db.query(Meeting).filter(
                Meeting.meeting_id == sample_meeting_data["meeting_id"]
            ).first()
            assert meeting is not None
            assert meeting.status == MeetingStatus.COMPLETED

            # Verify transcript created
            assert meeting.transcript is not None
            assert meeting.transcript.word_count == sample_transcription_data["word_count"]
            assert meeting.transcript.speaker_count == sample_transcription_data["speaker_count"]
            assert meeting.transcript.drive_file_id == "test-transcript-drive-id"

            # Verify service calls
            mock_meet_instance.check_recording_exists.assert_called_once()
            mock_meet_instance.download_recording.assert_called_once()
            mock_transcription_instance.transcribe.assert_called_once()
            mock_drive_instance.upload_transcript.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_no_recording(self, test_db, sample_meeting_data):
        """Test pipeline when no recording is found."""
        # Create meeting in database
        meeting = Meeting(**sample_meeting_data)
        test_db.add(meeting)
        test_db.commit()

        # Mock GoogleMeetService to return no recording
        with patch("src.services.meeting_processor.GoogleMeetService") as mock_meet:
            mock_meet_instance = MagicMock()
            mock_meet_instance.check_recording_exists.return_value = None
            mock_meet.return_value = mock_meet_instance

            # Process meeting
            processor = MeetingProcessor()
            result = await processor.process_meeting(sample_meeting_data["meeting_id"], test_db)

            # Verify result
            assert result["success"] is False
            assert result["status"] == "skipped"
            assert result["reason"] == "no_recording"

            # Verify database state
            meeting = test_db.query(Meeting).filter(
                Meeting.meeting_id == sample_meeting_data["meeting_id"]
            ).first()
            assert meeting.status == MeetingStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_pipeline_transcription_failure(self, test_db, sample_meeting_data):
        """Test pipeline when transcription fails."""
        from src.utils.exceptions import TranscriptionError

        # Create meeting in database
        meeting = Meeting(**sample_meeting_data)
        test_db.add(meeting)
        test_db.commit()

        # Mock services with transcription failure
        with patch("src.services.meeting_processor.GoogleMeetService") as mock_meet, \
             patch("src.services.meeting_processor.TranscriptionService") as mock_transcription:

            mock_meet_instance = MagicMock()
            mock_meet_instance.check_recording_exists.return_value = {
                "drive_id": "test-drive-id",
                "url": "https://drive.google.com/file/test",
                "size_bytes": 1024 * 1024 * 10,
            }
            mock_meet_instance.download_recording.return_value = Path("/tmp/test-audio.mp4")
            mock_meet.return_value = mock_meet_instance

            mock_transcription_instance = MagicMock()
            mock_transcription_instance.transcribe = AsyncMock(
                side_effect=TranscriptionError("Transcription failed")
            )
            mock_transcription.return_value = mock_transcription_instance

            # Process meeting should raise error
            processor = MeetingProcessor()
            with pytest.raises(Exception):  # ProcessingError
                await processor.process_meeting(sample_meeting_data["meeting_id"], test_db)

            # Verify database state
            meeting = test_db.query(Meeting).filter(
                Meeting.meeting_id == sample_meeting_data["meeting_id"]
            ).first()
            assert meeting.status == MeetingStatus.FAILED


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-e2e"])
