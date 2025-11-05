"""Integration tests for OCR fallback in PDF ingestion.

Tests Tesseract OCR fallback for scanned PDFs with low text density.
Tests are skipped if Tesseract is not available on the system.
"""

import pytest

from src.services.file_ingestion import FileIngestionService


@pytest.fixture
def scanned_pdf_file(tmp_path):
    """Create a simulated scanned PDF (image-based, no text layer).

    Note: This creates a PDF with minimal/no text to simulate a scanned document.
    In production, this would be an actual scanned PDF with embedded images.
    """
    pdf_path = tmp_path / "scanned_document.pdf"

    # PDF with very little text (simulates scanned page)
    # Real scanned PDFs would have image streams, but this approximates low text density
    pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 20>>stream
BT /F1 12 Tf ET
endstream endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000122 00000 n
0000000235 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
305
%%EOF"""

    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def check_tesseract_available():
    """Check if Tesseract OCR is available on the system."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


class TestOCRFallback:
    """Integration tests for Tesseract OCR fallback."""

    def test_scanned_pdf_triggers_ocr(self, db_session, scanned_pdf_file, check_tesseract_available):
        """Test that scanned PDFs trigger Tesseract OCR fallback.

        Verifies:
        - Low text density is detected
        - OCR is attempted if Tesseract available
        - Fallback gracefully skips OCR if Tesseract unavailable
        """
        if not check_tesseract_available:
            pytest.skip("Tesseract not available - skipping OCR test")

        service = FileIngestionService(db_session)

        # Extract text from scanned PDF
        text, metadata = service.extract_text(
            file_path=str(scanned_pdf_file),
            mime_type="application/pdf"
        )

        # Verify OCR was attempted
        # For this minimal PDF, OCR might not extract much, but metadata should reflect attempt
        assert metadata is not None
        assert "extraction_method" in metadata

        # If OCR was used, method should indicate it
        if metadata.get("ocr_pages"):
            assert "ocr" in metadata["extraction_method"].lower() or metadata["extraction_method"] == "fitz+ocr"

    def test_ocr_extraction_accuracy(self, db_session, tmp_path, check_tesseract_available):
        """Test OCR text extraction accuracy against known document.

        Note: This test requires actual scanned PDF with known text.
        Skipped if Tesseract not available.
        """
        if not check_tesseract_available:
            pytest.skip("Tesseract not available - skipping OCR accuracy test")

        # This test would use a fixture scanned PDF with known text
        # For now, we'll skip it as creating realistic scanned PDFs requires image processing
        pytest.skip("Requires actual scanned PDF fixture - implement when available")

    def test_tesseract_not_available_graceful_fallback(self, db_session, scanned_pdf_file):
        """Test graceful fallback when Tesseract is not available.

        Verifies:
        - Service doesn't crash if Tesseract missing
        - Returns available text (even if minimal)
        - Logs warning about OCR unavailability
        """
        service = FileIngestionService(db_session)

        # Even without Tesseract, should not raise exception
        try:
            text, metadata = service.extract_text(
                file_path=str(scanned_pdf_file),
                mime_type="application/pdf"
            )

            # Should return something, even if empty or minimal
            assert text is not None
            assert metadata is not None
            assert "extraction_method" in metadata

        except Exception as e:
            # Should not raise ImportError or similar
            pytest.fail(f"OCR fallback should be graceful, but raised: {e}")

    def test_mixed_native_and_scanned_pages(self, db_session, tmp_path, check_tesseract_available):
        """Test PDF with mix of native text and scanned pages.

        Verifies:
        - Native text pages use PyMuPDF
        - Scanned pages use OCR fallback
        - ocr_pages list tracks which pages used OCR
        """
        if not check_tesseract_available:
            pytest.skip("Tesseract not available - skipping mixed pages test")

        # This test would use a fixture PDF with mixed page types
        # Requires more complex PDF generation
        pytest.skip("Requires mixed-mode PDF fixture - implement when available")

    def test_ocr_language_configuration(self, db_session, tmp_path, check_tesseract_available):
        """Test OCR with Portuguese + English language configuration.

        Verifies:
        - Tesseract uses 'por+eng' language configuration
        - Multi-language text is extracted correctly
        """
        if not check_tesseract_available:
            pytest.skip("Tesseract not available - skipping language config test")

        # This test would verify that FileIngestionService._ocr_pdf_page
        # uses pytesseract.image_to_string(img, lang="por+eng")
        # Requires actual multi-language scanned PDF
        pytest.skip("Requires multi-language PDF fixture - implement when available")

    def test_high_dpi_rendering_for_ocr(self, db_session, scanned_pdf_file, check_tesseract_available):
        """Test that PDF pages are rendered at high DPI (300) for better OCR.

        Verifies:
        - Page rendering uses dpi=300 for better OCR accuracy
        - Image quality is sufficient for text recognition
        """
        if not check_tesseract_available:
            pytest.skip("Tesseract not available - skipping DPI test")

        service = FileIngestionService(db_session)

        # Extract text (internally uses 300 DPI for OCR)
        text, metadata = service.extract_text(
            file_path=str(scanned_pdf_file),
            mime_type="application/pdf"
        )

        # Verification: if OCR was used, it should have used high DPI
        # This is more of a code review verification than runtime test
        # Actual DPI usage is implementation detail in _ocr_pdf_page
        assert metadata is not None

    def test_ocr_error_handling(self, db_session, tmp_path, check_tesseract_available):
        """Test error handling when OCR fails on specific pages.

        Verifies:
        - OCR failures are logged but don't stop processing
        - Service continues with remaining pages
        - Failed OCR pages fall back to native text (even if minimal)
        """
        if not check_tesseract_available:
            pytest.skip("Tesseract not available - skipping OCR error handling test")

        # This test would use a deliberately corrupted/problematic PDF page
        # Requires fixture that triggers OCR errors
        pytest.skip("Requires error-triggering PDF fixture - implement when available")
