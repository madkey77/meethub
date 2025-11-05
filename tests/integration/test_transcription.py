"""Integration tests for TranscriptionService with Deepgram API."""

import asyncio
import pytest
from pathlib import Path

from src.services.transcription import TranscriptionService
from src.utils.exceptions import AudioValidationError, DeepgramAPIError


@pytest.mark.integration
class TestTranscriptionService:
    """Integration tests for Deepgram transcription service."""

    def test_service_initialization(self):
        """Test that TranscriptionService initializes correctly."""
        service = TranscriptionService()
        assert service.client is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transcribe_with_sample_audio(self):
        """Test transcription with sample audio file.

        Note: This test requires:
        1. A sample audio file at tests/fixtures/sample.mp3
        2. Valid Deepgram API key configured
        """
        sample_audio = Path("tests/fixtures/sample.mp3")

        if not sample_audio.exists():
            pytest.skip("Sample audio file not found at tests/fixtures/sample.mp3")

        try:
            service = TranscriptionService()
            result = await service.transcribe(sample_audio)

            # Validate result structure
            assert "full_text" in result
            assert "utterances" in result
            assert "word_count" in result
            assert "speaker_count" in result
            assert "speakers" in result

            # Validate data types
            assert isinstance(result["full_text"], str)
            assert isinstance(result["utterances"], list)
            assert isinstance(result["word_count"], int)
            assert isinstance(result["speaker_count"], int)
            assert isinstance(result["speakers"], list)

            # Validate content
            assert result["word_count"] > 0, "Should have at least some words"
            assert result["speaker_count"] > 0, "Should have at least one speaker"

            # Validate utterances structure
            if result["utterances"]:
                utterance = result["utterances"][0]
                assert "speaker" in utterance
                assert "text" in utterance
                assert "start" in utterance
                assert "end" in utterance

        except DeepgramAPIError as e:
            pytest.skip(f"Deepgram API error (check API key): {e}")

    def test_validate_audio_valid(self):
        """Test audio validation with valid file."""
        sample_audio = Path("tests/fixtures/sample.mp3")

        if not sample_audio.exists():
            pytest.skip("Sample audio file not found")

        service = TranscriptionService()
        result = service.validate_audio(sample_audio)

        assert result["valid"] is True
        assert "size_bytes" in result
        assert "extension" in result

    def test_validate_audio_invalid_not_found(self):
        """Test audio validation with non-existent file."""
        service = TranscriptionService()

        with pytest.raises(AudioValidationError) as exc_info:
            service.validate_audio("nonexistent.mp3")

        assert "not found" in str(exc_info.value).lower()

    def test_format_as_markdown(self, sample_transcription_data):
        """Test markdown formatting."""
        service = TranscriptionService()

        markdown = service.format_as_markdown(
            transcription_data=sample_transcription_data,
            meeting_title="Test Meeting",
            meeting_date="2025-11-01",
            duration_minutes=60,
            project_name="TEST",
            participants=["Alice", "Bob"],
        )

        # Validate markdown contains expected elements
        assert "# Meeting: Test Meeting" in markdown
        assert "**Date**: 2025-11-01" in markdown
        assert "**Duration**: 60 minutes" in markdown
        assert "**Project**: TEST" in markdown
        assert "**Participants**: Alice, Bob" in markdown
        assert "## Transcript" in markdown
        assert "Speaker 0" in markdown or "Speaker 1" in markdown
        assert "[00:00]" in markdown  # Timestamp format


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-integration"])
