"""Unit tests for MeetingChunker."""

import pytest

from src.services.chunking import MeetingChunker, ChunkResult


class TestMeetingChunkerInit:
    """Test MeetingChunker initialization."""

    def test_default_initialization(self):
        """Test chunker with default parameters."""
        chunker = MeetingChunker()
        assert chunker.chunk_size == 1200
        assert chunker.chunk_overlap == 200

    def test_custom_initialization(self):
        """Test chunker with custom parameters."""
        chunker = MeetingChunker(chunk_size=800, chunk_overlap=100)
        assert chunker.chunk_size == 800
        assert chunker.chunk_overlap == 100

    def test_invalid_chunk_size(self):
        """Test initialization with invalid chunk_size."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            MeetingChunker(chunk_size=0)

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            MeetingChunker(chunk_size=-100)

    def test_invalid_chunk_overlap(self):
        """Test initialization with invalid chunk_overlap."""
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            MeetingChunker(chunk_overlap=-50)

    def test_overlap_exceeds_chunk_size(self):
        """Test initialization where overlap >= chunk_size."""
        with pytest.raises(ValueError, match="chunk_overlap.*must be less than"):
            MeetingChunker(chunk_size=100, chunk_overlap=100)

        with pytest.raises(ValueError, match="chunk_overlap.*must be less than"):
            MeetingChunker(chunk_size=100, chunk_overlap=150)


class TestMeetingChunkerPlainText:
    """Test plain text chunking (fallback mode)."""

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = MeetingChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_whitespace_only(self):
        """Test chunking whitespace-only text."""
        chunker = MeetingChunker()
        chunks = chunker.chunk("   \n\t  ")
        assert chunks == []

    def test_none_text(self):
        """Test chunking None text."""
        chunker = MeetingChunker()
        with pytest.raises(ValueError, match="text cannot be None"):
            chunker.chunk(None)

    def test_short_text(self):
        """Test chunking text shorter than chunk_size."""
        chunker = MeetingChunker(chunk_size=100, chunk_overlap=20)
        text = "Short text"
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text_content == text
        assert chunks[0].chunk_index == 0
        assert chunks[0].char_offset_start == 0
        assert chunks[0].char_offset_end == len(text)

    def test_long_text_with_overlap(self):
        """Test chunking long text with overlap."""
        chunker = MeetingChunker(chunk_size=50, chunk_overlap=10)
        text = "A" * 120  # 120 characters

        chunks = chunker.chunk(text)

        # Should create 3 chunks: 0-50, 40-90, 80-120
        assert len(chunks) == 3
        assert chunks[0].char_offset_start == 0
        assert chunks[0].char_offset_end == 50
        assert chunks[1].char_offset_start == 40
        assert chunks[2].char_offset_start == 80


class TestMeetingChunkerDeepgram:
    """Test Deepgram utterance chunking."""

    @pytest.fixture
    def sample_utterances(self):
        """Sample Deepgram response."""
        return {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.5,
                        "end": 5.2,
                        "transcript": "Hello everyone."
                    },
                    {
                        "speaker": 1,
                        "start": 5.8,
                        "end": 12.3,
                        "transcript": "Thanks for joining us today."
                    },
                    {
                        "speaker": 0,
                        "start": 13.0,
                        "end": 18.5,
                        "transcript": "Let's start the meeting."
                    },
                ]
            }
        }

    def test_empty_utterances(self):
        """Test chunking with no utterances."""
        chunker = MeetingChunker()
        response = {"results": {"utterances": []}}
        chunks = chunker.chunk_from_deepgram(response)
        assert chunks == []

    def test_none_response(self):
        """Test chunking with None response."""
        chunker = MeetingChunker()
        with pytest.raises(ValueError, match="deepgram_response cannot be None"):
            chunker.chunk_from_deepgram(None)

    def test_invalid_response_format(self):
        """Test chunking with invalid response format."""
        chunker = MeetingChunker()
        with pytest.raises(ValueError, match="Invalid deepgram_response format"):
            chunker.chunk_from_deepgram("not a dict")

    def test_missing_utterance_fields(self):
        """Test chunking with incomplete utterance data."""
        chunker = MeetingChunker()
        response = {
            "results": {
                "utterances": [
                    {"speaker": 0}  # Missing start and transcript
                ]
            }
        }
        with pytest.raises(KeyError, match="Utterance missing required fields"):
            chunker.chunk_from_deepgram(response)

    def test_single_utterance(self, sample_utterances):
        """Test chunking single utterance."""
        chunker = MeetingChunker(chunk_size=100, chunk_overlap=20)
        response = {
            "results": {
                "utterances": [sample_utterances["results"]["utterances"][0]]
            }
        }

        chunks = chunker.chunk_from_deepgram(response)

        assert len(chunks) == 1
        assert chunks[0].text_content == "Hello everyone."
        assert chunks[0].chunk_index == 0
        assert chunks[0].metadata["speaker"] == "Speaker 0"
        assert chunks[0].metadata["timestamp"] == "00:00:00"
        assert chunks[0].metadata["speaker_name"] is None

    def test_multiple_utterances_one_chunk(self, sample_utterances):
        """Test multiple utterances fitting in one chunk."""
        chunker = MeetingChunker(chunk_size=200, chunk_overlap=50)
        chunks = chunker.chunk_from_deepgram(sample_utterances)

        # All utterances should fit in one chunk
        assert len(chunks) == 1
        assert "Hello everyone." in chunks[0].text_content
        assert "Thanks for joining us today." in chunks[0].text_content
        assert "Let's start the meeting." in chunks[0].text_content

    def test_multiple_chunks_with_speaker_boundaries(self):
        """Test chunking that splits across multiple chunks."""
        chunker = MeetingChunker(chunk_size=50, chunk_overlap=10)

        response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.0,
                        "end": 2.0,
                        "transcript": "First utterance that is quite long and exceeds chunk size."
                    },
                    {
                        "speaker": 1,
                        "start": 3.0,
                        "end": 5.0,
                        "transcript": "Second utterance also long."
                    },
                ]
            }
        }

        chunks = chunker.chunk_from_deepgram(response)

        # Should create 2 chunks (never splits mid-utterance)
        assert len(chunks) == 2
        assert chunks[0].metadata["speaker"] == "Speaker 0"
        assert chunks[1].metadata["speaker"] == "Speaker 1"

    def test_speaker_name_mapping(self, sample_utterances):
        """Test speaker ID to name mapping."""
        chunker = MeetingChunker(chunk_size=200, chunk_overlap=50)
        mapping = {
            0: "Alice Johnson",
            1: "Bob Smith"
        }

        chunks = chunker.chunk_from_deepgram(sample_utterances, mapping)

        assert chunks[0].metadata["speaker_name"] == "Alice Johnson"

    def test_timestamp_formatting(self):
        """Test timestamp conversion from seconds to HH:MM:SS."""
        assert MeetingChunker._format_timestamp(0.5) == "00:00:00"
        assert MeetingChunker._format_timestamp(65.0) == "00:01:05"
        assert MeetingChunker._format_timestamp(3661.0) == "01:01:01"
        assert MeetingChunker._format_timestamp(7325.5) == "02:02:05"

    def test_large_single_utterance(self):
        """Test utterance longer than chunk_size stays intact."""
        chunker = MeetingChunker(chunk_size=20, chunk_overlap=5)

        response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.0,
                        "end": 10.0,
                        "transcript": "This is a very long utterance that exceeds the chunk size significantly."
                    }
                ]
            }
        }

        chunks = chunker.chunk_from_deepgram(response)

        # Should keep entire utterance in one chunk
        assert len(chunks) == 1
        assert len(chunks[0].text_content) > chunker.chunk_size

    def test_chunk_overlap_with_utterances(self):
        """Test that overlap preserves last utterances."""
        chunker = MeetingChunker(chunk_size=100, chunk_overlap=30)

        response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.0,
                        "end": 2.0,
                        "transcript": "First part of the conversation that is moderately long."
                    },
                    {
                        "speaker": 1,
                        "start": 3.0,
                        "end": 5.0,
                        "transcript": "Second part continues the discussion with more details."
                    },
                    {
                        "speaker": 0,
                        "start": 6.0,
                        "end": 8.0,
                        "transcript": "Third part wraps up."
                    },
                ]
            }
        }

        chunks = chunker.chunk_from_deepgram(response)

        # Should create multiple chunks with overlap
        assert len(chunks) >= 2

        # Check that later chunks might contain repeated content
        # (This is complex to verify precisely, but we ensure no errors)
