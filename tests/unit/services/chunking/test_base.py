"""Unit tests for chunking base classes."""

import pytest

from src.services.chunking.base import ChunkResult, ChunkingStrategy


class TestChunkResult:
    """Test ChunkResult dataclass."""

    def test_valid_chunk_result(self):
        """Test creating a valid ChunkResult."""
        chunk = ChunkResult(
            text_content="Hello world",
            char_offset_start=0,
            char_offset_end=11,
            chunk_index=0,
            metadata={"speaker": "Alice"}
        )

        assert chunk.text_content == "Hello world"
        assert chunk.char_offset_start == 0
        assert chunk.char_offset_end == 11
        assert chunk.chunk_index == 0
        assert chunk.metadata == {"speaker": "Alice"}

    def test_default_metadata(self):
        """Test ChunkResult with default empty metadata."""
        chunk = ChunkResult(
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
            chunk_index=0
        )

        assert chunk.metadata == {}

    def test_invalid_offsets_equal(self):
        """Test ChunkResult with equal start and end offsets."""
        with pytest.raises(ValueError, match="char_offset_end.*must be greater"):
            ChunkResult(
                text_content="Test",
                char_offset_start=5,
                char_offset_end=5,
                chunk_index=0
            )

    def test_invalid_offsets_reversed(self):
        """Test ChunkResult with end before start."""
        with pytest.raises(ValueError, match="char_offset_end.*must be greater"):
            ChunkResult(
                text_content="Test",
                char_offset_start=10,
                char_offset_end=5,
                chunk_index=0
            )

    def test_negative_chunk_index(self):
        """Test ChunkResult with negative chunk_index."""
        with pytest.raises(ValueError, match="chunk_index must be non-negative"):
            ChunkResult(
                text_content="Test",
                char_offset_start=0,
                char_offset_end=4,
                chunk_index=-1
            )

    def test_empty_text_content(self):
        """Test ChunkResult with empty text_content."""
        with pytest.raises(ValueError, match="text_content cannot be empty"):
            ChunkResult(
                text_content="",
                char_offset_start=0,
                char_offset_end=4,
                chunk_index=0
            )

    def test_metadata_independence(self):
        """Test that metadata is independent between instances."""
        metadata1 = {"key": "value1"}
        chunk1 = ChunkResult(
            text_content="Chunk 1",
            char_offset_start=0,
            char_offset_end=7,
            chunk_index=0,
            metadata=metadata1
        )

        metadata2 = {"key": "value2"}
        chunk2 = ChunkResult(
            text_content="Chunk 2",
            char_offset_start=7,
            char_offset_end=14,
            chunk_index=1,
            metadata=metadata2
        )

        assert chunk1.metadata["key"] == "value1"
        assert chunk2.metadata["key"] == "value2"

        # Modifying one shouldn't affect the other
        chunk1.metadata["new_key"] = "new_value"
        assert "new_key" not in chunk2.metadata


class TestChunkingStrategy:
    """Test ChunkingStrategy abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that ChunkingStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ChunkingStrategy()

    def test_must_implement_chunk_method(self):
        """Test that subclasses must implement chunk() method."""
        class IncompleteChunker(ChunkingStrategy):
            pass

        with pytest.raises(TypeError):
            IncompleteChunker()

    def test_concrete_implementation(self):
        """Test creating a concrete implementation."""
        class SimpleChunker(ChunkingStrategy):
            def chunk(self, text: str, source_metadata: dict = None):
                # Simple implementation: return entire text as one chunk
                if not text:
                    return []

                return [
                    ChunkResult(
                        text_content=text,
                        char_offset_start=0,
                        char_offset_end=len(text),
                        chunk_index=0,
                        metadata=source_metadata or {}
                    )
                ]

        chunker = SimpleChunker()
        chunks = chunker.chunk("Test text")

        assert len(chunks) == 1
        assert chunks[0].text_content == "Test text"

    def test_abstract_method_signature(self):
        """Test that chunk method has correct signature."""
        class TestChunker(ChunkingStrategy):
            def chunk(self, text: str, source_metadata: dict = None):
                return []

        chunker = TestChunker()

        # Should accept text only
        result1 = chunker.chunk("text")
        assert result1 == []

        # Should accept text and metadata
        result2 = chunker.chunk("text", {"key": "value"})
        assert result2 == []
