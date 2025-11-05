"""Contract tests for POST /api/v1/files/upload endpoint.

This module validates the file upload endpoint against the OpenAPI schema,
ensuring request and response formats match the API contract.

Tests:
- Multipart form data upload validation
- Required fields enforcement (file, project_id)
- Response schema validation (FileUploadResponse)
- HTTP status codes for various scenarios
"""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.schemas.file_schemas import FileUploadResponse
from src.models import File, FileSourceType, Project


@pytest.fixture
def test_client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF file content for testing."""
    # Minimal valid PDF structure
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/F1 <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n>>\n>>\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Test PDF) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000315 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n408\n%%EOF"


@pytest.fixture
def test_project(db_session):
    """Create test project for file uploads."""
    project = Project(
        name="test-project",
        drive_folder_id="test-folder-id",
        classification_rules=[],
        is_default=True,
        display_name="Test Project",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


class TestFileUploadContract:
    """Contract tests for POST /api/v1/files/upload."""

    def test_upload_multipart_form_data_structure(self, test_client, test_project, sample_pdf_bytes):
        """Test multipart form data upload with correct structure.

        Contract: Endpoint accepts multipart/form-data with:
        - file: binary file content
        - project_id: integer (optional)
        """
        # Prepare multipart form data
        files = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"project_id": test_project.project_id}

        # Send request
        response = test_client.post("/api/v1/files/upload", files=files, data=data)

        # Verify request was accepted (should be 200 or 202)
        assert response.status_code in [200, 201, 202], f"Unexpected status: {response.status_code}"

    def test_upload_required_field_file(self, test_client, test_project):
        """Test that 'file' field is required.

        Contract: Request without 'file' field should return 422 Unprocessable Entity.
        """
        # Send request without file
        data = {"project_id": test_project.project_id}

        response = test_client.post("/api/v1/files/upload", data=data)

        # Verify validation error
        assert response.status_code == 422

    def test_upload_optional_project_id(self, test_client, sample_pdf_bytes):
        """Test that 'project_id' field is optional.

        Contract: Request without project_id should use default project.
        """
        # Send request without project_id (should use default)
        files = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}

        response = test_client.post("/api/v1/files/upload", files=files)

        # Should succeed with default project
        assert response.status_code in [200, 201, 202], f"Unexpected status: {response.status_code}"

    def test_upload_response_schema(self, test_client, test_project, sample_pdf_bytes):
        """Test FileUploadResponse schema compliance.

        Contract: Response must include:
        - file_id (int)
        - file_version_id (int)
        - job_run_id (int, optional)
        - status (str)
        - message (str)
        """
        # Send valid upload request
        files = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"project_id": test_project.project_id}

        response = test_client.post("/api/v1/files/upload", files=files, data=data)

        # Verify response structure
        assert response.status_code in [200, 201, 202]
        response_data = response.json()

        # Validate against FileUploadResponse schema
        upload_response = FileUploadResponse(**response_data)

        # Verify required fields
        assert isinstance(upload_response.file_id, int)
        assert upload_response.file_id > 0
        assert isinstance(upload_response.file_version_id, int)
        assert upload_response.file_version_id > 0
        assert isinstance(upload_response.status, str)
        assert upload_response.status in ["queued", "duplicate_skipped", "processing"]
        assert isinstance(upload_response.message, str)
        assert len(upload_response.message) > 0

        # job_run_id is optional but should be int if present
        if upload_response.job_run_id is not None:
            assert isinstance(upload_response.job_run_id, int)
            assert upload_response.job_run_id > 0

    def test_upload_invalid_file_type_returns_400(self, test_client, test_project):
        """Test that unsupported file types return 400 Bad Request.

        Contract: Unsupported MIME types should return 400 with error details.
        """
        # Send invalid file type
        invalid_content = b"<html><body>Not a valid file</body></html>"
        files = {"file": ("test.html", io.BytesIO(invalid_content), "text/html")}
        data = {"project_id": test_project.project_id}

        response = test_client.post("/api/v1/files/upload", files=files, data=data)

        # Verify error response
        assert response.status_code == 400
        error_data = response.json()
        assert "detail" in error_data or "message" in error_data

    def test_upload_file_too_large_returns_400(self, test_client, test_project):
        """Test that oversized files return 400 Bad Request.

        Contract: Files exceeding size limits (50MB for documents) should return 400.
        """
        # Create 51MB file (exceeds 50MB document limit)
        large_content = b"X" * (51 * 1024 * 1024)
        files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}
        data = {"project_id": test_project.project_id}

        response = test_client.post("/api/v1/files/upload", files=files, data=data)

        # Verify error response
        assert response.status_code == 400
        error_data = response.json()
        assert "detail" in error_data or "message" in error_data
        # Check error mentions size limit
        error_text = str(error_data).lower()
        assert "size" in error_text or "large" in error_text or "limit" in error_text

    def test_upload_duplicate_file_returns_409(self, test_client, test_project, sample_pdf_bytes, db_session):
        """Test that duplicate files return 409 Conflict.

        Contract: Uploading same file (same hash) twice should return 409 with existing file_id.
        """
        # Upload file first time
        files_first = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"project_id": test_project.project_id}

        response_first = test_client.post("/api/v1/files/upload", files=files_first, data=data)
        assert response_first.status_code in [200, 201, 202]
        first_upload = response_first.json()

        # Upload same file again
        files_second = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}

        response_second = test_client.post("/api/v1/files/upload", files=files_second, data=data)

        # Verify duplicate detection
        assert response_second.status_code == 409
        duplicate_response = response_second.json()

        # Should include existing file_id
        assert "file_id" in duplicate_response or "existing_file_id" in duplicate_response
        # Should reference the first upload
        existing_id = duplicate_response.get("file_id") or duplicate_response.get("existing_file_id")
        assert existing_id == first_upload["file_id"]

    def test_upload_force_reprocess_parameter(self, test_client, test_project, sample_pdf_bytes):
        """Test force_reprocess query parameter bypasses duplicate detection.

        Contract: force_reprocess=true allows re-upload of duplicate files.
        """
        # Upload file first time
        files_first = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"project_id": test_project.project_id}

        response_first = test_client.post("/api/v1/files/upload", files=files_first, data=data)
        assert response_first.status_code in [200, 201, 202]

        # Upload same file with force_reprocess=true
        files_second = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}

        response_second = test_client.post(
            "/api/v1/files/upload?force_reprocess=true",
            files=files_second,
            data=data
        )

        # Should create new job run, not return 409
        assert response_second.status_code in [200, 201, 202]
        second_upload = response_second.json()

        # job_run_id should be different from first upload
        assert "job_run_id" in second_upload
        assert second_upload["job_run_id"] is not None

    def test_upload_nonexistent_project_returns_404(self, test_client, sample_pdf_bytes):
        """Test that invalid project_id returns 404 Not Found.

        Contract: Non-existent project_id should return 404.
        """
        # Send request with non-existent project_id
        files = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"project_id": 99999}  # Non-existent

        response = test_client.post("/api/v1/files/upload", files=files, data=data)

        # Verify error response
        assert response.status_code == 404

    def test_upload_content_type_header(self, test_client, test_project, sample_pdf_bytes):
        """Test that Content-Type is correctly set for multipart/form-data.

        Contract: Request must use multipart/form-data content type.
        """
        # TestClient automatically sets Content-Type for files parameter
        files = {"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"project_id": test_project.project_id}

        response = test_client.post("/api/v1/files/upload", files=files, data=data)

        # Should succeed (TestClient handles Content-Type automatically)
        assert response.status_code in [200, 201, 202]

    def test_upload_returns_job_run_id_for_processing(self, test_client, test_project, sample_pdf_bytes):
        """Test that successful upload returns job_run_id for tracking.

        Contract: New uploads (not duplicates) should trigger RAG pipeline and return job_run_id.
        """
        # Upload new file
        files = {"file": ("unique_file.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"project_id": test_project.project_id}

        response = test_client.post("/api/v1/files/upload", files=files, data=data)

        # Verify job_run_id is returned
        assert response.status_code in [200, 201, 202]
        upload_response = response.json()

        # For new files (not duplicates), job_run_id should be present
        if upload_response.get("status") != "duplicate_skipped":
            assert "job_run_id" in upload_response
            assert upload_response["job_run_id"] is not None
            assert isinstance(upload_response["job_run_id"], int)
            assert upload_response["job_run_id"] > 0
