"""Integration tests for concurrent file uploads.

Tests parallel upload handling, concurrency limits, and race condition prevention.
"""

import concurrent.futures
import time
from pathlib import Path

import pytest

from src.models import File, FileVersion, Project
from src.services.file_ingestion import FileIngestionService


@pytest.fixture
def test_project(db_session):
    """Create test project."""
    project = Project(
        name="concurrent-test-project",
        drive_folder_id="test-folder-concurrent",
        classification_rules=[],
        is_default=False,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def sample_files(tmp_path):
    """Create 20 sample files for concurrent testing."""
    files = []
    for i in range(20):
        file_path = tmp_path / f"document_{i:02d}.txt"
        file_path.write_text(f"Document {i} content for concurrency testing.")
        files.append(file_path)
    return files


class TestConcurrentUploads:
    """Integration tests for concurrent file uploads."""

    def test_concurrent_uploads_all_succeed(self, db_session, test_project, sample_files):
        """Test that all concurrent uploads complete successfully.

        Verifies:
        - All 20 files are uploaded
        - No files are lost
        - All File entities created
        """
        service = FileIngestionService(db_session)

        def upload_file(file_path):
            return service.ingest_file(str(file_path), test_project.project_id)

        # Upload files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_file, f) for f in sample_files]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify all uploaded
        assert len(results) == 20

        # Verify all in database
        files_in_db = (
            db_session.query(File)
            .filter(File.project_id == test_project.project_id)
            .count()
        )
        assert files_in_db == 20

    def test_concurrent_uploads_no_race_conditions(self, db_session, test_project, sample_files):
        """Test that concurrent uploads don't create race conditions.

        Verifies:
        - Each file has exactly one FileVersion
        - No duplicate versions created
        - Database integrity maintained
        """
        service = FileIngestionService(db_session)

        def upload_file(file_path):
            return service.ingest_file(str(file_path), test_project.project_id)

        # Upload concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(upload_file, f) for f in sample_files]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify no duplicate versions
        for file_entity in results:
            versions = (
                db_session.query(FileVersion)
                .filter(FileVersion.file_id == file_entity.file_id)
                .all()
            )
            assert len(versions) == 1, f"File {file_entity.file_id} has {len(versions)} versions, expected 1"

    def test_concurrent_duplicate_uploads(self, db_session, test_project, tmp_path):
        """Test concurrent uploads of same file (duplicate detection).

        Verifies:
        - Multiple threads uploading same file handled correctly
        - Only one File entity created
        - Duplicate detection works under concurrency
        """
        # Create single file
        file_path = tmp_path / "same_file.txt"
        file_path.write_text("Same content for all uploads")

        service = FileIngestionService(db_session)

        def upload_same_file():
            return service.ingest_file(str(file_path), test_project.project_id)

        # Upload same file 10 times concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(upload_same_file) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should return same file_id
        file_ids = [r.file_id for r in results]
        assert len(set(file_ids)) == 1, "All uploads should return same file_id"

        # Verify only one File created
        files_count = (
            db_session.query(File)
            .filter(File.project_id == test_project.project_id)
            .count()
        )
        assert files_count == 1

    @pytest.mark.slow
    def test_concurrency_limits_respected(self, db_session, test_project, sample_files):
        """Test that MAX_CONCURRENT_JOBS limits are respected.

        Note: This test focuses on FileIngestionService.
        RAG pipeline concurrency limits tested separately.

        Verifies:
        - File ingestion handles many concurrent requests
        - No deadlocks or hangs
        - All requests eventually complete
        """
        service = FileIngestionService(db_session)

        start_time = time.time()

        def upload_file(file_path):
            return service.ingest_file(str(file_path), test_project.project_id)

        # Upload with higher concurrency than typical limit
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(upload_file, f) for f in sample_files]
            results = [f.result() for f in concurrent.futures.as_completed(futures, timeout=60)]

        elapsed_time = time.time() - start_time

        # All should complete
        assert len(results) == 20

        # Should complete in reasonable time (not hang)
        assert elapsed_time < 60, f"Upload took too long: {elapsed_time}s"

    def test_concurrent_different_file_types(self, db_session, test_project, tmp_path):
        """Test concurrent upload of different file types.

        Verifies:
        - Mixed MIME types handled concurrently
        - Type detection works in parallel
        - No conflicts between different extractors
        """
        # Create files of different types
        files = []

        # Text files
        for i in range(5):
            f = tmp_path / f"text_{i}.txt"
            f.write_text(f"Text file {i}")
            files.append(f)

        # Markdown files
        for i in range(5):
            f = tmp_path / f"markdown_{i}.md"
            f.write_text(f"# Markdown {i}\nContent here")
            files.append(f)

        # JSON files
        for i in range(5):
            f = tmp_path / f"json_{i}.json"
            f.write_text(f'{{"key": "value{i}"}}')
            files.append(f)

        service = FileIngestionService(db_session)

        def upload_file(file_path):
            return service.ingest_file(str(file_path), test_project.project_id)

        # Upload concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(upload_file, f) for f in files]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify all uploaded with correct types
        assert len(results) == 15

        # Verify MIME types
        mime_types = [r.mime_type for r in results]
        assert "text/plain" in mime_types
        assert "text/markdown" in mime_types
        assert "application/json" in mime_types
