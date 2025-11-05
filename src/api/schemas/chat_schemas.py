"""Pydantic schemas for RAG chat/query endpoints.

This module defines request/response schemas for:
- Chat query submission with RAG retrieval
- Chat responses with citations and metadata
- Citation details (speaker-aware for meetings, page-aware for documents)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==============================================================================
# Enums
# ==============================================================================

class SourceTypeEnum(str, Enum):
    """Citation source type."""

    MEETING = "meeting"
    DOCUMENT = "document"
    CHAT_EXPORT = "chat_export"


# ==============================================================================
# Request Schemas
# ==============================================================================

class ChatQueryRequest(BaseModel):
    """Request for RAG chat query.

    Attributes:
        query: Natural language query (3-2000 characters)
        project_id: Filter retrieval to specific project
        top_k: Number of chunks to retrieve (1-50)
        min_similarity: Minimum similarity threshold (0.0-1.0)
        llm_provider: LLM provider for answer generation (openai, anthropic)
        llm_model: Specific model name (e.g., gpt-4o, claude-3-5-sonnet)
        experimental_mode: Enable multi-provider comparison
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Who decided to use Kubernetes for deployment, and what does the architecture document say about scalability?",
                "project_id": 1,
                "top_k": 10,
                "min_similarity": 0.6,
                "llm_provider": "openai",
                "llm_model": "gpt-4o",
            }
        }
    )

    query: str = Field(
        ...,
        description="Natural language query",
        min_length=3,
        max_length=2000,
        examples=["Who decided to use Kubernetes for deployment?"],
    )
    project_id: Optional[int] = Field(
        None,
        description="Filter to specific project",
        examples=[1],
    )
    top_k: int = Field(
        10,
        description="Number of chunks to retrieve",
        ge=1,
        le=50,
    )
    min_similarity: float = Field(
        0.6,
        description="Minimum similarity threshold",
        ge=0.0,
        le=1.0,
    )
    llm_provider: Optional[str] = Field(
        None,
        description="LLM provider (uses LLM_PROVIDER_PREFERENCE if not specified)",
        examples=["openai", "anthropic"],
    )
    llm_model: Optional[str] = Field(
        None,
        description="Specific model name",
        examples=["gpt-4o", "claude-3-5-sonnet"],
    )
    experimental_mode: bool = Field(
        False,
        description="Enable multi-provider comparison",
    )

    @field_validator("query")
    @classmethod
    def validate_query_length(cls, v: str) -> str:
        """Validate query is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or whitespace-only")
        return v.strip()

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        """Validate LLM provider is supported."""
        if v is not None:
            v = v.lower()
            if v not in ["openai", "anthropic"]:
                raise ValueError("LLM provider must be 'openai' or 'anthropic'")
        return v


# ==============================================================================
# Response Schemas
# ==============================================================================

class Citation(BaseModel):
    """Citation with source information.

    For meetings:
        - speaker: Speaker name or label
        - speaker_name: Resolved speaker name (if mapping available)
        - timestamp: Timestamp in meeting (HH:MM:SS)

    For documents:
        - page: Page number
        - section: Section heading

    For chat exports:
        - message_sender: Message sender
        - message_timestamp: Message timestamp

    Attributes:
        citation_id: Unique citation identifier
        source_type: Source type (meeting, document, chat_export)
        file_path: File path (meeting:// URI for meetings)
        chunk_index: Chunk index in file
        similarity_score: Cosine similarity score (0.0-1.0)
        chunk_text: Excerpt from chunk for context
        speaker: Speaker name or label (meetings only)
        speaker_name: Resolved speaker name (meetings only)
        timestamp: Timestamp in meeting (meetings only)
        page: Page number (documents only)
        section: Section heading (documents only)
        message_sender: Message sender (chat exports only)
        message_timestamp: Message timestamp (chat exports only)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "citation_id": "cit_001",
                    "source_type": "meeting",
                    "file_path": "meeting://meeting-123",
                    "chunk_index": 15,
                    "similarity_score": 0.89,
                    "chunk_text": "I think we should use Kubernetes for deployment because it gives us better scalability...",
                    "speaker": "Speaker 2",
                    "speaker_name": "Alice Smith",
                    "timestamp": "00:14:32",
                },
                {
                    "citation_id": "cit_002",
                    "source_type": "document",
                    "file_path": "/ingest/project-alpha/architecture.pdf",
                    "chunk_index": 8,
                    "similarity_score": 0.87,
                    "chunk_text": "Kubernetes provides horizontal scaling capabilities essential for our microservices...",
                    "page": 12,
                    "section": "Deployment Architecture",
                },
            ]
        }
    )

    citation_id: str = Field(..., description="Citation identifier")
    source_type: SourceTypeEnum = Field(..., description="Source type")
    file_path: str = Field(..., description="File path or URI")
    chunk_index: Optional[int] = Field(None, description="Chunk index", ge=0)
    similarity_score: float = Field(..., description="Similarity score", ge=0.0, le=1.0)
    chunk_text: str = Field(..., description="Chunk excerpt")

    # Meeting-specific fields
    speaker: Optional[str] = Field(None, description="Speaker label (meetings only)")
    speaker_name: Optional[str] = Field(None, description="Resolved speaker name (meetings only)")
    timestamp: Optional[str] = Field(None, description="Timestamp HH:MM:SS (meetings only)")

    # Document-specific fields
    page: Optional[int] = Field(None, description="Page number (documents only)", ge=1)
    section: Optional[str] = Field(None, description="Section heading (documents only)")

    # Chat export-specific fields
    message_sender: Optional[str] = Field(None, description="Message sender (chat exports only)")
    message_timestamp: Optional[datetime] = Field(
        None,
        description="Message timestamp (chat exports only)",
    )


class RetrievalMetadata(BaseModel):
    """Metadata about RAG retrieval and generation.

    Attributes:
        chunks_retrieved: Number of chunks retrieved
        avg_similarity: Average similarity score
        max_similarity: Maximum similarity score
        min_similarity: Minimum similarity score (excluding filtered)
        llm_provider: LLM provider used
        llm_model: LLM model used
        tokens_used: Total tokens consumed
        cost_estimate: Estimated cost in USD
    """

    model_config = ConfigDict(from_attributes=True)

    chunks_retrieved: int = Field(..., description="Chunks retrieved", ge=0)
    avg_similarity: Optional[float] = Field(None, description="Average similarity", ge=0.0, le=1.0)
    max_similarity: Optional[float] = Field(None, description="Maximum similarity", ge=0.0, le=1.0)
    min_similarity: Optional[float] = Field(None, description="Minimum similarity", ge=0.0, le=1.0)
    llm_provider: str = Field(..., description="LLM provider", examples=["openai"])
    llm_model: str = Field(..., description="LLM model", examples=["gpt-4o"])
    tokens_used: Optional[int] = Field(None, description="Tokens consumed", ge=0)
    cost_estimate: Optional[float] = Field(None, description="Cost estimate (USD)", ge=0)


class ChatResponse(BaseModel):
    """Response from RAG chat query.

    Attributes:
        answer: LLM-generated answer grounded in retrieved context
        citations: List of citations supporting the answer
        retrieval_metadata: Metadata about retrieval and generation
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "According to Alice in the standup on 2025-11-01 at 14:32, the team decided to use Kubernetes for deployment. The decision is also documented in architecture.pdf page 12, which states that Kubernetes provides better scalability for microservices.",
                "citations": [
                    {
                        "citation_id": "cit_001",
                        "source_type": "meeting",
                        "file_path": "meeting://meeting-123",
                        "speaker": "Alice Smith",
                        "timestamp": "00:14:32",
                        "similarity_score": 0.89,
                        "chunk_text": "I think we should use Kubernetes for deployment because it gives us better scalability...",
                    },
                    {
                        "citation_id": "cit_002",
                        "source_type": "document",
                        "file_path": "/ingest/project-alpha/architecture.pdf",
                        "page": 12,
                        "section": "Deployment Architecture",
                        "similarity_score": 0.87,
                        "chunk_text": "Kubernetes provides horizontal scaling capabilities essential for our microservices...",
                    },
                ],
                "retrieval_metadata": {
                    "chunks_retrieved": 10,
                    "avg_similarity": 0.78,
                    "max_similarity": 0.89,
                    "llm_provider": "openai",
                    "llm_model": "gpt-4o",
                    "tokens_used": 3200,
                    "cost_estimate": 0.08,
                },
            }
        }
    )

    answer: str = Field(..., description="LLM-generated answer")
    citations: List[Citation] = Field(default_factory=list, description="Citations")
    retrieval_metadata: Optional[RetrievalMetadata] = Field(None, description="Retrieval metadata")
