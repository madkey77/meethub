"""ChromaDB-backed vector store wrapper used by the RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

try:
    import chromadb
    from chromadb.api.models.Collection import Collection
    from chromadb.errors import NotFoundError
except ImportError:  # pragma: no cover - handled during initialization
    chromadb = None  # type: ignore
    Collection = Any  # type: ignore
    NotFoundError = Exception  # type: ignore

from src.config import settings
from src.utils.exceptions import ConfigurationError
from src.utils.logging import get_logger


@dataclass(slots=True)
class VectorRecord:
    """Container for a single embedding row destined for the vector store."""

    vector_id: str
    values: Sequence[float]
    metadata: dict[str, Any] | None = None
    document: str | None = None


@dataclass(slots=True)
class QueryResult:
    """Represents the outcome of a similarity search query."""

    ids: list[str]
    metadatas: list[dict[str, Any]]
    documents: list[str]
    distances: list[float]


class ChromaVectorStore:
    """High-level wrapper around ChromaDB PersistentClient collections."""

    def __init__(
        self,
        *,
        persist_path: Path | str | None = None,
        collection_name: str | None = None,
        collection_metadata: dict[str, Any] | None = None,
    ) -> None:
        if chromadb is None:
            raise ConfigurationError(
                "chromadb package is not installed",
                details={"hint": "Run 'pip install chromadb' inside the project environment."},
            )

        self._logger = get_logger(__name__).bind(service="vector_store")
        path = Path(persist_path or settings.chromadb_path)
        path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(path))
        self._default_collection_name = collection_name or settings.chromadb_collection_name
        self._collection_metadata = collection_metadata or {}
        self._collection: Collection | None = None

    @property
    def client(self) -> chromadb.PersistentClient:
        """Expose the underlying Chroma persistent client."""

        return self._client

    @property
    def collection(self) -> Collection:
        """Return (and lazily create) the configured collection."""

        if self._collection is None:
            self._collection = self._ensure_collection(
                self._default_collection_name,
                metadata=self._collection_metadata,
            )
        return self._collection

    def _ensure_collection(self, name: str, metadata: dict[str, Any] | None = None) -> Collection:
        metadata = metadata or {}
        try:
            collection = self._client.get_collection(name)
            if metadata:
                stored_metadata = collection.metadata or {}
                for key, value in metadata.items():
                    if key not in stored_metadata:
                        stored_metadata[key] = value
                if stored_metadata != (collection.metadata or {}):
                    collection.modify(metadata=stored_metadata)
            return collection
        except NotFoundError:  # pragma: no cover - depends on runtime state
            self._logger.info(
                "vector_store.create_collection",
                collection=name,
                metadata=metadata,
            )
            return self._client.create_collection(name=name, metadata=metadata)

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Insert or update embeddings in the configured collection."""

        if not records:
            return

        collection = self.collection

        ids = [record.vector_id for record in records]
        embeddings = [list(record.values) for record in records]
        metadatas = [record.metadata or {} for record in records]
        documents = [record.document for record in records]

        kwargs: dict[str, Any] = {
            "ids": ids,
            "embeddings": embeddings,
            "metadatas": metadatas,
        }
        if any(document is not None for document in documents):
            kwargs["documents"] = [document or "" for document in documents]

        collection.upsert(**kwargs)
        self._logger.info("vector_store.upsert", count=len(records))

    def delete(self, *, ids: Sequence[str] | None = None, where: dict[str, Any] | None = None) -> None:
        """Remove embeddings by identifier or metadata filter."""

        if not ids and not where:
            raise ValueError("Either ids or where must be provided for delete operations")

        self.collection.delete(ids=list(ids) if ids else None, where=where)
        self._logger.info(
            "vector_store.delete",
            count=len(ids) if ids else None,
            where=where,
        )

    def query(
        self,
        *,
        vector: Sequence[float],
        top_k: int,
        where: dict[str, Any] | None = None,
        include_embeddings: bool = False,
    ) -> QueryResult:
        """Execute a similarity search against the collection."""

        include: list[str] = ["metadatas", "documents", "distances"]
        if include_embeddings:
            include.append("embeddings")

        response = self.collection.query(
            query_embeddings=[list(vector)],
            n_results=top_k,
            where=where,
            include=include,
        )

        ids = response.get("ids", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        documents = response.get("documents", [[]])[0]
        distances = response.get("distances", [[]])[0]

        return QueryResult(
            ids=[str(identifier) for identifier in ids],
            metadatas=[metadata or {} for metadata in metadatas],
            documents=[document or "" for document in documents],
            distances=[float(distance) for distance in distances],
        )

    def list_collections(self) -> list[str]:
        """Return the names of collections available in the client."""

        return [collection.name for collection in self._client.list_collections()]

    def reset_collection(self, name: str | None = None) -> None:
        """Drop and recreate the specified (or default) collection."""

        target = name or self._default_collection_name
        try:
            self._client.delete_collection(target)
        except NotFoundError:  # pragma: no cover - depends on runtime state
            self._logger.warning("vector_store.reset_missing", collection=target)
        finally:
            if target == self._default_collection_name:
                self._collection = self._ensure_collection(target, self._collection_metadata)
            self._logger.info("vector_store.reset_collection", collection=target)

    def persist(self) -> None:
        """Flush data to disk (mostly a no-op for PersistentClient but kept for clarity)."""

        self._client.persist()
        self._logger.debug("vector_store.persisted")
