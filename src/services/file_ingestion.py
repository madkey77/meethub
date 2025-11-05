"""Multi-format file ingestion service for RAG pipeline.

This module provides a comprehensive file ingestion service supporting:
- PDF (native text extraction + OCR fallback for scanned pages)
- DOCX (Word documents)
- Markdown
- Plain text
- JSON (chat exports from Slack/Teams/WhatsApp)

The service handles:
- MIME type detection
- File validation (size limits, format support)
- Text extraction with format-specific metadata
- SHA-256 hash calculation for duplicate detection
- Database persistence of File and FileVersion entities
"""

import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from src.config import settings
from src.models import File, FileSourceType, FileVersion
from src.utils.exceptions import FileIngestionError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class UnsupportedFormatError(FileIngestionError):
    """File format is not supported."""

    troubleshooting_hint = (
        "Supported formats: PDF, DOCX, Markdown (.md), Plain Text (.txt), JSON (chat exports). "
        "Check MIME type and file extension."
    )


class FileTooLargeError(FileIngestionError):
    """File exceeds size limits."""

    troubleshooting_hint = (
        "Audio files: max 100MB. Documents: max 50MB. "
        "Consider compressing or splitting large files."
    )


class CorruptedFileError(FileIngestionError):
    """File is corrupted or password-protected."""

    troubleshooting_hint = (
        "File may be corrupted, password-protected, or malformed. "
        "Try opening the file manually to verify integrity."
    )


class FileIngestionService:
    """Multi-format file ingestion service for RAG pipeline.

    Handles file validation, text extraction, hash calculation, duplicate detection,
    and database persistence of File and FileVersion entities.

    Example:
        >>> service = FileIngestionService(db_session)
        >>> file = service.ingest_file("/path/to/document.pdf", project_id=1)
        >>> print(f"Ingested: {file.relative_path} (version: {file.current_version_id})")
    """

    # Supported MIME types and their extractors
    SUPPORTED_MIME_TYPES = {
        "application/pdf": "_extract_pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "_extract_docx",
        "text/markdown": "_extract_markdown",
        "text/plain": "_extract_plain_text",
        "application/json": "_extract_json_chat",
    }

    # File size limits (in bytes)
    MAX_AUDIO_SIZE = 100 * 1024 * 1024  # 100 MB
    MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50 MB

    def __init__(self, db_session: Session):
        """Initialize file ingestion service.

        Args:
            db_session: SQLAlchemy database session for persistence operations
        """
        self.db = db_session
        self.logger = logger.bind(service="file_ingestion")

    def ingest_file(
        self,
        file_path: str,
        project_id: int,
        source_type: str = "uploaded_document",
    ) -> File:
        """Main entry point for file ingestion.

        Performs complete ingestion workflow:
        1. Validate file (exists, readable, size limits)
        2. Detect MIME type and check format support
        3. Calculate SHA-256 hash
        4. Check for duplicates (same hash in project)
        5. Extract text content with metadata
        6. Create or update File and FileVersion entities
        7. Persist to database

        Args:
            file_path: Absolute path to file on filesystem
            project_id: Project ID for organizational grouping
            source_type: Source classification (meeting, uploaded_document, chat_export)

        Returns:
            File entity (with current_version_id set)

        Raises:
            FileIngestionError: If validation, extraction, or persistence fails
            UnsupportedFormatError: If file format is not supported
            FileTooLargeError: If file exceeds size limits
            CorruptedFileError: If file cannot be read or extracted

        Example:
            >>> service = FileIngestionService(db_session)
            >>> file = service.ingest_file("/uploads/report.pdf", project_id=5)
            >>> print(f"File ID: {file.file_id}, Version: {file.current_version_id}")
        """
        path = Path(file_path)
        self.logger.info(
            "Starting file ingestion",
            file_path=str(path),
            project_id=project_id,
            source_type=source_type,
        )

        try:
            # Step 1: Validate file
            is_valid, error_msg = self.validate_file(file_path)
            if not is_valid:
                raise FileIngestionError(
                    f"File validation failed: {error_msg}",
                    details={"file_path": file_path, "error": error_msg},
                )

            # Step 2: Detect MIME type
            mime_type = self.detect_mime_type(file_path)
            if mime_type not in self.SUPPORTED_MIME_TYPES:
                raise UnsupportedFormatError(
                    f"Unsupported file format: {mime_type}",
                    details={"file_path": file_path, "mime_type": mime_type},
                )

            # Step 3: Calculate hash
            content_hash = self.calculate_hash(file_path)
            self.logger.debug(
                "File hash calculated",
                content_hash=content_hash,
                file_path=file_path,
            )

            # Step 4: Check for duplicates
            duplicate_file = self.check_duplicate(content_hash, project_id)
            if duplicate_file:
                self.logger.info(
                    "Duplicate file detected",
                    existing_file_id=duplicate_file.file_id,
                    content_hash=content_hash,
                )
                return duplicate_file

            # Step 5: Extract text content
            text_content, metadata = self.extract_text(file_path, mime_type)
            self.logger.info(
                "Text extracted successfully",
                text_length=len(text_content),
                metadata=metadata,
            )

            # Step 6: Create File entity
            file_entity = File(
                relative_path=str(path.name),  # Just filename for now
                mime_type=mime_type,
                source_type=FileSourceType(source_type),
                project_id=project_id,
                deleted=False,
            )
            self.db.add(file_entity)
            self.db.flush()  # Get file_id

            # Step 7: Create FileVersion entity
            file_size = path.stat().st_size
            file_version = FileVersion(
                file_id=file_entity.file_id,
                content_hash=content_hash,
                file_size_bytes=file_size,
                content_locator=str(path.absolute()),
                is_current=True,
            )
            self.db.add(file_version)
            self.db.flush()  # Get version_id

            # Step 8: Update File with current version
            file_entity.current_version_id = file_version.version_id
            self.db.commit()

            self.logger.info(
                "File ingestion completed",
                file_id=file_entity.file_id,
                version_id=file_version.version_id,
                content_hash=content_hash,
            )

            return file_entity

        except FileIngestionError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            self.logger.error(
                "Unexpected error during file ingestion",
                error=str(e),
                file_path=file_path,
            )
            raise FileIngestionError(
                f"File ingestion failed: {str(e)}",
                details={"file_path": file_path, "error_type": type(e).__name__},
            ) from e

    def extract_text(self, file_path: str, mime_type: str) -> Tuple[str, dict]:
        """Extract text content from file with format-specific metadata.

        Dispatches to appropriate format-specific extractor based on MIME type.

        Args:
            file_path: Path to file
            mime_type: MIME type (must be in SUPPORTED_MIME_TYPES)

        Returns:
            Tuple of (text_content, metadata_dict)
            - text_content: Extracted text as string
            - metadata: Format-specific metadata (page_count, speaker, etc.)

        Raises:
            UnsupportedFormatError: If MIME type not supported
            CorruptedFileError: If extraction fails

        Example:
            >>> text, meta = service.extract_text("/doc.pdf", "application/pdf")
            >>> print(f"Extracted {len(text)} chars, {meta['page_count']} pages")
        """
        if mime_type not in self.SUPPORTED_MIME_TYPES:
            raise UnsupportedFormatError(
                f"No extractor for MIME type: {mime_type}",
                details={"mime_type": mime_type},
            )

        extractor_method = getattr(self, self.SUPPORTED_MIME_TYPES[mime_type])
        try:
            return extractor_method(file_path)
        except Exception as e:
            self.logger.error(
                "Text extraction failed",
                file_path=file_path,
                mime_type=mime_type,
                error=str(e),
            )
            raise CorruptedFileError(
                f"Failed to extract text: {str(e)}",
                details={
                    "file_path": file_path,
                    "mime_type": mime_type,
                    "error_type": type(e).__name__,
                },
            ) from e

    def _extract_pdf(self, file_path: str) -> Tuple[str, dict]:
        """Extract text from PDF using PyMuPDF (fitz) with OCR fallback.

        Uses PyMuPDF for native text extraction. Detects scanned pages (low text density)
        and falls back to Tesseract OCR if available.

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (text_content, metadata)
            - text_content: Extracted text with page breaks
            - metadata: {"page_count": int, "ocr_pages": list, "extraction_method": str}

        Example:
            >>> text, meta = service._extract_pdf("/report.pdf")
            >>> print(f"Pages: {meta['page_count']}, OCR used: {len(meta['ocr_pages'])}")
        """
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise FileIngestionError(
                "PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF",
                details={"required_package": "PyMuPDF"},
            ) from e

        doc = fitz.open(file_path)
        text_pages = []
        ocr_pages = []
        tesseract_available = self._check_tesseract_available()

        for page_num, page in enumerate(doc):
            text = page.get_text()

            # Detect scanned pages (low text density)
            if len(text.strip()) < 50 and tesseract_available:
                # Try OCR fallback
                self.logger.debug(
                    "Low text density detected, attempting OCR",
                    page=page_num + 1,
                )
                try:
                    ocr_text = self._ocr_pdf_page(page)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                        ocr_pages.append(page_num + 1)
                except Exception as ocr_error:
                    self.logger.warning(
                        "OCR failed for page",
                        page=page_num + 1,
                        error=str(ocr_error),
                    )

            text_pages.append(text)

        doc.close()

        full_text = "\n\n--- Page Break ---\n\n".join(text_pages)
        metadata = {
            "page_count": len(text_pages),
            "ocr_pages": ocr_pages,
            "extraction_method": "fitz+ocr" if ocr_pages else "fitz",
            "has_images": True,  # PDFs typically have images
        }

        return full_text, metadata

    def _ocr_pdf_page(self, page) -> str:
        """Perform OCR on a PDF page using Tesseract.

        Args:
            page: PyMuPDF page object

        Returns:
            OCR-extracted text

        Raises:
            Exception: If OCR fails
        """
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise FileIngestionError(
                "pytesseract or PIL not installed. Install with: pip install pytesseract Pillow",
                details={"required_packages": "pytesseract, Pillow"},
            ) from e

        # Render page as image
        pix = page.get_pixmap(dpi=300)  # High DPI for better OCR
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Perform OCR
        text = pytesseract.image_to_string(img, lang="por+eng")  # Portuguese + English
        return text

    def _check_tesseract_available(self) -> bool:
        """Check if Tesseract OCR is available."""
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def _extract_docx(self, file_path: str) -> Tuple[str, dict]:
        """Extract text from Word document (.docx) using python-docx.

        Preserves paragraph structure and extracts heading metadata.

        Args:
            file_path: Path to DOCX file

        Returns:
            Tuple of (text_content, metadata)
            - text_content: Extracted text with paragraph breaks
            - metadata: {"heading_count": int, "paragraph_count": int}

        Example:
            >>> text, meta = service._extract_docx("/report.docx")
            >>> print(f"Headings: {meta['heading_count']}, Paragraphs: {meta['paragraph_count']}")
        """
        try:
            from docx import Document
        except ImportError as e:
            raise FileIngestionError(
                "python-docx not installed. Install with: pip install python-docx",
                details={"required_package": "python-docx"},
            ) from e

        doc = Document(file_path)
        paragraphs = []
        heading_count = 0

        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
                # Check if paragraph is a heading
                if para.style.name.startswith("Heading"):
                    heading_count += 1

        full_text = "\n\n".join(paragraphs)
        metadata = {
            "paragraph_count": len(paragraphs),
            "heading_count": heading_count,
            "extraction_method": "python-docx",
        }

        return full_text, metadata

    def _extract_json_chat(self, file_path: str) -> Tuple[str, dict]:
        """Extract text from JSON chat exports (Slack, Teams, WhatsApp).

        Uses JMESPath expressions for different chat formats. Supports:
        - Slack: messages with user/text/timestamp
        - Microsoft Teams: similar structure
        - WhatsApp: message array format

        Args:
            file_path: Path to JSON file

        Returns:
            Tuple of (text_content, metadata)
            - text_content: Formatted chat transcript
            - metadata: {"message_count": int, "participants": list, "format": str}

        Example:
            >>> text, meta = service._extract_json_chat("/slack_export.json")
            >>> print(f"Messages: {meta['message_count']}, Users: {len(meta['participants'])}")
        """
        try:
            import jmespath
        except ImportError:
            # Fallback to basic JSON parsing if jmespath not available
            jmespath = None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Detect format and extract messages
        if isinstance(data, list):
            # Slack/Teams format: array of message objects
            messages = data
            format_type = "slack/teams"
        elif isinstance(data, dict) and "messages" in data:
            # Alternative format with messages key
            messages = data["messages"]
            format_type = "generic"
        else:
            # Unknown format, try to extract any text
            messages = []
            format_type = "unknown"

        # Extract and format messages
        formatted_messages = []
        participants = set()

        for msg in messages:
            if isinstance(msg, dict):
                user = msg.get("user", msg.get("sender", msg.get("from", "Unknown")))
                text = msg.get("text", msg.get("message", msg.get("content", "")))
                timestamp = msg.get("ts", msg.get("timestamp", ""))

                if text:
                    participants.add(user)
                    formatted_messages.append(f"[{timestamp}] {user}: {text}")

        full_text = "\n".join(formatted_messages)
        metadata = {
            "message_count": len(formatted_messages),
            "participants": list(participants),
            "format": format_type,
            "extraction_method": "json",
        }

        return full_text, metadata

    def _extract_markdown(self, file_path: str) -> Tuple[str, dict]:
        """Extract text from Markdown file.

        Reads as plain text and optionally parses structure (headings).

        Args:
            file_path: Path to Markdown file

        Returns:
            Tuple of (text_content, metadata)
            - text_content: Raw markdown text
            - metadata: {"heading_count": int, "line_count": int}

        Example:
            >>> text, meta = service._extract_markdown("/README.md")
            >>> print(f"Headings: {meta['heading_count']}")
        """
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Count headings (lines starting with #)
        lines = text.split("\n")
        heading_count = sum(1 for line in lines if line.strip().startswith("#"))

        metadata = {
            "line_count": len(lines),
            "heading_count": heading_count,
            "extraction_method": "plain_text",
        }

        return text, metadata

    def _extract_plain_text(self, file_path: str) -> Tuple[str, dict]:
        """Extract text from plain text file with encoding detection.

        Tries UTF-8 first, falls back to chardet if available.

        Args:
            file_path: Path to text file

        Returns:
            Tuple of (text_content, metadata)
            - text_content: File contents as string
            - metadata: {"char_count": int, "line_count": int, "encoding": str}

        Example:
            >>> text, meta = service._extract_plain_text("/notes.txt")
            >>> print(f"Encoding: {meta['encoding']}, Lines: {meta['line_count']}")
        """
        # Try UTF-8 first
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            encoding = "utf-8"
        except UnicodeDecodeError:
            # Fall back to chardet
            try:
                import chardet

                with open(file_path, "rb") as f:
                    raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected["encoding"] or "utf-8"

                with open(file_path, "r", encoding=encoding) as f:
                    text = f.read()
            except Exception:
                # Last resort: latin-1 (never fails)
                with open(file_path, "r", encoding="latin-1") as f:
                    text = f.read()
                encoding = "latin-1"

        lines = text.split("\n")
        metadata = {
            "char_count": len(text),
            "line_count": len(lines),
            "encoding": encoding,
            "extraction_method": "plain_text",
        }

        return text, metadata

    def detect_mime_type(self, file_path: str) -> str:
        """Detect MIME type of file.

        Uses python-magic if available, otherwise falls back to mimetypes module.

        Args:
            file_path: Path to file

        Returns:
            MIME type string (e.g., "application/pdf")

        Example:
            >>> mime = service.detect_mime_type("/doc.pdf")
            >>> print(mime)  # "application/pdf"
        """
        # Try python-magic first (more accurate)
        try:
            import magic

            mime = magic.from_file(file_path, mime=True)
            return mime
        except (ImportError, Exception):
            pass

        # Fall back to mimetypes module
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            return mime_type

        # Default to octet-stream if unknown
        return "application/octet-stream"

    def calculate_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file content.

        Reads file in chunks for memory efficiency.

        Args:
            file_path: Path to file

        Returns:
            SHA-256 hash as hex string (64 characters)

        Example:
            >>> hash_val = service.calculate_hash("/doc.pdf")
            >>> print(len(hash_val))  # 64
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in 64KB chunks for memory efficiency
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """Validate file exists, is readable, and meets size limits.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if validation passes
            - error_message: Empty string if valid, error description if invalid

        Example:
            >>> is_valid, error = service.validate_file("/doc.pdf")
            >>> if not is_valid:
            ...     print(f"Validation failed: {error}")
        """
        path = Path(file_path)

        # Check existence
        if not path.exists():
            return False, f"File does not exist: {file_path}"

        # Check if it's a file (not directory)
        if not path.is_file():
            return False, f"Path is not a file: {file_path}"

        # Check readable
        if not path.stat().st_mode & 0o400:  # Read permission
            return False, f"File is not readable: {file_path}"

        # Check not empty
        file_size = path.stat().st_size
        if file_size == 0:
            return False, "File is empty"

        # Check size limits based on extension
        if path.suffix.lower() in [".mp3", ".mp4", ".wav", ".m4a", ".flac", ".ogg"]:
            # Audio file
            if file_size > self.MAX_AUDIO_SIZE:
                return (
                    False,
                    f"Audio file too large: {file_size / (1024*1024):.1f}MB (max: 100MB)",
                )
        else:
            # Document file
            if file_size > self.MAX_DOCUMENT_SIZE:
                return (
                    False,
                    f"Document too large: {file_size / (1024*1024):.1f}MB (max: 50MB)",
                )

        return True, ""

    def check_duplicate(self, content_hash: str, project_id: int) -> Optional[File]:
        """Check if file with same hash already exists in project.

        Queries for FileVersion with matching hash in same project.

        Args:
            content_hash: SHA-256 hash to search for
            project_id: Project ID to scope search

        Returns:
            File entity if duplicate found, None otherwise

        Example:
            >>> duplicate = service.check_duplicate("abc123...", project_id=1)
            >>> if duplicate:
            ...     print(f"Duplicate of file {duplicate.file_id}")
        """
        # Query for existing FileVersion with same hash in this project
        existing_version = (
            self.db.query(FileVersion)
            .join(File, File.file_id == FileVersion.file_id)
            .filter(
                FileVersion.content_hash == content_hash,
                File.project_id == project_id,
                File.deleted == False,  # noqa: E712
            )
            .first()
        )

        if existing_version:
            return existing_version.file
        return None
