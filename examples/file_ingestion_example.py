"""Example usage of FileIngestionService.

This script demonstrates how to use the FileIngestionService to ingest various file formats
into the RAG pipeline.

Prerequisites:
    - Database initialized with tables (run alembic upgrade head)
    - At least one project exists in the database
    - Test files available in various formats

Usage:
    python examples/file_ingestion_example.py
"""

from pathlib import Path

from src.models import SessionLocal, get_db, init_db, Project
from src.services.file_ingestion import FileIngestionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


def create_sample_files(temp_dir: Path):
    """Create sample files for testing each format."""
    # Sample plain text
    txt_file = temp_dir / "sample.txt"
    txt_file.write_text("This is a sample plain text document.\nIt has multiple lines.\n")

    # Sample markdown
    md_file = temp_dir / "sample.md"
    md_file.write_text(
        "# Sample Markdown\n\n"
        "## Introduction\n\n"
        "This is a **markdown** document.\n\n"
        "## Details\n\n"
        "- Item 1\n- Item 2\n"
    )

    # Sample JSON chat export (Slack format)
    json_file = temp_dir / "chat_export.json"
    import json

    chat_data = [
        {
            "user": "alice@example.com",
            "text": "Hey team, let's discuss the project status",
            "ts": "2025-01-15T10:00:00Z",
        },
        {
            "user": "bob@example.com",
            "text": "Sure! The backend is 80% complete",
            "ts": "2025-01-15T10:01:30Z",
        },
        {
            "user": "alice@example.com",
            "text": "Great progress! What about the frontend?",
            "ts": "2025-01-15T10:02:15Z",
        },
    ]
    json_file.write_text(json.dumps(chat_data, indent=2))

    return {
        "txt": txt_file,
        "md": md_file,
        "json": json_file,
    }


def example_ingest_text_file(db, project_id: int):
    """Example: Ingest a plain text file."""
    print("\n" + "=" * 80)
    print("Example 1: Ingest Plain Text File")
    print("=" * 80)

    service = FileIngestionService(db)

    # Create temp directory and sample file
    temp_dir = Path("./temp_examples")
    temp_dir.mkdir(exist_ok=True)
    sample_files = create_sample_files(temp_dir)

    try:
        # Ingest the text file
        file = service.ingest_file(
            str(sample_files["txt"].absolute()),
            project_id=project_id,
            source_type="uploaded_document",
        )

        print(f"\nFile ingested successfully!")
        print(f"  File ID: {file.file_id}")
        print(f"  Path: {file.relative_path}")
        print(f"  MIME Type: {file.mime_type}")
        print(f"  Source Type: {file.source_type}")
        print(f"  Current Version ID: {file.current_version_id}")

        # Get version details
        version = db.query(FileVersion).filter_by(version_id=file.current_version_id).first()
        print(f"\nVersion Details:")
        print(f"  Content Hash: {version.content_hash}")
        print(f"  File Size: {version.file_size_bytes} bytes")
        print(f"  Content Locator: {version.content_locator}")

        return file

    finally:
        # Cleanup
        for f in sample_files.values():
            if f.exists():
                f.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()


def example_ingest_markdown(db, project_id: int):
    """Example: Ingest a Markdown file."""
    print("\n" + "=" * 80)
    print("Example 2: Ingest Markdown File")
    print("=" * 80)

    service = FileIngestionService(db)

    temp_dir = Path("./temp_examples")
    temp_dir.mkdir(exist_ok=True)
    sample_files = create_sample_files(temp_dir)

    try:
        file = service.ingest_file(
            str(sample_files["md"].absolute()),
            project_id=project_id,
            source_type="uploaded_document",
        )

        print(f"\nMarkdown file ingested successfully!")
        print(f"  File ID: {file.file_id}")
        print(f"  MIME Type: {file.mime_type}")

        # Extract text to show metadata
        text, metadata = service.extract_text(
            str(sample_files["md"].absolute()), file.mime_type
        )
        print(f"\nExtracted Metadata:")
        print(f"  Heading Count: {metadata['heading_count']}")
        print(f"  Line Count: {metadata['line_count']}")
        print(f"  Extraction Method: {metadata['extraction_method']}")

        return file

    finally:
        for f in sample_files.values():
            if f.exists():
                f.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()


def example_ingest_json_chat(db, project_id: int):
    """Example: Ingest a JSON chat export."""
    print("\n" + "=" * 80)
    print("Example 3: Ingest JSON Chat Export")
    print("=" * 80)

    service = FileIngestionService(db)

    temp_dir = Path("./temp_examples")
    temp_dir.mkdir(exist_ok=True)
    sample_files = create_sample_files(temp_dir)

    try:
        file = service.ingest_file(
            str(sample_files["json"].absolute()),
            project_id=project_id,
            source_type="chat_export",
        )

        print(f"\nJSON chat export ingested successfully!")
        print(f"  File ID: {file.file_id}")
        print(f"  Source Type: {file.source_type}")

        # Extract text to show metadata
        text, metadata = service.extract_text(
            str(sample_files["json"].absolute()), file.mime_type
        )
        print(f"\nExtracted Metadata:")
        print(f"  Message Count: {metadata['message_count']}")
        print(f"  Participants: {metadata['participants']}")
        print(f"  Format: {metadata['format']}")

        print(f"\nExtracted Text Preview:")
        print(text[:300] + "..." if len(text) > 300 else text)

        return file

    finally:
        for f in sample_files.values():
            if f.exists():
                f.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()


def example_duplicate_detection(db, project_id: int):
    """Example: Demonstrate duplicate file detection."""
    print("\n" + "=" * 80)
    print("Example 4: Duplicate File Detection")
    print("=" * 80)

    service = FileIngestionService(db)

    temp_dir = Path("./temp_examples")
    temp_dir.mkdir(exist_ok=True)

    # Create a sample file
    test_file = temp_dir / "duplicate_test.txt"
    test_file.write_text("This file will be ingested twice to test deduplication.")

    try:
        # First ingestion
        print("\nFirst ingestion:")
        file1 = service.ingest_file(
            str(test_file.absolute()),
            project_id=project_id,
            source_type="uploaded_document",
        )
        print(f"  File ID: {file1.file_id}")

        # Second ingestion (should detect duplicate)
        print("\nSecond ingestion (same content):")
        file2 = service.ingest_file(
            str(test_file.absolute()),
            project_id=project_id,
            source_type="uploaded_document",
        )
        print(f"  File ID: {file2.file_id}")

        if file1.file_id == file2.file_id:
            print("\n✓ Duplicate detected! Same File entity returned.")
        else:
            print("\n✗ Warning: Different File entities (should be same)")

    finally:
        if test_file.exists():
            test_file.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()


def example_validation_errors(db, project_id: int):
    """Example: Demonstrate file validation errors."""
    print("\n" + "=" * 80)
    print("Example 5: File Validation Errors")
    print("=" * 80)

    service = FileIngestionService(db)

    # Test 1: Non-existent file
    print("\nTest 1: Non-existent file")
    try:
        service.ingest_file("/path/to/nonexistent.txt", project_id=project_id)
    except Exception as e:
        print(f"  ✓ Expected error: {type(e).__name__}: {str(e)[:80]}")

    # Test 2: Empty file
    print("\nTest 2: Empty file")
    temp_dir = Path("./temp_examples")
    temp_dir.mkdir(exist_ok=True)
    empty_file = temp_dir / "empty.txt"
    empty_file.write_text("")

    try:
        service.ingest_file(str(empty_file.absolute()), project_id=project_id)
    except Exception as e:
        print(f"  ✓ Expected error: {type(e).__name__}: {str(e)[:80]}")
    finally:
        if empty_file.exists():
            empty_file.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("FileIngestionService Examples")
    print("=" * 80)

    # Initialize database
    print("\nInitializing database...")
    init_db()

    # Create a test project if needed
    db = next(get_db())
    project = db.query(Project).first()

    if not project:
        print("\nNo projects found. Creating test project...")
        from src.models.project import Project

        project = Project(
            name="test_project",
            drive_folder_id="test_folder_id",
            classification_rules=[],
            is_default=True,
            display_name="Test Project",
            description="Test project for file ingestion examples",
        )
        db.add(project)
        db.commit()
        print(f"Created project: {project.name} (ID: {project.project_id})")
    else:
        print(f"Using existing project: {project.name} (ID: {project.project_id})")

    project_id = project.project_id

    # Run examples
    try:
        example_ingest_text_file(db, project_id)
        example_ingest_markdown(db, project_id)
        example_ingest_json_chat(db, project_id)
        example_duplicate_detection(db, project_id)
        example_validation_errors(db, project_id)

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        logger.error("Example failed", error=str(e))
        print(f"\n✗ Example failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    from src.models.file_version import FileVersion

    main()
