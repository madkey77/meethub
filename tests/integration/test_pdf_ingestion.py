"""Integration tests for PDF file ingestion.

Tests PDF text extraction with PyMuPDF, verifies File and FileVersion creation,
and ensures RAG pipeline is triggered correctly.
"""

import hashlib
import tempfile
from pathlib import Path

import pytest

from src.models import File, FileSourceType, FileVersion, JobRun, JobRunStatus, Project
from src.services.file_ingestion import FileIngestionService


@pytest.fixture
def sample_pdf_file(tmp_path):
    """Create a sample PDF file with native text content."""
    pdf_path = tmp_path / "sample_document.pdf"

    # Minimal valid PDF with text content
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 125
>>
stream
BT
/F1 24 Tf
100 700 Td
(Meeting Intelligence System) Tj
0 -50 Td
(This is a test PDF document for ingestion testing.) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000315 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
489
%%EOF"""

    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def test_project(db_session):
    """Create test project for file uploads."""
    project = Project(
        name="pdf-test-project",
        drive_folder_id="test-folder-pdf",
        classification_rules=[],
        is_default=False,
        display_name="PDF Test Project",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


class TestPDFIngestion:
    """Integration tests for PDF file ingestion."""

    def test_pdf_upload_creates_file_entity(self, db_session, test_project, sample_pdf_file):
        """Test that PDF upload creates File entity in database.

        Verifies:
        - File record is created
        - MIME type is detected as application/pdf
        - Source type is set correctly
        - Project ID is linked
        """
        service = FileIngestionService(db_session)

        # Ingest PDF file
        file_entity = service.ingest_file(
            file_path=str(sample_pdf_file),
            project_id=test_project.project_id,
            source_type="uploaded_document"
        )

        # Verify File entity created
        assert file_entity is not None
        assert file_entity.file_id > 0
        assert file_entity.mime_type == "application/pdf"
        assert file_entity.source_type == FileSourceType.UPLOADED_DOCUMENT
        assert file_entity.project_id == test_project.project_id
        assert file_entity.deleted is False

    def test_pdf_upload_creates_file_version(self, db_session, test_project, sample_pdf_file):
        """Test that PDF upload creates FileVersion with correct hash.

        Verifies:
        - FileVersion record is created
        - SHA-256 hash is calculated correctly
        - File size is recorded
        - Version is marked as current
        """
        service = FileIngestionService(db_session)

        # Calculate expected hash
        with open(sample_pdf_file, "rb") as f:
            expected_hash = hashlib.sha256(f.read()).hexdigest()

        # Ingest PDF file
        file_entity = service.ingest_file(
            file_path=str(sample_pdf_file),
            project_id=test_project.project_id,
            source_type="uploaded_document"
        )

        # Verify FileVersion created
        assert file_entity.current_version_id is not None

        version = (
            db_session.query(FileVersion)
            .filter(FileVersion.version_id == file_entity.current_version_id)
            .first()
        )

        assert version is not None
        assert version.content_hash == expected_hash
        assert version.file_size_bytes == sample_pdf_file.stat().st_size
        assert version.is_current is True
        assert version.content_locator == str(sample_pdf_file.absolute())

    def test_pdf_text_extraction_with_pymupdf(self, db_session, test_project, sample_pdf_file):
        """Test text extraction from PDF using PyMuPDF (fitz).

        Verifies:
        - Text is extracted from native PDF
        - Extracted text contains expected content
        - Metadata includes page count
        """
        service = FileIngestionService(db_session)

        # Extract text
        text, metadata = service.extract_text(
            file_path=str(sample_pdf_file),
            mime_type="application/pdf"
        )

        # Verify text extraction
        assert text is not None
        assert len(text) > 0
        assert "Meeting Intelligence System" in text or "test PDF" in text

        # Verify metadata
        assert metadata is not None
        assert "page_count" in metadata
        assert metadata["page_count"] == 1
        assert "extraction_method" in metadata
        assert "fitz" in metadata["extraction_method"]

    def test_pdf_native_text_extraction(self, db_session, test_project, tmp_path):
        """Test extraction from PDF with digital (native) text.

        Verifies:
        - Native text PDFs use PyMuPDF without OCR
        - Text density is high (not scanned)
        - Extraction method is 'fitz' (not 'fitz+ocr')
        """
        # Create PDF with more substantial text content
        pdf_path = tmp_path / "digital_text.pdf"
        pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 200>>stream
BT /F1 12 Tf 50 700 Td (This is a digital PDF with native text content.) Tj 0 -20 Td (It should be extracted using PyMuPDF without requiring OCR.) Tj 0 -20 Td (The text density is high and the content is clearly digital.) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000400 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
650
%%EOF"""
        pdf_path.write_bytes(pdf_content)

        service = FileIngestionService(db_session)

        # Extract text
        text, metadata = service.extract_text(
            file_path=str(pdf_path),
            mime_type="application/pdf"
        )

        # Verify native text extraction
        assert len(text) > 50  # Substantial text content
        assert "digital PDF" in text or "native text" in text

        # Should not use OCR for digital PDF
        assert metadata["extraction_method"] == "fitz"
        assert metadata.get("ocr_pages", []) == []

    def test_pdf_ingestion_triggers_rag_pipeline(self, db_session, test_project, sample_pdf_file):
        """Test that PDF ingestion can trigger RAG pipeline.

        Note: This test verifies the service returns File entity correctly.
        Actual RAG pipeline triggering is tested in API layer.
        """
        service = FileIngestionService(db_session)

        # Ingest file
        file_entity = service.ingest_file(
            file_path=str(sample_pdf_file),
            project_id=test_project.project_id,
            source_type="uploaded_document"
        )

        # Verify file is ready for RAG processing
        assert file_entity.current_version_id is not None
        assert file_entity.deleted is False

        # File can now be passed to RAG pipeline
        version = (
            db_session.query(FileVersion)
            .filter(FileVersion.version_id == file_entity.current_version_id)
            .first()
        )
        assert version.content_locator is not None

    def test_pdf_duplicate_detection(self, db_session, test_project, sample_pdf_file):
        """Test duplicate PDF detection by content hash.

        Verifies:
        - Same file uploaded twice is detected as duplicate
        - Returns existing File entity
        - Does not create duplicate FileVersion
        """
        service = FileIngestionService(db_session)

        # Upload first time
        file_first = service.ingest_file(
            file_path=str(sample_pdf_file),
            project_id=test_project.project_id,
            source_type="uploaded_document"
        )

        # Upload same file again
        file_second = service.ingest_file(
            file_path=str(sample_pdf_file),
            project_id=test_project.project_id,
            source_type="uploaded_document"
        )

        # Should return same file
        assert file_first.file_id == file_second.file_id
        assert file_first.current_version_id == file_second.current_version_id

        # Verify only one version exists
        versions = (
            db_session.query(FileVersion)
            .filter(FileVersion.file_id == file_first.file_id)
            .all()
        )
        assert len(versions) == 1

    def test_pdf_metadata_extraction(self, db_session, test_project, tmp_path):
        """Test metadata extraction from PDF (page count, OCR usage).

        Verifies:
        - Page count is extracted
        - Extraction method is recorded
        - OCR page list is tracked (empty for native PDFs)
        """
        # Create multi-page PDF
        pdf_path = tmp_path / "multipage.pdf"
        pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 2/Kids[3 0 R 5 0 R]>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 50>>stream
BT /F1 12 Tf 50 700 Td (Page 1 content) Tj ET
endstream endobj
5 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 6 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>>>endobj
6 0 obj<</Length 50>>stream
BT /F1 12 Tf 50 700 Td (Page 2 content) Tj ET
endstream endobj
xref
0 7
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000122 00000 n
0000000310 00000 n
0000000410 00000 n
0000000610 00000 n
trailer<</Size 7/Root 1 0 R>>
startxref
710
%%EOF"""
        pdf_path.write_bytes(pdf_content)

        service = FileIngestionService(db_session)

        # Extract text with metadata
        text, metadata = service.extract_text(
            file_path=str(pdf_path),
            mime_type="application/pdf"
        )

        # Verify metadata
        assert metadata["page_count"] == 2
        assert "Page 1" in text or "Page 2" in text
        assert "extraction_method" in metadata
        assert metadata["extraction_method"] == "fitz"  # No OCR needed
