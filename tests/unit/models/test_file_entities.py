"""Unit tests for File, FileVersion, Chunk, and Embedding model entities.

Tests cover:
- Valid entity creation
- Foreign key relationships
- Unique constraints
- Check constraints (file_size > 0, offsets valid, etc.)
- Soft delete behavior
- Index existence verification
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.models import Base
from src.models.file import File, FileSourceType
from src.models.file_version import FileVersion
from src.models.chunk import Chunk
from src.models.embedding import Embedding
from src.models.project import Project


class TestFileEntity:
    """Test suite for File entity."""

    def test_file_creation_valid(self, test_db):
        """Test creating a valid File entity."""
        # Create a project first (foreign key requirement)
        project = Project(name="Test Project", description="Test description")
        test_db.add(project)
        test_db.commit()

        # Create file
        file = File(
            relative_path="documents/test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        # Verify
        assert file.file_id is not None
        assert file.relative_path == "documents/test.pdf"
        assert file.mime_type == "application/pdf"
        assert file.source_type == FileSourceType.UPLOADED_DOCUMENT
        assert file.project_id == project.project_id
        assert file.deleted is False
        assert file.created_at is not None
        assert file.updated_at is not None

    def test_file_source_type_enum(self, test_db):
        """Test FileSourceType enum values."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        # Test all source types
        for source_type in [
            FileSourceType.MEETING,
            FileSourceType.UPLOADED_DOCUMENT,
            FileSourceType.CHAT_EXPORT,
        ]:
            file = File(
                relative_path=f"test_{source_type.value}.txt",
                mime_type="text/plain",
                source_type=source_type,
                project_id=project.project_id,
            )
            test_db.add(file)
            test_db.commit()
            assert file.source_type == source_type

    def test_file_project_foreign_key(self, test_db):
        """Test File.project_id foreign key constraint."""
        # Try to create file with invalid project_id
        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=99999,  # Non-existent project
        )
        test_db.add(file)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_file_soft_delete(self, test_db):
        """Test soft delete behavior."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        # Soft delete
        file.deleted = True
        test_db.commit()

        # Verify still exists in database
        retrieved = test_db.query(File).filter_by(file_id=file.file_id).first()
        assert retrieved is not None
        assert retrieved.deleted is True

    def test_file_indexes_exist(self, test_db):
        """Test that expected indexes exist on File table."""
        inspector = inspect(test_db.bind)
        indexes = inspector.get_indexes("files")
        index_names = {idx["name"] for idx in indexes}

        # Check for expected indexes
        expected_indexes = {
            "idx_file_project",
            "idx_file_relative_path",
            "idx_file_source_type",
            "idx_file_deleted",
            "idx_file_current_version",
        }

        assert expected_indexes.issubset(index_names), f"Missing indexes: {expected_indexes - index_names}"

    def test_file_relationship_to_project(self, test_db):
        """Test File.project relationship."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        # Test relationship
        assert file.project is not None
        assert file.project.project_id == project.project_id
        assert file.project.name == "Test Project"

    def test_file_relationship_to_versions(self, test_db):
        """Test File.versions relationship."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        # Create versions
        version1 = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/v1.pdf",
        )
        version2 = FileVersion(
            file_id=file.file_id,
            content_hash="def456",
            file_size_bytes=1200,
            content_locator="/path/to/v2.pdf",
        )
        test_db.add_all([version1, version2])
        test_db.commit()

        # Test relationship
        assert len(file.versions) == 2
        assert version1 in file.versions
        assert version2 in file.versions


class TestFileVersionEntity:
    """Test suite for FileVersion entity."""

    def test_file_version_creation_valid(self, test_db):
        """Test creating a valid FileVersion entity."""
        # Setup
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        # Create file version
        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123def456",
            file_size_bytes=5000,
            content_locator="/data/uploads/test_v1.pdf",
            is_current=True,
        )
        test_db.add(version)
        test_db.commit()

        # Verify
        assert version.version_id is not None
        assert version.file_id == file.file_id
        assert version.content_hash == "abc123def456"
        assert version.file_size_bytes == 5000
        assert version.content_locator == "/data/uploads/test_v1.pdf"
        assert version.is_current is True
        assert version.discovered_at is not None

    def test_file_version_file_foreign_key(self, test_db):
        """Test FileVersion.file_id foreign key constraint."""
        # Try to create version with invalid file_id
        version = FileVersion(
            file_id=99999,  # Non-existent file
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_file_version_file_size_check_constraint(self, test_db):
        """Test file_size_bytes > 0 check constraint."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        # Try to create version with zero file size
        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=0,  # Invalid
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_file_version_negative_file_size_check(self, test_db):
        """Test negative file size is rejected."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        # Try to create version with negative file size
        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=-100,  # Invalid
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_file_version_indexes_exist(self, test_db):
        """Test that expected indexes exist on FileVersion table."""
        inspector = inspect(test_db.bind)
        indexes = inspector.get_indexes("file_versions")
        index_names = {idx["name"] for idx in indexes}

        expected_indexes = {
            "idx_file_version_file",
            "idx_file_version_hash",
            "idx_file_version_is_current",
        }

        assert expected_indexes.issubset(index_names), f"Missing indexes: {expected_indexes - index_names}"

    def test_file_version_relationship_to_file(self, test_db):
        """Test FileVersion.file relationship."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        # Test relationship
        assert version.file is not None
        assert version.file.file_id == file.file_id
        assert version.file.relative_path == "test.pdf"

    def test_file_version_relationship_to_chunks(self, test_db):
        """Test FileVersion.chunks relationship."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        # Create chunks
        chunk1 = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="First chunk",
            char_offset_start=0,
            char_offset_end=11,
        )
        chunk2 = Chunk(
            file_version_id=version.version_id,
            chunk_index=1,
            text_content="Second chunk",
            char_offset_start=11,
            char_offset_end=23,
        )
        test_db.add_all([chunk1, chunk2])
        test_db.commit()

        # Test relationship
        assert len(version.chunks) == 2
        assert chunk1 in version.chunks
        assert chunk2 in version.chunks


class TestChunkEntity:
    """Test suite for Chunk entity."""

    def test_chunk_creation_valid(self, test_db):
        """Test creating a valid Chunk entity."""
        # Setup
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        # Create chunk
        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="This is a test chunk with some content.",
            char_offset_start=0,
            char_offset_end=40,
            metadata_json={"page": 1, "heading": "Introduction"},
        )
        test_db.add(chunk)
        test_db.commit()

        # Verify
        assert chunk.chunk_id is not None
        assert chunk.file_version_id == version.version_id
        assert chunk.chunk_index == 0
        assert chunk.text_content == "This is a test chunk with some content."
        assert chunk.char_offset_start == 0
        assert chunk.char_offset_end == 40
        assert chunk.metadata_json == {"page": 1, "heading": "Introduction"}
        assert chunk.deleted is False
        assert chunk.created_at is not None

    def test_chunk_file_version_foreign_key(self, test_db):
        """Test Chunk.file_version_id foreign key constraint."""
        # Try to create chunk with invalid file_version_id
        chunk = Chunk(
            file_version_id=99999,  # Non-existent version
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_chunk_index_non_negative_constraint(self, test_db):
        """Test chunk_index >= 0 check constraint."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        # Try to create chunk with negative index
        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=-1,  # Invalid
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_chunk_offset_start_non_negative_constraint(self, test_db):
        """Test char_offset_start >= 0 check constraint."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        # Try to create chunk with negative offset start
        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=-10,  # Invalid
            char_offset_end=4,
        )
        test_db.add(chunk)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_chunk_valid_offsets_constraint(self, test_db):
        """Test char_offset_end > char_offset_start check constraint."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        # Try to create chunk with end <= start
        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=10,
            char_offset_end=10,  # Invalid: equal to start
        )
        test_db.add(chunk)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_chunk_metadata_json_nullable(self, test_db):
        """Test that metadata_json can be null."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        # Create chunk without metadata
        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
            metadata_json=None,
        )
        test_db.add(chunk)
        test_db.commit()

        assert chunk.metadata_json is None

    def test_chunk_soft_delete(self, test_db):
        """Test soft delete behavior."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)
        test_db.commit()

        # Soft delete
        chunk.deleted = True
        test_db.commit()

        # Verify still exists
        retrieved = test_db.query(Chunk).filter_by(chunk_id=chunk.chunk_id).first()
        assert retrieved is not None
        assert retrieved.deleted is True

    def test_chunk_indexes_exist(self, test_db):
        """Test that expected indexes exist on Chunk table."""
        inspector = inspect(test_db.bind)
        indexes = inspector.get_indexes("chunks")
        index_names = {idx["name"] for idx in indexes}

        expected_indexes = {
            "idx_chunk_file_version",
            "idx_chunk_index",
            "idx_chunk_deleted",
        }

        assert expected_indexes.issubset(index_names), f"Missing indexes: {expected_indexes - index_names}"

    def test_chunk_relationship_to_file_version(self, test_db):
        """Test Chunk.file_version relationship."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)
        test_db.commit()

        # Test relationship
        assert chunk.file_version is not None
        assert chunk.file_version.version_id == version.version_id

    def test_chunk_relationship_to_embedding(self, test_db):
        """Test Chunk.embedding relationship (one-to-one)."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)
        test_db.commit()

        # Create embedding
        embedding = Embedding(
            chunk_id=chunk.chunk_id,
            embedding_model="text-embedding-3-large",
            vector_db_id="vec_123",
            collection_name="test_collection",
        )
        test_db.add(embedding)
        test_db.commit()

        # Test relationship
        assert chunk.embedding is not None
        assert chunk.embedding.embedding_id == embedding.embedding_id


class TestEmbeddingEntity:
    """Test suite for Embedding entity."""

    def test_embedding_creation_valid(self, test_db):
        """Test creating a valid Embedding entity."""
        # Setup
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test chunk",
            char_offset_start=0,
            char_offset_end=10,
        )
        test_db.add(chunk)
        test_db.commit()

        # Create embedding
        embedding = Embedding(
            chunk_id=chunk.chunk_id,
            embedding_model="text-embedding-3-large",
            vector_db_id="chroma_vec_abc123",
            collection_name="meethub_embeddings",
        )
        test_db.add(embedding)
        test_db.commit()

        # Verify
        assert embedding.embedding_id is not None
        assert embedding.chunk_id == chunk.chunk_id
        assert embedding.embedding_model == "text-embedding-3-large"
        assert embedding.vector_db_id == "chroma_vec_abc123"
        assert embedding.collection_name == "meethub_embeddings"
        assert embedding.created_at is not None

    def test_embedding_chunk_unique_constraint(self, test_db):
        """Test that chunk_id is unique (one embedding per chunk)."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)
        test_db.commit()

        # Create first embedding
        embedding1 = Embedding(
            chunk_id=chunk.chunk_id,
            embedding_model="text-embedding-3-large",
            vector_db_id="vec_1",
            collection_name="test_collection",
        )
        test_db.add(embedding1)
        test_db.commit()

        # Try to create second embedding for same chunk
        embedding2 = Embedding(
            chunk_id=chunk.chunk_id,  # Same chunk_id
            embedding_model="text-embedding-3-large",
            vector_db_id="vec_2",
            collection_name="test_collection",
        )
        test_db.add(embedding2)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_embedding_chunk_foreign_key(self, test_db):
        """Test Embedding.chunk_id foreign key constraint."""
        # Try to create embedding with invalid chunk_id
        embedding = Embedding(
            chunk_id=99999,  # Non-existent chunk
            embedding_model="text-embedding-3-large",
            vector_db_id="vec_123",
            collection_name="test_collection",
        )
        test_db.add(embedding)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_embedding_indexes_exist(self, test_db):
        """Test that expected indexes exist on Embedding table."""
        inspector = inspect(test_db.bind)
        indexes = inspector.get_indexes("embeddings")
        index_names = {idx["name"] for idx in indexes}

        expected_indexes = {
            "idx_embedding_model",
            "idx_embedding_collection",
            "idx_embedding_vector_db_id",
        }

        assert expected_indexes.issubset(index_names), f"Missing indexes: {expected_indexes - index_names}"

    def test_embedding_relationship_to_chunk(self, test_db):
        """Test Embedding.chunk relationship."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)
        test_db.commit()

        embedding = Embedding(
            chunk_id=chunk.chunk_id,
            embedding_model="text-embedding-3-large",
            vector_db_id="vec_123",
            collection_name="test_collection",
        )
        test_db.add(embedding)
        test_db.commit()

        # Test relationship
        assert embedding.chunk is not None
        assert embedding.chunk.chunk_id == chunk.chunk_id
        assert embedding.chunk.text_content == "Test"


class TestCascadeDeleteBehavior:
    """Test cascade delete behaviors across entities."""

    def test_delete_file_cascades_to_versions(self, test_db):
        """Test that deleting a file cascades to file versions."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        version_id = version.version_id

        # Delete file
        test_db.delete(file)
        test_db.commit()

        # Verify version was also deleted
        deleted_version = test_db.query(FileVersion).filter_by(version_id=version_id).first()
        assert deleted_version is None

    def test_delete_version_cascades_to_chunks(self, test_db):
        """Test that deleting a file version cascades to chunks."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)
        test_db.commit()

        chunk_id = chunk.chunk_id

        # Delete version
        test_db.delete(version)
        test_db.commit()

        # Verify chunk was also deleted
        deleted_chunk = test_db.query(Chunk).filter_by(chunk_id=chunk_id).first()
        assert deleted_chunk is None

    def test_delete_chunk_cascades_to_embedding(self, test_db):
        """Test that deleting a chunk cascades to embedding."""
        project = Project(name="Test Project")
        test_db.add(project)
        test_db.commit()

        file = File(
            relative_path="test.pdf",
            mime_type="application/pdf",
            source_type=FileSourceType.UPLOADED_DOCUMENT,
            project_id=project.project_id,
        )
        test_db.add(file)
        test_db.commit()

        version = FileVersion(
            file_id=file.file_id,
            content_hash="abc123",
            file_size_bytes=1000,
            content_locator="/path/to/file.pdf",
        )
        test_db.add(version)
        test_db.commit()

        chunk = Chunk(
            file_version_id=version.version_id,
            chunk_index=0,
            text_content="Test",
            char_offset_start=0,
            char_offset_end=4,
        )
        test_db.add(chunk)
        test_db.commit()

        embedding = Embedding(
            chunk_id=chunk.chunk_id,
            embedding_model="text-embedding-3-large",
            vector_db_id="vec_123",
            collection_name="test_collection",
        )
        test_db.add(embedding)
        test_db.commit()

        embedding_id = embedding.embedding_id

        # Delete chunk
        test_db.delete(chunk)
        test_db.commit()

        # Verify embedding was also deleted
        deleted_embedding = test_db.query(Embedding).filter_by(embedding_id=embedding_id).first()
        assert deleted_embedding is None
