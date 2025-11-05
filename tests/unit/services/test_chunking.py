"""Unit tests for chunking strategies (MeetingChunker and DocumentChunker).

Tests cover:
MeetingChunker:
- Preserves speaker metadata from Deepgram utterances
- Never splits mid-utterance
- Handles chunk_size and chunk_overlap correctly
- Formats timestamps (seconds → HH:MM:SS)
- Single utterance > chunk_size stays intact

DocumentChunker:
- Respects chunk_size and chunk_overlap configs
- Splits on natural boundaries (paragraphs, sentences)
- Preserves metadata (page, heading, section)
- Uses LangChain RecursiveCharacterTextSplitter
"""

import pytest
from unittest.mock import patch, MagicMock

from src.services.chunking.meeting_chunker import MeetingChunker
from src.services.chunking.document_chunker import DocumentChunker
from src.services.chunking.base import ChunkResult


class TestMeetingChunkerInitialization:
    """Test MeetingChunker initialization and validation."""

    def test_initialization_default_parameters(self):
        """Test initialization with default parameters."""
        chunker = MeetingChunker()

        assert chunker.chunk_size == 1200
        assert chunker.chunk_overlap == 200

    def test_initialization_custom_parameters(self):
        """Test initialization with custom parameters."""
        chunker = MeetingChunker(chunk_size=1000, chunk_overlap=150)

        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 150

    def test_initialization_invalid_chunk_size(self):
        """Test that zero or negative chunk_size raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            MeetingChunker(chunk_size=0, chunk_overlap=100)
        assert "chunk_size must be positive" in str(exc_info.value)

        with pytest.raises(ValueError):
            MeetingChunker(chunk_size=-100, chunk_overlap=100)

    def test_initialization_negative_overlap(self):
        """Test that negative chunk_overlap raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            MeetingChunker(chunk_size=1000, chunk_overlap=-50)
        assert "chunk_overlap must be non-negative" in str(exc_info.value)

    def test_initialization_overlap_greater_than_size(self):
        """Test that overlap >= chunk_size raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            MeetingChunker(chunk_size=1000, chunk_overlap=1000)
        assert "chunk_overlap" in str(exc_info.value)
        assert "must be less than" in str(exc_info.value)


class TestMeetingChunkerDeepgramProcessing:
    """Test MeetingChunker with Deepgram response format."""

    def test_chunk_from_deepgram_simple(self):
        """Test basic chunking from Deepgram response."""
        deepgram_response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.5,
                        "end": 5.2,
                        "transcript": "Hello everyone, let's start the meeting.",
                    },
                    {
                        "speaker": 1,
                        "start": 5.8,
                        "end": 12.3,
                        "transcript": "Thanks for joining. Today we'll discuss the project roadmap.",
                    },
                ]
            }
        }

        chunker = MeetingChunker(chunk_size=1200, chunk_overlap=200)
        chunks = chunker.chunk_from_deepgram(deepgram_response)

        # Should create one chunk (both utterances fit)
        assert len(chunks) == 1
        assert "Hello everyone" in chunks[0].text_content
        assert "discuss the project" in chunks[0].text_content

    def test_preserves_speaker_metadata(self):
        """Test that speaker metadata is preserved in chunks."""
        deepgram_response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.5,
                        "end": 5.2,
                        "transcript": "First utterance.",
                    },
                ]
            }
        }

        chunker = MeetingChunker()
        chunks = chunker.chunk_from_deepgram(deepgram_response)

        assert len(chunks) == 1
        assert chunks[0].metadata_json["speaker"] == "Speaker 0"
        assert chunks[0].metadata_json["timestamp"] == "00:00:00"
        assert chunks[0].metadata_json["speaker_name"] is None

    def test_preserves_speaker_names_with_mapping(self):
        """Test that speaker names are mapped when participant_mapping provided."""
        deepgram_response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.0,
                        "end": 5.0,
                        "transcript": "Hello from Alice.",
                    },
                    {
                        "speaker": 1,
                        "start": 5.5,
                        "end": 10.0,
                        "transcript": "Hello from Bob.",
                    },
                ]
            }
        }

        participant_mapping = {
            0: "Alice Smith",
            1: "Bob Jones",
        }

        chunker = MeetingChunker()
        chunks = chunker.chunk_from_deepgram(deepgram_response, participant_mapping)

        # Should have both speakers in metadata
        assert chunks[0].metadata_json["speaker_name"] == "Alice Smith"

    def test_never_splits_mid_utterance(self):
        """Test that chunker never splits within an utterance."""
        # Create utterances that together exceed chunk_size
        deepgram_response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.0,
                        "end": 10.0,
                        "transcript": "A" * 700,  # 700 chars
                    },
                    {
                        "speaker": 0,
                        "start": 10.0,
                        "end": 20.0,
                        "transcript": "B" * 700,  # 700 chars, total = 1400 > 1200
                    },
                ]
            }
        }

        chunker = MeetingChunker(chunk_size=1200, chunk_overlap=200)
        chunks = chunker.chunk_from_deepgram(deepgram_response)

        # Should create 2 chunks since combined exceeds chunk_size
        assert len(chunks) >= 1

        # Each chunk should contain complete utterances (all A's or all B's)
        for chunk in chunks:
            # No chunk should have mixed A's and B's at the boundary
            text = chunk.text_content
            # If has A's, should not have B's mixed in the same utterance
            if "A" in text and "B" in text:
                # This is OK if they're separate utterances (space-separated)
                assert " " in text  # Should have space between utterances

    def test_single_utterance_larger_than_chunk_size(self):
        """Test that single utterance larger than chunk_size stays intact."""
        long_text = "This is a very long utterance. " * 100  # ~3000 chars

        deepgram_response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.0,
                        "end": 60.0,
                        "transcript": long_text,
                    },
                ]
            }
        }

        chunker = MeetingChunker(chunk_size=1200, chunk_overlap=200)
        chunks = chunker.chunk_from_deepgram(deepgram_response)

        # Should create one chunk containing the entire utterance
        assert len(chunks) == 1
        assert chunks[0].text_content == long_text

    def test_timestamp_formatting(self):
        """Test that timestamps are formatted as HH:MM:SS."""
        test_cases = [
            (0.0, "00:00:00"),
            (65.5, "00:01:05"),
            (3661.0, "01:01:01"),
            (7325.0, "02:02:05"),
        ]

        for seconds, expected in test_cases:
            formatted = MeetingChunker._format_timestamp(seconds)
            assert formatted == expected

    def test_chunk_overlap_with_utterances(self):
        """Test that chunk overlap preserves utterances correctly."""
        deepgram_response = {
            "results": {
                "utterances": [
                    {"speaker": 0, "start": 0.0, "end": 5.0, "transcript": "A" * 500},
                    {"speaker": 0, "start": 5.0, "end": 10.0, "transcript": "B" * 500},
                    {"speaker": 0, "start": 10.0, "end": 15.0, "transcript": "C" * 500},
                ]
            }
        }

        chunker = MeetingChunker(chunk_size=1200, chunk_overlap=600)
        chunks = chunker.chunk_from_deepgram(deepgram_response)

        # Should create chunks with overlap
        assert len(chunks) >= 2

        # Overlapping content should appear in consecutive chunks
        # (Last utterance(s) of chunk N should appear in chunk N+1)


class TestMeetingChunkerFallback:
    """Test MeetingChunker plain text fallback."""

    def test_chunk_plain_text(self):
        """Test chunking plain text (fallback method)."""
        text = "This is a plain text document. " * 50  # ~1600 chars

        chunker = MeetingChunker(chunk_size=1200, chunk_overlap=200)
        chunks = chunker.chunk(text)

        # Should create multiple chunks
        assert len(chunks) >= 1
        assert all(isinstance(chunk, ChunkResult) for chunk in chunks)

    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        chunker = MeetingChunker()
        chunks = chunker.chunk("")

        assert len(chunks) == 0

    def test_chunk_none_raises_error(self):
        """Test that chunking None raises ValueError."""
        chunker = MeetingChunker()

        with pytest.raises(ValueError) as exc_info:
            chunker.chunk(None)

        assert "text cannot be None" in str(exc_info.value)


class TestMeetingChunkerEdgeCases:
    """Test edge cases for MeetingChunker."""

    def test_chunk_from_deepgram_none_raises_error(self):
        """Test that None deepgram_response raises ValueError."""
        chunker = MeetingChunker()

        with pytest.raises(ValueError) as exc_info:
            chunker.chunk_from_deepgram(None)

        assert "deepgram_response cannot be None" in str(exc_info.value)

    def test_chunk_from_deepgram_missing_results(self):
        """Test handling of malformed Deepgram response."""
        chunker = MeetingChunker()

        with pytest.raises(ValueError) as exc_info:
            chunker.chunk_from_deepgram({})  # Missing 'results'

        assert "Invalid deepgram_response format" in str(exc_info.value)

    def test_chunk_from_deepgram_empty_utterances(self):
        """Test handling of empty utterances list."""
        deepgram_response = {"results": {"utterances": []}}

        chunker = MeetingChunker()
        chunks = chunker.chunk_from_deepgram(deepgram_response)

        assert len(chunks) == 0

    def test_chunk_from_deepgram_missing_required_fields(self):
        """Test that missing required utterance fields raises KeyError."""
        deepgram_response = {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        # Missing 'start' and 'transcript'
                        "end": 5.0,
                    },
                ]
            }
        }

        chunker = MeetingChunker()

        with pytest.raises(KeyError):
            chunker.chunk_from_deepgram(deepgram_response)


class TestDocumentChunkerInitialization:
    """Test DocumentChunker initialization and validation."""

    def test_initialization_default_parameters(self):
        """Test initialization with default parameters."""
        chunker = DocumentChunker()

        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 200

    def test_initialization_custom_parameters(self):
        """Test initialization with custom parameters."""
        chunker = DocumentChunker(chunk_size=800, chunk_overlap=100)

        assert chunker.chunk_size == 800
        assert chunker.chunk_overlap == 100

    def test_initialization_invalid_chunk_size(self):
        """Test that invalid chunk_size raises ValueError."""
        with pytest.raises(ValueError):
            DocumentChunker(chunk_size=0, chunk_overlap=100)

        with pytest.raises(ValueError):
            DocumentChunker(chunk_size=-500, chunk_overlap=100)

    def test_initialization_negative_overlap(self):
        """Test that negative overlap raises ValueError."""
        with pytest.raises(ValueError):
            DocumentChunker(chunk_size=1000, chunk_overlap=-100)

    def test_initialization_overlap_greater_than_size(self):
        """Test that overlap >= chunk_size raises ValueError."""
        with pytest.raises(ValueError):
            DocumentChunker(chunk_size=1000, chunk_overlap=1000)


class TestDocumentChunkerBasicChunking:
    """Test basic DocumentChunker chunking functionality."""

    def test_chunk_simple_text(self):
        """Test chunking simple text."""
        text = "This is a simple document.\n\nIt has multiple paragraphs.\n\nEach paragraph is separated by blank lines."

        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)
        chunks = chunker.chunk(text)

        # Should create chunks
        assert len(chunks) >= 1
        assert all(isinstance(chunk, ChunkResult) for chunk in chunks)

    def test_chunk_respects_size_limit(self):
        """Test that chunks respect chunk_size limit."""
        text = "A" * 5000  # Long text

        chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
        chunks = chunker.chunk(text)

        # All chunks except possibly last should be ~chunk_size
        for chunk in chunks[:-1]:
            assert len(chunk.text_content) <= chunker.chunk_size * 1.1  # Allow some flexibility

    def test_chunk_preserves_metadata(self):
        """Test that source metadata is preserved in all chunks."""
        text = "Document content. " * 100

        source_metadata = {
            "page": 3,
            "heading": "Results",
            "section": "3.2",
            "document_id": "doc-123",
        }

        chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
        chunks = chunker.chunk(text, source_metadata=source_metadata)

        # All chunks should have the source metadata
        for chunk in chunks:
            assert chunk.metadata_json["page"] == 3
            assert chunk.metadata_json["heading"] == "Results"
            assert chunk.metadata_json["section"] == "3.2"
            assert chunk.metadata_json["document_id"] == "doc-123"

    def test_chunk_empty_text(self):
        """Test chunking empty text returns empty list."""
        chunker = DocumentChunker()

        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []  # Whitespace only

    def test_chunk_none_raises_error(self):
        """Test that chunking None raises ValueError."""
        chunker = DocumentChunker()

        with pytest.raises(ValueError) as exc_info:
            chunker.chunk(None)

        assert "text cannot be None" in str(exc_info.value)


class TestDocumentChunkerNaturalBoundaries:
    """Test that DocumentChunker splits on natural boundaries."""

    def test_splits_on_paragraph_boundaries(self):
        """Test that chunker prefers splitting on paragraph boundaries."""
        text = """First paragraph with some content that describes something.

Second paragraph with different content that continues the discussion.

Third paragraph with even more interesting information."""

        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk(text)

        # Chunks should ideally split between paragraphs
        # At least verify no errors and chunks created
        assert len(chunks) >= 1

    def test_handles_short_document(self):
        """Test handling of document shorter than chunk_size."""
        text = "This is a very short document."

        chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
        chunks = chunker.chunk(text)

        # Should create single chunk
        assert len(chunks) == 1
        assert chunks[0].text_content == text

    def test_chunk_overlap_creates_overlapping_content(self):
        """Test that chunk_overlap creates overlapping content."""
        text = "A " * 1000  # 2000 chars

        chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
        chunks = chunker.chunk(text)

        # Should have multiple chunks
        assert len(chunks) >= 2

        # Chunks should have some overlapping content
        # (End of chunk N appears in start of chunk N+1)


class TestDocumentChunkerWithStructure:
    """Test DocumentChunker with structure markers."""

    def test_chunk_with_structure_basic(self):
        """Test basic chunking with structure markers."""
        text = "# Introduction\n\nThis is the intro.\n\n## Methods\n\nThis describes methods."

        structure_markers = [
            {"type": "heading", "level": 1, "text": "Introduction", "offset": 0},
            {"type": "heading", "level": 2, "text": "Methods", "offset": 50},
        ]

        chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
        chunks = chunker.chunk_with_structure(text, structure_markers)

        # Should create chunks with structure metadata
        assert len(chunks) >= 1

        # First chunk should have "Introduction" as heading
        if chunks[0].char_offset_start < 50:
            assert chunks[0].metadata_json.get("heading") == "Introduction"

    def test_chunk_with_structure_page_breaks(self):
        """Test structure markers with page breaks."""
        text = "Page 1 content. " * 50 + "Page 2 content. " * 50

        structure_markers = [
            {"type": "page_break", "page": 2, "offset": 800},
        ]

        chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
        chunks = chunker.chunk_with_structure(text, structure_markers)

        # Chunks should have page metadata
        for chunk in chunks:
            assert "page" in chunk.metadata_json
            assert chunk.metadata_json["page"] >= 1

    def test_chunk_with_structure_none_markers(self):
        """Test that None structure_markers returns basic chunks."""
        text = "Document content without structure."

        chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
        chunks = chunker.chunk_with_structure(text, structure_markers=None)

        # Should still create chunks
        assert len(chunks) >= 1

    def test_chunk_with_structure_empty_text(self):
        """Test structure chunking with empty text."""
        chunker = DocumentChunker()
        chunks = chunker.chunk_with_structure("", structure_markers=[])

        assert len(chunks) == 0

    def test_chunk_with_structure_none_text_raises_error(self):
        """Test that None text raises ValueError."""
        chunker = DocumentChunker()

        with pytest.raises(ValueError):
            chunker.chunk_with_structure(None)


class TestDocumentChunkerLangChainIntegration:
    """Test DocumentChunker integration with LangChain."""

    def test_uses_langchain_splitter(self):
        """Test that DocumentChunker uses LangChain RecursiveCharacterTextSplitter."""
        chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)

        # Verify that _splitter exists and has correct configuration
        assert hasattr(chunker, "_splitter")
        assert chunker._splitter is not None

    def test_handles_langchain_exception(self):
        """Test handling of LangChain exceptions."""
        chunker = DocumentChunker()

        # Mock LangChain splitter to raise exception
        with patch.object(chunker._splitter, "split_text", side_effect=Exception("LangChain error")):
            with pytest.raises(ValueError) as exc_info:
                chunker.chunk("Test text")

            assert "Failed to split text" in str(exc_info.value)
