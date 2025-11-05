"""Integration tests for ChromaDB vector store.

Tests cover:
- Collection creation with persistent client
- Batch embedding storage (add 100 embeddings)
- Metadata filtering (filter by project_id, source_type)
- Top-K retrieval with similarity scores
- Collection deletion
- Persistence across restarts (create, close, reopen)
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Any

from src.services.vector_store import ChromaVectorStore, VectorRecord, QueryResult


@pytest.fixture
def temp_chroma_dir():
    """Create a temporary directory for ChromaDB data."""
    temp_dir = tempfile.mkdtemp(prefix="test_chroma_")
    yield Path(temp_dir)
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def vector_store(temp_chroma_dir):
    """Create a ChromaVectorStore instance with temporary storage."""
    store = ChromaVectorStore(
        persist_path=temp_chroma_dir,
        collection_name="test_collection",
        collection_metadata={"description": "Test collection"},
    )
    yield store
    # Cleanup is handled by temp_chroma_dir fixture


class TestChromaVectorStoreBasics:
    """Test basic ChromaVectorStore operations."""

    def test_initialization(self, temp_chroma_dir):
        """Test that ChromaVectorStore initializes correctly."""
        store = ChromaVectorStore(
            persist_path=temp_chroma_dir,
            collection_name="test_init",
        )

        assert store is not None
        assert store.client is not None
        assert store.collection is not None
        assert store.collection.name == "test_init"

    def test_collection_creation_with_metadata(self, temp_chroma_dir):
        """Test collection creation with custom metadata."""
        metadata = {
            "description": "Integration test collection",
            "version": "1.0",
            "created_by": "test_suite",
        }

        store = ChromaVectorStore(
            persist_path=temp_chroma_dir,
            collection_name="test_metadata",
            collection_metadata=metadata,
        )

        # Verify collection exists and has metadata
        assert store.collection.name == "test_metadata"
        # Metadata should be present (exact structure depends on ChromaDB version)
        assert store.collection.metadata is not None

    def test_list_collections(self, vector_store):
        """Test listing collections."""
        collections = vector_store.list_collections()

        assert isinstance(collections, list)
        assert "test_collection" in collections


class TestVectorUpsert:
    """Test vector upsert operations."""

    def test_upsert_single_record(self, vector_store):
        """Test upserting a single vector record."""
        record = VectorRecord(
            vector_id="vec_1",
            values=[0.1, 0.2, 0.3, 0.4, 0.5],
            metadata={"source": "test", "index": 0},
            document="This is a test document.",
        )

        vector_store.upsert([record])

        # Verify by querying
        result = vector_store.query(
            vector=[0.1, 0.2, 0.3, 0.4, 0.5],
            top_k=1,
        )

        assert len(result.ids) == 1
        assert result.ids[0] == "vec_1"
        assert result.documents[0] == "This is a test document."

    def test_upsert_batch_100_embeddings(self, vector_store):
        """Test batch upserting 100 embeddings."""
        records = []
        for i in range(100):
            # Create simple vectors with different values
            vector = [float(i) / 100.0 + j * 0.01 for j in range(5)]
            record = VectorRecord(
                vector_id=f"vec_{i:03d}",
                values=vector,
                metadata={"batch": "test", "index": i, "category": f"cat_{i % 5}"},
                document=f"Document number {i}",
            )
            records.append(record)

        # Upsert all at once
        vector_store.upsert(records)

        # Verify count by querying
        result = vector_store.query(
            vector=[0.5, 0.51, 0.52, 0.53, 0.54],
            top_k=100,
        )

        # Should get all 100 embeddings back
        assert len(result.ids) == 100

    def test_upsert_updates_existing(self, vector_store):
        """Test that upserting with same ID updates the record."""
        # Initial insert
        record1 = VectorRecord(
            vector_id="vec_update",
            values=[1.0, 0.0, 0.0],
            metadata={"version": 1},
            document="Original document",
        )
        vector_store.upsert([record1])

        # Update with same ID
        record2 = VectorRecord(
            vector_id="vec_update",
            values=[0.0, 1.0, 0.0],  # Different vector
            metadata={"version": 2},  # Different metadata
            document="Updated document",
        )
        vector_store.upsert([record2])

        # Query and verify update
        result = vector_store.query(
            vector=[0.0, 1.0, 0.0],
            top_k=1,
        )

        assert len(result.ids) == 1
        assert result.ids[0] == "vec_update"
        assert result.documents[0] == "Updated document"
        assert result.metadatas[0]["version"] == 2

    def test_upsert_empty_list(self, vector_store):
        """Test that upserting empty list does nothing."""
        # Should not raise error
        vector_store.upsert([])

        # Collection should still be empty (or have only previous test data)
        collections_count = len(vector_store.list_collections())
        assert collections_count >= 1  # At least test_collection exists


class TestMetadataFiltering:
    """Test metadata filtering in queries."""

    def test_filter_by_project_id(self, vector_store):
        """Test filtering by project_id metadata."""
        # Insert records with different project_ids
        records = [
            VectorRecord(
                vector_id="proj1_vec1",
                values=[1.0, 0.0, 0.0],
                metadata={"project_id": 1, "source_type": "meeting"},
                document="Project 1 document 1",
            ),
            VectorRecord(
                vector_id="proj1_vec2",
                values=[0.9, 0.1, 0.0],
                metadata={"project_id": 1, "source_type": "document"},
                document="Project 1 document 2",
            ),
            VectorRecord(
                vector_id="proj2_vec1",
                values=[0.8, 0.2, 0.0],
                metadata={"project_id": 2, "source_type": "meeting"},
                document="Project 2 document 1",
            ),
        ]
        vector_store.upsert(records)

        # Query with project_id filter
        result = vector_store.query(
            vector=[1.0, 0.0, 0.0],
            top_k=10,
            where={"project_id": 1},
        )

        # Should only get project 1 records
        assert len(result.ids) == 2
        assert all("proj1" in vec_id for vec_id in result.ids)

    def test_filter_by_source_type(self, vector_store):
        """Test filtering by source_type metadata."""
        records = [
            VectorRecord(
                vector_id="meeting_vec1",
                values=[1.0, 0.0, 0.0],
                metadata={"project_id": 1, "source_type": "meeting"},
                document="Meeting transcript",
            ),
            VectorRecord(
                vector_id="doc_vec1",
                values=[0.9, 0.1, 0.0],
                metadata={"project_id": 1, "source_type": "uploaded_document"},
                document="Uploaded PDF",
            ),
            VectorRecord(
                vector_id="meeting_vec2",
                values=[0.8, 0.2, 0.0],
                metadata={"project_id": 1, "source_type": "meeting"},
                document="Another meeting",
            ),
        ]
        vector_store.upsert(records)

        # Query for only meetings
        result = vector_store.query(
            vector=[1.0, 0.0, 0.0],
            top_k=10,
            where={"source_type": "meeting"},
        )

        # Should only get meeting records
        assert len(result.ids) == 2
        assert all("meeting" in vec_id for vec_id in result.ids)

    def test_filter_by_multiple_criteria(self, vector_store):
        """Test filtering by multiple metadata fields."""
        records = [
            VectorRecord(
                vector_id="vec1",
                values=[1.0, 0.0, 0.0],
                metadata={"project_id": 1, "source_type": "meeting", "tag": "important"},
                document="Doc 1",
            ),
            VectorRecord(
                vector_id="vec2",
                values=[0.9, 0.1, 0.0],
                metadata={"project_id": 1, "source_type": "meeting", "tag": "normal"},
                document="Doc 2",
            ),
            VectorRecord(
                vector_id="vec3",
                values=[0.8, 0.2, 0.0],
                metadata={"project_id": 2, "source_type": "meeting", "tag": "important"},
                document="Doc 3",
            ),
        ]
        vector_store.upsert(records)

        # Query with multiple filters
        result = vector_store.query(
            vector=[1.0, 0.0, 0.0],
            top_k=10,
            where={"project_id": 1, "tag": "important"},
        )

        # Should only get one record matching both criteria
        assert len(result.ids) == 1
        assert result.ids[0] == "vec1"


class TestTopKRetrieval:
    """Test top-K retrieval with similarity scores."""

    def test_top_k_retrieval(self, vector_store):
        """Test retrieving top-K most similar vectors."""
        # Insert 10 vectors
        records = []
        for i in range(10):
            vector = [float(i) / 10.0, 1.0 - float(i) / 10.0, 0.0]
            records.append(
                VectorRecord(
                    vector_id=f"vec_{i}",
                    values=vector,
                    metadata={"index": i},
                    document=f"Document {i}",
                )
            )
        vector_store.upsert(records)

        # Query for top 3
        result = vector_store.query(
            vector=[0.0, 1.0, 0.0],
            top_k=3,
        )

        # Should get exactly 3 results
        assert len(result.ids) == 3
        assert len(result.distances) == 3

        # Results should be ordered by similarity (distance)
        # Distances should be non-decreasing (closest first)
        for i in range(len(result.distances) - 1):
            assert result.distances[i] <= result.distances[i + 1]

    def test_similarity_scores(self, vector_store):
        """Test that similarity scores (distances) are meaningful."""
        # Insert exact match and different vector
        records = [
            VectorRecord(
                vector_id="exact_match",
                values=[1.0, 0.0, 0.0],
                metadata={"type": "exact"},
                document="Exact match",
            ),
            VectorRecord(
                vector_id="different",
                values=[0.0, 1.0, 0.0],
                metadata={"type": "different"},
                document="Different vector",
            ),
        ]
        vector_store.upsert(records)

        # Query with exact match vector
        result = vector_store.query(
            vector=[1.0, 0.0, 0.0],
            top_k=2,
        )

        # Exact match should be first with distance ~0
        assert result.ids[0] == "exact_match"
        assert result.distances[0] < 0.01  # Very close to 0

        # Different vector should have higher distance
        assert result.ids[1] == "different"
        assert result.distances[1] > result.distances[0]


class TestCollectionManagement:
    """Test collection deletion and management."""

    def test_reset_collection(self, vector_store):
        """Test resetting (deleting and recreating) a collection."""
        # Add some data
        record = VectorRecord(
            vector_id="vec_1",
            values=[1.0, 0.0, 0.0],
            metadata={"test": "data"},
            document="Test document",
        )
        vector_store.upsert([record])

        # Verify data exists
        result = vector_store.query(vector=[1.0, 0.0, 0.0], top_k=1)
        assert len(result.ids) == 1

        # Reset collection
        vector_store.reset_collection()

        # Verify data is gone
        result = vector_store.query(vector=[1.0, 0.0, 0.0], top_k=1)
        assert len(result.ids) == 0

    def test_delete_by_ids(self, vector_store):
        """Test deleting specific vectors by ID."""
        records = [
            VectorRecord(
                vector_id="vec_keep",
                values=[1.0, 0.0, 0.0],
                metadata={"status": "keep"},
                document="Keep this",
            ),
            VectorRecord(
                vector_id="vec_delete",
                values=[0.0, 1.0, 0.0],
                metadata={"status": "delete"},
                document="Delete this",
            ),
        ]
        vector_store.upsert(records)

        # Delete one vector
        vector_store.delete(ids=["vec_delete"])

        # Verify deleted
        result = vector_store.query(vector=[0.0, 1.0, 0.0], top_k=2)
        assert len(result.ids) == 1
        assert result.ids[0] == "vec_keep"

    def test_delete_by_metadata_filter(self, vector_store):
        """Test deleting vectors by metadata filter."""
        records = [
            VectorRecord(
                vector_id="vec_1",
                values=[1.0, 0.0, 0.0],
                metadata={"category": "delete_me"},
                document="Will be deleted",
            ),
            VectorRecord(
                vector_id="vec_2",
                values=[0.0, 1.0, 0.0],
                metadata={"category": "keep_me"},
                document="Will be kept",
            ),
        ]
        vector_store.upsert(records)

        # Delete by metadata
        vector_store.delete(where={"category": "delete_me"})

        # Verify only keep_me remains
        result = vector_store.query(vector=[1.0, 0.0, 0.0], top_k=2)
        assert len(result.ids) == 1
        assert result.ids[0] == "vec_2"


class TestPersistence:
    """Test persistence across ChromaDB client restarts."""

    def test_persistence_across_restarts(self, temp_chroma_dir):
        """Test that data persists when creating new ChromaVectorStore instance."""
        # Create first instance and add data
        store1 = ChromaVectorStore(
            persist_path=temp_chroma_dir,
            collection_name="persist_test",
        )

        records = [
            VectorRecord(
                vector_id="persistent_vec",
                values=[1.0, 2.0, 3.0],
                metadata={"persistent": True},
                document="This should persist",
            )
        ]
        store1.upsert(records)

        # Explicitly persist (though PersistentClient should auto-persist)
        store1.persist()

        # Create new instance with same path
        store2 = ChromaVectorStore(
            persist_path=temp_chroma_dir,
            collection_name="persist_test",
        )

        # Query data from new instance
        result = store2.query(vector=[1.0, 2.0, 3.0], top_k=1)

        # Data should still be there
        assert len(result.ids) == 1
        assert result.ids[0] == "persistent_vec"
        assert result.documents[0] == "This should persist"

    def test_persistence_with_100_vectors(self, temp_chroma_dir):
        """Test persistence with larger dataset (100 vectors)."""
        # First instance - add 100 vectors
        store1 = ChromaVectorStore(
            persist_path=temp_chroma_dir,
            collection_name="large_persist_test",
        )

        records = []
        for i in range(100):
            vector = [float(i), float(i + 1), float(i + 2)]
            records.append(
                VectorRecord(
                    vector_id=f"vec_{i:03d}",
                    values=vector,
                    metadata={"index": i, "batch": "persistence_test"},
                    document=f"Persistent document {i}",
                )
            )

        store1.upsert(records)
        store1.persist()

        # Second instance - verify all data
        store2 = ChromaVectorStore(
            persist_path=temp_chroma_dir,
            collection_name="large_persist_test",
        )

        # Query for all vectors
        result = store2.query(vector=[50.0, 51.0, 52.0], top_k=100)

        # Should get all 100 back
        assert len(result.ids) == 100
        assert all(f"vec_" in vec_id for vec_id in result.ids)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_query_empty_collection(self, vector_store):
        """Test querying an empty collection."""
        result = vector_store.query(vector=[1.0, 0.0, 0.0], top_k=10)

        # Should return empty results, not error
        assert len(result.ids) == 0
        assert len(result.metadatas) == 0
        assert len(result.documents) == 0
        assert len(result.distances) == 0

    def test_delete_without_criteria_raises_error(self, vector_store):
        """Test that delete without ids or where raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            vector_store.delete()

        assert "Either ids or where must be provided" in str(exc_info.value)

    def test_upsert_record_without_document(self, vector_store):
        """Test upserting record without document field."""
        record = VectorRecord(
            vector_id="no_doc",
            values=[1.0, 0.0, 0.0],
            metadata={"test": True},
            document=None,  # No document
        )

        # Should not raise error
        vector_store.upsert([record])

        result = vector_store.query(vector=[1.0, 0.0, 0.0], top_k=1)
        assert len(result.ids) == 1

    def test_upsert_record_without_metadata(self, vector_store):
        """Test upserting record without metadata."""
        record = VectorRecord(
            vector_id="no_meta",
            values=[1.0, 0.0, 0.0],
            metadata=None,  # No metadata
            document="Document without metadata",
        )

        # Should not raise error
        vector_store.upsert([record])

        result = vector_store.query(vector=[1.0, 0.0, 0.0], top_k=1)
        assert len(result.ids) == 1
        assert result.metadatas[0] == {}  # Empty dict for None metadata
