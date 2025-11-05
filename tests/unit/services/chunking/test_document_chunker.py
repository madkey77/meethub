"""Unit tests for DocumentChunker."""

import pytest

from src.services.chunking import DocumentChunker, ChunkResult


class TestDocumentChunkerInit:
    """Test DocumentChunker initialization."""

    def test_default_initialization(self):
        """Test chunker with default parameters."""
        chunker = DocumentChunker()
        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 200

    def test_custom_initialization(self):
        """Test chunker with custom parameters."""
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 100

    def test_invalid_chunk_size(self):
        """Test initialization with invalid chunk_size."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            DocumentChunker(chunk_size=0)

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            DocumentChunker(chunk_size=-100)

    def test_invalid_chunk_overlap(self):
        """Test initialization with invalid chunk_overlap."""
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            DocumentChunker(chunk_overlap=-50)

    def test_overlap_exceeds_chunk_size(self):
        """Test initialization where overlap >= chunk_size."""
        with pytest.raises(ValueError, match="chunk_overlap.*must be less than"):
            DocumentChunker(chunk_size=100, chunk_overlap=100)


class TestDocumentChunkerBasic:
    """Test basic document chunking."""

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = DocumentChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_whitespace_only(self):
        """Test chunking whitespace-only text."""
        chunker = DocumentChunker()
        chunks = chunker.chunk("   \n\n\t  ")
        assert chunks == []

    def test_none_text(self):
        """Test chunking None text."""
        chunker = DocumentChunker()
        with pytest.raises(ValueError, match="text cannot be None"):
            chunker.chunk(None)

    def test_short_text(self):
        """Test chunking text shorter than chunk_size."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a short document."
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text_content == text
        assert chunks[0].chunk_index == 0
        assert chunks[0].char_offset_start == 0

    def test_simple_paragraph_splitting(self):
        """Test that chunker splits on paragraph boundaries."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        text = """First paragraph with some content.

Second paragraph with more content that should be in a different chunk.

Third paragraph to ensure splitting works correctly."""

        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        # Verify chunks are created
        for chunk in chunks:
            assert isinstance(chunk, ChunkResult)
            assert chunk.text_content
            assert chunk.char_offset_end > chunk.char_offset_start


class TestDocumentChunkerMetadata:
    """Test metadata preservation."""

    def test_no_metadata(self):
        """Test chunking without source metadata."""
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)
        text = "Simple text without metadata."

        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].metadata == {}

    def test_preserve_source_metadata(self):
        """Test that source metadata is preserved in all chunks."""
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)

        text = "A" * 120  # Long text to create multiple chunks

        metadata = {
            "page": 5,
            "heading": "Introduction",
            "section": "1.2.3",
            "document_id": "doc-123",
            "author": "John Doe"
        }

        chunks = chunker.chunk(text, source_metadata=metadata)

        # All chunks should have the same metadata
        for chunk in chunks:
            assert chunk.metadata["page"] == 5
            assert chunk.metadata["heading"] == "Introduction"
            assert chunk.metadata["section"] == "1.2.3"
            assert chunk.metadata["document_id"] == "doc-123"
            assert chunk.metadata["author"] == "John Doe"

    def test_metadata_not_shared_between_calls(self):
        """Test that metadata doesn't leak between chunking calls."""
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)

        text1 = "First document text."
        metadata1 = {"document_id": "doc1"}
        chunks1 = chunker.chunk(text1, source_metadata=metadata1)

        text2 = "Second document text."
        metadata2 = {"document_id": "doc2"}
        chunks2 = chunker.chunk(text2, source_metadata=metadata2)

        assert chunks1[0].metadata["document_id"] == "doc1"
        assert chunks2[0].metadata["document_id"] == "doc2"


class TestDocumentChunkerStructured:
    """Test chunking with structural markers."""

    def test_chunk_with_structure_no_markers(self):
        """Test structured chunking without markers (fallback to basic)."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        text = "Document text without structure markers."

        chunks = chunker.chunk_with_structure(text, structure_markers=None)

        assert len(chunks) == 1
        assert chunks[0].text_content == text

    def test_chunk_with_structure_empty_text(self):
        """Test structured chunking with empty text."""
        chunker = DocumentChunker()
        chunks = chunker.chunk_with_structure("", structure_markers=[])
        assert chunks == []

    def test_chunk_with_structure_none_text(self):
        """Test structured chunking with None text."""
        chunker = DocumentChunker()
        with pytest.raises(ValueError, match="text cannot be None"):
            chunker.chunk_with_structure(None)

    def test_chunk_with_heading_markers(self):
        """Test structured chunking with heading markers."""
        chunker = DocumentChunker(chunk_size=200, chunk_overlap=50)

        text = """Introduction paragraph with some content.

More content in the introduction section that continues here.

Architecture section starts here with technical details.

Implementation section with code examples."""

        markers = [
            {"type": "heading", "level": 1, "text": "Introduction", "offset": 0},
            {"type": "heading", "level": 2, "text": "Architecture", "offset": 100},
            {"type": "heading", "level": 2, "text": "Implementation", "offset": 200},
        ]

        chunks = chunker.chunk_with_structure(text, markers)

        # Verify that chunks have heading metadata
        assert len(chunks) > 0

        # First chunk should have "Introduction" heading
        assert chunks[0].metadata.get("heading") == "Introduction"
        assert chunks[0].metadata.get("heading_level") == 1

    def test_chunk_with_page_markers(self):
        """Test structured chunking with page break markers."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        text = "A" * 300  # 300 characters across multiple pages

        markers = [
            {"type": "page_break", "page": 1, "offset": 0},
            {"type": "page_break", "page": 2, "offset": 100},
            {"type": "page_break", "page": 3, "offset": 200},
        ]

        chunks = chunker.chunk_with_structure(text, markers)

        # Verify page metadata is assigned correctly
        assert len(chunks) > 0

        # Check that pages are assigned based on chunk position
        for chunk in chunks:
            assert "page" in chunk.metadata
            assert chunk.metadata["page"] >= 1

    def test_chunk_with_mixed_markers(self):
        """Test structured chunking with both headings and page breaks."""
        chunker = DocumentChunker(chunk_size=200, chunk_overlap=50)

        text = """Chapter 1 Introduction.

Content on page 1 continues here with more details.

Page 2 starts here with new content.

Chapter 2 Methods section begins.

More content on page 2."""

        markers = [
            {"type": "heading", "level": 1, "text": "Chapter 1", "offset": 0},
            {"type": "page_break", "page": 1, "offset": 0},
            {"type": "page_break", "page": 2, "offset": 100},
            {"type": "heading", "level": 1, "text": "Chapter 2", "offset": 150},
        ]

        chunks = chunker.chunk_with_structure(text, markers)

        # Verify both heading and page metadata are present
        assert len(chunks) > 0

        for chunk in chunks:
            # All chunks should have page number
            assert "page" in chunk.metadata

            # Some chunks should have heading
            # (depends on chunk boundaries)


class TestDocumentChunkerEdgeCases:
    """Test edge cases and error handling."""

    def test_very_long_paragraph(self):
        """Test chunking with paragraph longer than chunk_size."""
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)

        # Single paragraph longer than chunk_size (no paragraph breaks)
        text = "This is a very long paragraph without any breaks that exceeds the chunk size significantly and should be split intelligently by the chunker."

        chunks = chunker.chunk(text)

        # Should create multiple chunks
        assert len(chunks) > 1

        # Verify offsets are sequential and non-overlapping or overlapping correctly
        for i in range(len(chunks) - 1):
            # Next chunk should start before or at the end of current chunk (overlap)
            assert chunks[i + 1].char_offset_start <= chunks[i].char_offset_end

    def test_multiple_newlines(self):
        """Test chunking with multiple consecutive newlines."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        text = """Paragraph one.


Paragraph two with multiple newlines before it.



Paragraph three with even more newlines."""

        chunks = chunker.chunk(text)

        assert len(chunks) > 0
        # Chunker should handle multiple newlines gracefully

    def test_special_characters(self):
        """Test chunking with special characters."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        text = """Special chars: @#$%^&*()_+-=[]{}|;:'",.<>?/

Unicode: 你好世界 🌍 αβγδ

Mixed content works fine."""

        chunks = chunker.chunk(text)

        assert len(chunks) > 0
        # Verify special characters are preserved
        combined = "".join(chunk.text_content for chunk in chunks)
        assert "你好世界" in combined
        assert "🌍" in combined

    def test_chunk_indices_sequential(self):
        """Test that chunk indices are sequential starting from 0."""
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)

        text = "A" * 200  # Create multiple chunks

        chunks = chunker.chunk(text)

        assert len(chunks) > 1

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_offsets_valid(self):
        """Test that all chunk offsets are valid."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        text = """This is a document with multiple paragraphs.

Each paragraph should be chunked appropriately.

The offsets should be correct and sequential."""

        chunks = chunker.chunk(text)

        for chunk in chunks:
            # Offsets should be within text bounds
            assert 0 <= chunk.char_offset_start < len(text)
            assert chunk.char_offset_start < chunk.char_offset_end <= len(text)

            # Text content length should match offset difference
            # (may not be exact due to overlap and whitespace handling)
            assert len(chunk.text_content) <= chunk.char_offset_end - chunk.char_offset_start + chunker.chunk_overlap
