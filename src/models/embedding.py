"""Embedding model for vector storage metadata."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class Embedding(Base):
    """Embedding entity tracking vector embeddings in ChromaDB."""

    __tablename__ = "embeddings"

    # Primary key
    embedding_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key (unique - one embedding per chunk)
    chunk_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chunks.chunk_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Vector store metadata
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Model used to generate embedding (e.g., text-embedding-3-large)",
    )
    vector_db_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="ID in ChromaDB for vector retrieval",
    )
    collection_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="ChromaDB collection name",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    chunk: Mapped["Chunk"] = relationship(
        "Chunk",
        back_populates="embedding",
    )

    # Indexes
    __table_args__ = (
        Index("idx_embedding_model", "embedding_model"),
        Index("idx_embedding_collection", "collection_name"),
        Index("idx_embedding_vector_db_id", "vector_db_id"),
    )

    def __repr__(self) -> str:
        """String representation of Embedding."""
        return f"<Embedding(id={self.embedding_id}, chunk_id={self.chunk_id}, model={self.embedding_model})>"
