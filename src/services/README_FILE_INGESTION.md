# File Ingestion Service Documentation

## Overview

The `FileIngestionService` is a comprehensive multi-format file ingestion system for the RAG-Enhanced Meeting Intelligence System. It handles validation, text extraction, hash-based duplicate detection, and database persistence for various document formats.

## Supported File Formats

### 1. PDF Files (`application/pdf`)
- **Extraction Method**: PyMuPDF (fitz) for native text extraction
- **OCR Fallback**: Tesseract OCR for scanned pages (automatic detection)
- **Metadata**: `page_count`, `ocr_pages`, `extraction_method`, `has_images`

**Example:**
```python
file = service.ingest_file("/path/to/report.pdf", project_id=1)
# Automatically detects scanned pages and uses OCR if needed
```

### 2. Word Documents (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
- **Extraction Method**: python-docx library
- **Features**: Preserves paragraph structure, extracts heading metadata
- **Metadata**: `paragraph_count`, `heading_count`, `extraction_method`

**Example:**
```python
file = service.ingest_file("/path/to/document.docx", project_id=1)
```

### 3. Markdown (`text/markdown`)
- **Extraction Method**: Plain text with structure parsing
- **Features**: Heading detection, structure preservation
- **Metadata**: `line_count`, `heading_count`, `extraction_method`

**Example:**
```python
file = service.ingest_file("/path/to/README.md", project_id=1)
```

### 4. Plain Text (`text/plain`)
- **Extraction Method**: Direct file read with encoding detection
- **Features**: UTF-8 first, chardet fallback for other encodings
- **Metadata**: `char_count`, `line_count`, `encoding`

**Example:**
```python
file = service.ingest_file("/path/to/notes.txt", project_id=1)
```

### 5. JSON Chat Exports (`application/json`)
- **Extraction Method**: LangChain JSONLoader with JMESPath
- **Supported Formats**: Slack, Microsoft Teams, WhatsApp
- **Metadata**: `message_count`, `participants`, `format`

**Example:**
```python
file = service.ingest_file("/path/to/slack_export.json", project_id=1, source_type="chat_export")
```

## File Size Limits

- **Audio files**: 100 MB maximum
- **Documents**: 50 MB maximum

Files exceeding these limits will raise `FileTooLargeError`.

## Key Features

### 1. Hash-Based Duplicate Detection

The service calculates SHA-256 hash of file content to detect duplicates:

```python
service = FileIngestionService(db_session)

# First ingestion creates new File entity
file1 = service.ingest_file("/path/to/doc.pdf", project_id=1)

# Second ingestion with same content returns existing File
file2 = service.ingest_file("/path/to/doc.pdf", project_id=1)

assert file1.file_id == file2.file_id  # Same entity returned
```

### 2. MIME Type Detection

Automatic MIME type detection using:
- `python-magic` (if available) - more accurate
- `mimetypes` module (fallback) - based on file extension

### 3. Format-Specific Metadata Extraction

Each format provides specific metadata:

```python
text, metadata = service.extract_text("/doc.pdf", "application/pdf")
print(metadata)
# {
#   "page_count": 15,
#   "ocr_pages": [3, 7],
#   "extraction_method": "fitz+ocr",
#   "has_images": True
# }
```

### 4. OCR Support for Scanned PDFs

Automatic detection of scanned pages:
- Pages with <50 characters trigger OCR attempt
- Uses Tesseract OCR if available
- Graceful fallback if OCR fails or unavailable

### 5. Database Persistence

Creates two entities:
- **File**: Logical file with project association
- **FileVersion**: Immutable snapshot with hash and content location

```python
file = service.ingest_file("/doc.pdf", project_id=1)

# Access version details
version = db.query(FileVersion).filter_by(
    version_id=file.current_version_id
).first()

print(f"Hash: {version.content_hash}")
print(f"Size: {version.file_size_bytes} bytes")
print(f"Location: {version.content_locator}")
```

## Usage Examples

### Basic Ingestion

```python
from src.models import get_db
from src.services.file_ingestion import FileIngestionService

db = next(get_db())
service = FileIngestionService(db)

# Ingest a file
file = service.ingest_file(
    file_path="/path/to/document.pdf",
    project_id=1,
    source_type="uploaded_document"
)

print(f"File ID: {file.file_id}")
print(f"Version ID: {file.current_version_id}")
```

### Extract Text with Metadata

```python
# Extract text without persisting to database
text, metadata = service.extract_text(
    file_path="/path/to/document.pdf",
    mime_type="application/pdf"
)

print(f"Extracted {len(text)} characters")
print(f"Metadata: {metadata}")
```

### File Validation

```python
# Validate before ingestion
is_valid, error_msg = service.validate_file("/path/to/file.pdf")

if not is_valid:
    print(f"Validation failed: {error_msg}")
else:
    file = service.ingest_file("/path/to/file.pdf", project_id=1)
```

### Check for Duplicates

```python
# Calculate hash
content_hash = service.calculate_hash("/path/to/file.pdf")

# Check if duplicate exists
duplicate = service.check_duplicate(content_hash, project_id=1)

if duplicate:
    print(f"Duplicate of file {duplicate.file_id}")
else:
    print("No duplicate found")
```

### Detect MIME Type

```python
mime_type = service.detect_mime_type("/path/to/unknown_file")
print(f"Detected MIME type: {mime_type}")
```

## Error Handling

### Exception Hierarchy

```
MeetHubError (base)
└── RAGError
    └── FileIngestionError (base for file ingestion)
        ├── UnsupportedFormatError
        ├── FileTooLargeError
        └── CorruptedFileError
```

### Handling Errors

```python
from src.services.file_ingestion import (
    FileIngestionService,
    UnsupportedFormatError,
    FileTooLargeError,
    CorruptedFileError,
)

try:
    file = service.ingest_file("/path/to/file.xyz", project_id=1)
except UnsupportedFormatError as e:
    print(f"Unsupported format: {e}")
    print(f"Hint: {e.troubleshooting_hint}")
except FileTooLargeError as e:
    print(f"File too large: {e}")
except CorruptedFileError as e:
    print(f"File corrupted: {e}")
except FileIngestionError as e:
    print(f"Ingestion failed: {e}")
    print(f"Details: {e.details}")
```

## Dependencies

### Required

```bash
pip install pymupdf python-docx sqlalchemy
```

### Optional (Enhanced Features)

```bash
# OCR for scanned PDFs
pip install pytesseract pillow

# More accurate MIME detection
pip install python-magic

# Encoding detection for text files
pip install chardet

# JSON path expressions for chat exports
pip install jmespath
```

### System Dependencies

**For OCR (optional):**
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-por tesseract-ocr-eng

# macOS
brew install tesseract tesseract-lang

# Windows
# Download installer from https://github.com/UB-Mannheim/tesseract/wiki
```

## Configuration

File size limits can be customized in `src/config.py`:

```python
class Settings(BaseSettings):
    # Add these settings
    max_audio_file_size_mb: int = Field(default=100, ge=1)
    max_document_file_size_mb: int = Field(default=50, ge=1)
```

Then update `FileIngestionService`:

```python
MAX_AUDIO_SIZE = settings.max_audio_file_size_mb * 1024 * 1024
MAX_DOCUMENT_SIZE = settings.max_document_file_size_mb * 1024 * 1024
```

## Implementation Details

### Text Extraction Flow

```
File Path
    ↓
validate_file() → Check existence, permissions, size
    ↓
detect_mime_type() → Determine file format
    ↓
extract_text() → Dispatch to format-specific extractor
    ↓
    ├── _extract_pdf() → PyMuPDF + OCR fallback
    ├── _extract_docx() → python-docx
    ├── _extract_json_chat() → JSON + JMESPath
    ├── _extract_markdown() → Plain text + structure
    └── _extract_plain_text() → Encoding detection
    ↓
(text_content, metadata)
```

### Ingestion Flow

```
File Path + Project ID
    ↓
validate_file()
    ↓
detect_mime_type()
    ↓
calculate_hash()
    ↓
check_duplicate() → Return existing if found
    ↓
extract_text()
    ↓
Create File entity
    ↓
Create FileVersion entity
    ↓
Link File.current_version_id → FileVersion
    ↓
Commit to database
    ↓
Return File entity
```

### Duplicate Detection Logic

1. Calculate SHA-256 hash of file content
2. Query `file_versions` table for matching hash
3. Filter by project_id (same file in different projects = not duplicate)
4. Exclude soft-deleted files
5. Return File entity if match found

## Testing

Run the example script:

```bash
python examples/file_ingestion_example.py
```

This demonstrates:
- Plain text ingestion
- Markdown ingestion
- JSON chat export ingestion
- Duplicate detection
- Validation error handling

## Performance Considerations

### Large Files

- Files are read in 64KB chunks for hash calculation (memory efficient)
- OCR is only triggered for pages with low text density
- Text extraction is done in a single pass

### Database Queries

- Duplicate check uses indexed query on `content_hash` and `project_id`
- Only one database transaction per ingestion
- Efficient JOIN between `FileVersion` and `File` tables

### Recommended Practices

1. **Batch Processing**: Use separate database sessions for concurrent ingestions
2. **Large PDFs**: Consider splitting PDFs >100 pages before ingestion
3. **OCR**: Tesseract can be slow; consider async processing for scanned PDFs
4. **Memory**: PDF rendering for OCR uses ~10MB per page at 300 DPI

## Future Enhancements

1. **Additional Formats**:
   - PowerPoint (PPTX)
   - Excel (XLSX)
   - HTML/EPUB
   - Audio transcription integration

2. **Advanced OCR**:
   - Language detection
   - Multi-column layout handling
   - Table extraction

3. **Cloud Storage**:
   - S3/GCS integration for content_locator
   - Streaming ingestion for large files

4. **Async Processing**:
   - Background ingestion jobs
   - Progress tracking
   - Batch ingestion API

## Troubleshooting

### Issue: "PyMuPDF not installed"

**Solution:**
```bash
pip install pymupdf
```

### Issue: "Tesseract not found"

**Solution:**
1. Install system package (see Dependencies section)
2. Or continue without OCR (native PDF text extraction still works)

### Issue: "File validation failed: File is not readable"

**Solution:**
- Check file permissions: `chmod +r /path/to/file`
- Verify file exists and path is absolute

### Issue: "Duplicate file detected" (unexpected)

**Explanation:**
- SHA-256 hash collision (same content)
- This is expected behavior for duplicate detection

**Solution:**
- To force new ingestion, modify file content slightly
- Or use different project_id

### Issue: "MIME type detection returns application/octet-stream"

**Solution:**
1. Install python-magic: `pip install python-magic`
2. Or ensure file has correct extension (.pdf, .docx, etc.)

## API Reference

See docstrings in `src/services/file_ingestion.py` for complete API documentation:

```python
help(FileIngestionService)
help(FileIngestionService.ingest_file)
help(FileIngestionService.extract_text)
```

## Related Components

- **Models**: `src/models/file.py`, `src/models/file_version.py`
- **Exceptions**: `src/utils/exceptions.py` (FileIngestionError hierarchy)
- **Configuration**: `src/config.py` (file size limits)
- **Chunking**: `src/services/chunking/` (next step after ingestion)
- **RAG Pipeline**: `src/services/rag_pipeline.py` (orchestrates ingestion → chunking → embedding)
