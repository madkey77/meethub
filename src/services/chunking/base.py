"""Abstract base class for chunking strategies.

This module defines the interface that all chunking strategies must implement.
Chunking strategies are responsible for breaking down large text documents into
smaller, semantically meaningful segments suitable for embedding and retrieval.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class ChunkResult:
    """Result of chunking operation containing text and metadata.

    Attributes:
        text_content: The actual text content of the chunk
        char_offset_start: Starting character position in the original document
        char_offset_end: Ending character position in the original document
        chunk_index: Sequential position of this chunk in the document (0-indexed)
        metadata: Additional context preserved from source (speaker, timestamp, etc.)

    Example:
        >>> chunk = ChunkResult(
        ...     text_content="Hello everyone, let's start the meeting.",
        ...     char_offset_start=0,
        ...     char_offset_end=41,
        ...     chunk_index=0,
        ...     metadata={"speaker": "Speaker 0", "timestamp": "00:00:05"}
        ... )
    """
    text_content: str
    char_offset_start: int
    char_offset_end: int
    chunk_index: int
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate chunk result fields."""
        if self.char_offset_end <= self.char_offset_start:
            raise ValueError(
                f"char_offset_end ({self.char_offset_end}) must be greater than "
                f"char_offset_start ({self.char_offset_start})"
            )
        if self.chunk_index < 0:
            raise ValueError(f"chunk_index must be non-negative, got {self.chunk_index}")
        if not self.text_content:
            raise ValueError("text_content cannot be empty")


class ChunkingStrategy(ABC):
    """Abstract base class for text chunking strategies.

    All chunking implementations must inherit from this class and implement
    the chunk() method. This ensures consistent interface across different
    chunking approaches (meeting transcripts, documents, etc.).

    Example:
        >>> class SimpleChunker(ChunkingStrategy):
        ...     def chunk(self, text: str, source_metadata: dict = None) -> List[ChunkResult]:
        ...         # Implementation here
        ...         pass
    """

    @abstractmethod
    def chunk(self, text: str, source_metadata: dict = None) -> List[ChunkResult]:
        """Break text into chunks with preserved metadata.

        Args:
            text: The input text to chunk. Can be empty (returns empty list).
            source_metadata: Optional metadata to preserve in chunks. Can include:
                - speaker information for meeting transcripts
                - page numbers for PDFs
                - section headings for structured documents
                - custom application-specific metadata

        Returns:
            List of ChunkResult objects, each containing:
                - text_content: chunk text
                - char_offset_start/end: position in original text
                - chunk_index: sequential position
                - metadata: preserved and chunk-specific metadata

            Returns empty list if input text is empty.

        Raises:
            ValueError: If text is None (empty string is allowed)
            NotImplementedError: If subclass doesn't implement this method

        Example:
            >>> strategy = SomeChunker()
            >>> chunks = strategy.chunk(
            ...     text="Long document text...",
            ...     source_metadata={"document_id": "doc123", "author": "Alice"}
            ... )
            >>> for chunk in chunks:
            ...     print(f"Chunk {chunk.chunk_index}: {chunk.text_content[:50]}...")
        """
        pass
