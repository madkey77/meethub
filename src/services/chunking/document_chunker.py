"""Document chunking strategy using LangChain's RecursiveCharacterTextSplitter.

This module implements chunking for general documents (PDFs, DOCX, markdown, etc.)
using LangChain's battle-tested text splitting approach. It intelligently splits
on paragraph, sentence, and word boundaries while preserving structural metadata.
"""

from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.services.chunking.base import ChunkingStrategy, ChunkResult


class DocumentChunker(ChunkingStrategy):
    """Chunks documents using LangChain's recursive character splitting.

    This chunker uses LangChain's RecursiveCharacterTextSplitter which tries
    to split on natural boundaries in this order:
        1. Paragraph boundaries (\\n\\n)
        2. Single newlines (\\n)
        3. Spaces
        4. Characters (as last resort)

    This approach preserves semantic coherence better than fixed-size splitting.
    It's suitable for PDFs, Word documents, markdown files, and other structured
    text documents.

    Key Features:
        - Recursive splitting strategy (paragraphs → sentences → words)
        - Preserves document structure metadata (page, heading, section)
        - Configurable chunk size and overlap
        - Handles edge cases (empty text, short documents)

    Args:
        chunk_size: Target maximum characters per chunk (default: 1000)
        chunk_overlap: Number of overlapping characters between chunks (default: 200)

    Example:
        >>> document_text = '''
        ... # Introduction
        ...
        ... This is the first paragraph with some important content.
        ...
        ... This is the second paragraph continuing the discussion.
        ...
        ... ## Architecture
        ...
        ... Here we describe the technical architecture.
        ... '''
        >>> chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
        >>> chunks = chunker.chunk(
        ...     text=document_text,
        ...     source_metadata={
        ...         "page": 1,
        ...         "heading": "Introduction",
        ...         "document_id": "doc123"
        ...     }
        ... )
        >>> print(f"Created {len(chunks)} chunks")
        >>> print(chunks[0].metadata)
        {'page': 1, 'heading': 'Introduction', 'document_id': 'doc123'}
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """Initialize the document chunker.

        Args:
            chunk_size: Target maximum characters per chunk. Defaults to 1000
                which balances context preservation with embedding model limits.
            chunk_overlap: Number of overlapping characters between consecutive
                chunks. Defaults to 200 to maintain semantic continuity.

        Raises:
            ValueError: If chunk_size <= 0 or chunk_overlap < 0 or
                chunk_overlap >= chunk_size
        """
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be non-negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be less than "
                f"chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Initialize LangChain's RecursiveCharacterTextSplitter
        # Default separators: ["\n\n", "\n", " ", ""]
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def chunk(self, text: str, source_metadata: dict = None) -> List[ChunkResult]:
        """Break document text into semantic chunks with metadata.

        This method uses LangChain's recursive splitting approach which tries
        to split on natural boundaries (paragraphs, then sentences, then words).
        This preserves semantic coherence better than fixed-size splitting.

        Args:
            text: The document text to chunk. Can be from PDF, DOCX, markdown,
                plain text, etc. Empty or whitespace-only text returns empty list.
            source_metadata: Optional metadata to preserve in all chunks:
                - page: int - Page number for PDFs
                - heading: str - Current section heading for structured docs
                - section: str - Section number (e.g., "2.3.1")
                - document_id: str - Source document identifier
                - document_type: str - File type (pdf, docx, markdown, etc.)
                - Custom fields as needed

        Returns:
            List of ChunkResult objects, each containing:
                - text_content: The chunk text
                - char_offset_start: Starting position in original text
                - char_offset_end: Ending position in original text
                - chunk_index: Sequential position (0-indexed)
                - metadata: Source metadata plus any chunk-specific metadata

            Returns empty list if input text is empty or whitespace-only.

        Raises:
            ValueError: If text is None

        Example:
            >>> chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
            >>> chunks = chunker.chunk(
            ...     text="Long document text with multiple paragraphs...",
            ...     source_metadata={
            ...         "page": 3,
            ...         "heading": "Results",
            ...         "section": "3.2",
            ...         "document_id": "research-paper-2024"
            ...     }
            ... )
            >>> for chunk in chunks:
            ...     print(f"Chunk {chunk.chunk_index} at offset {chunk.char_offset_start}")
            ...     print(f"  Page: {chunk.metadata.get('page')}")
            ...     print(f"  Section: {chunk.metadata.get('section')}")
        """
        if text is None:
            raise ValueError("text cannot be None")

        # Handle empty text
        if not text or not text.strip():
            return []

        # Use LangChain splitter to create text chunks
        try:
            text_chunks = self._splitter.split_text(text)
        except Exception as e:
            raise ValueError(f"Failed to split text: {e}")

        # Handle case where text is shorter than chunk_size
        if not text_chunks:
            return []

        # Convert LangChain chunks to ChunkResult objects with offsets
        chunks = []
        char_offset = 0

        for chunk_index, chunk_text in enumerate(text_chunks):
            # Find the chunk in the original text to get accurate offset
            # (LangChain may modify whitespace, so we search for it)
            chunk_start = text.find(chunk_text, char_offset)

            # If exact match not found (due to whitespace changes), use calculated offset
            if chunk_start == -1:
                chunk_start = char_offset

            chunk_end = chunk_start + len(chunk_text)

            # Create metadata dict (copy source metadata if provided)
            chunk_metadata = {}
            if source_metadata:
                chunk_metadata.update(source_metadata)

            # Create ChunkResult
            chunk_result = ChunkResult(
                text_content=chunk_text,
                char_offset_start=chunk_start,
                char_offset_end=chunk_end,
                chunk_index=chunk_index,
                metadata=chunk_metadata,
            )
            chunks.append(chunk_result)

            # Update offset for next iteration (with overlap consideration)
            char_offset = chunk_end - self.chunk_overlap

        return chunks

    def chunk_with_structure(
        self,
        text: str,
        structure_markers: List[dict] = None
    ) -> List[ChunkResult]:
        """Advanced chunking that preserves document structure markers.

        This method is useful for documents with clear structural elements
        like headings, sections, or page breaks. It associates each chunk
        with the appropriate structural context.

        Args:
            text: The document text to chunk
            structure_markers: List of structural markers in the document:
                [
                    {"type": "heading", "level": 1, "text": "Introduction", "offset": 0},
                    {"type": "page_break", "page": 2, "offset": 1500},
                    {"type": "heading", "level": 2, "text": "Methods", "offset": 3200},
                    ...
                ]

        Returns:
            List of ChunkResult objects with structure metadata enriched:
                - metadata.current_heading: Active heading at chunk position
                - metadata.current_page: Active page number at chunk position
                - metadata.section_hierarchy: List of nested headings

        Example:
            >>> markers = [
            ...     {"type": "heading", "level": 1, "text": "Chapter 1", "offset": 0},
            ...     {"type": "page_break", "page": 2, "offset": 500},
            ...     {"type": "heading", "level": 2, "text": "Section 1.1", "offset": 600},
            ... ]
            >>> chunks = chunker.chunk_with_structure(text, markers)
            >>> print(chunks[0].metadata)
            {'current_heading': 'Chapter 1', 'heading_level': 1, 'current_page': 1}
        """
        if text is None:
            raise ValueError("text cannot be None")

        if not text or not text.strip():
            return []

        # First, get basic chunks
        basic_chunks = self.chunk(text)

        # If no structure markers provided, return basic chunks
        if not structure_markers:
            return basic_chunks

        # Sort markers by offset
        sorted_markers = sorted(structure_markers, key=lambda m: m.get("offset", 0))

        # Enrich each chunk with structure context
        for chunk in basic_chunks:
            chunk_start = chunk.char_offset_start

            # Find active heading and page at this offset
            current_heading = None
            current_page = 1
            heading_level = None

            for marker in sorted_markers:
                marker_offset = marker.get("offset", 0)

                # Only consider markers before this chunk
                if marker_offset > chunk_start:
                    break

                marker_type = marker.get("type")

                if marker_type == "heading":
                    current_heading = marker.get("text")
                    heading_level = marker.get("level")
                elif marker_type == "page_break":
                    current_page = marker.get("page", current_page + 1)

            # Add structure metadata
            if current_heading:
                chunk.metadata["heading"] = current_heading
                chunk.metadata["heading_level"] = heading_level

            chunk.metadata["page"] = current_page

        return basic_chunks
