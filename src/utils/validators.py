"""Audio file and input validation utilities."""

import mimetypes
import re
from pathlib import Path
from typing import Literal

from src.utils.exceptions import AudioValidationError
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Supported audio formats
SUPPORTED_AUDIO_FORMATS = {
    "audio/mpeg",  # MP3
    "audio/mp3",
    "audio/wav",  # WAV
    "audio/wave",
    "audio/x-wav",
    "audio/m4a",  # M4A
    "audio/mp4",
    "audio/ogg",  # OGG
    "audio/flac",  # FLAC
}

SUPPORTED_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac"}

# Maximum audio file size (3 hours at ~500MB for high-quality recording)
MAX_AUDIO_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_DURATION_MINUTES = 180  # 3 hours per spec


def validate_audio_file(file_path: Path | str) -> dict[str, any]:
    """Validate audio file format and size.

    Args:
        file_path: Path to audio file

    Returns:
        Dictionary with validation results:
            - valid: bool
            - file_path: Path
            - size_bytes: int
            - mime_type: str | None
            - extension: str

    Raises:
        AudioValidationError: If file is invalid
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path

    # Check file exists
    if not path.exists():
        raise AudioValidationError(
            f"Audio file not found: {path}",
            details={"file_path": str(path)},
        )

    # Check file is not empty
    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise AudioValidationError(
            f"Audio file is empty: {path}",
            details={"file_path": str(path), "size_bytes": 0},
        )

    # Check file size
    if size_bytes > MAX_AUDIO_SIZE_BYTES:
        raise AudioValidationError(
            f"Audio file exceeds maximum size: {size_bytes} bytes (max: {MAX_AUDIO_SIZE_BYTES})",
            details={
                "file_path": str(path),
                "size_bytes": size_bytes,
                "max_size_bytes": MAX_AUDIO_SIZE_BYTES,
            },
        )

    # Check file extension
    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise AudioValidationError(
            f"Unsupported audio format: {extension}",
            details={
                "file_path": str(path),
                "extension": extension,
                "supported_extensions": list(SUPPORTED_EXTENSIONS),
            },
        )

    # Check MIME type
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type and mime_type not in SUPPORTED_AUDIO_FORMATS:
        logger.warning(
            "Audio file MIME type not in supported list but extension is valid",
            file_path=str(path),
            mime_type=mime_type,
            extension=extension,
        )

    logger.info(
        "Audio file validated successfully",
        file_path=str(path),
        size_mb=round(size_bytes / (1024 * 1024), 2),
        mime_type=mime_type,
        extension=extension,
    )

    return {
        "valid": True,
        "file_path": path,
        "size_bytes": size_bytes,
        "mime_type": mime_type,
        "extension": extension,
    }


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize filename for filesystem compatibility.

    Removes or replaces invalid characters for cross-platform compatibility.

    Args:
        filename: Original filename
        max_length: Maximum filename length (default: 255)

    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    # Invalid: / \ : * ? " < > |
    sanitized = re.sub(r'[/\\:*?"<>|]', "_", filename)

    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(". ")

    # Replace multiple spaces/underscores with single
    sanitized = re.sub(r"[ _]+", "_", sanitized)

    # Truncate to max length
    if len(sanitized) > max_length:
        # Keep file extension if present
        parts = sanitized.rsplit(".", 1)
        if len(parts) == 2:
            name, ext = parts
            max_name_length = max_length - len(ext) - 1
            sanitized = f"{name[:max_name_length]}.{ext}"
        else:
            sanitized = sanitized[:max_length]

    # Ensure not empty
    if not sanitized:
        sanitized = "unnamed"

    return sanitized


def validate_email(email: str) -> bool:
    """Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    # Simple email regex (RFC 5322 simplified)
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_meeting_title(title: str) -> str:
    """Validate and sanitize meeting title.

    Args:
        title: Meeting title

    Returns:
        Sanitized title

    Raises:
        ValueError: If title is empty after sanitization
    """
    if not title:
        raise ValueError("Meeting title cannot be empty")

    # Remove excessive whitespace
    sanitized = " ".join(title.split())

    # Sanitize for filesystem
    sanitized = sanitize_filename(sanitized, max_length=500)

    if not sanitized:
        raise ValueError("Meeting title is empty after sanitization")

    return sanitized


def validate_project_name(project_name: str) -> str:
    """Validate project name is filesystem-safe.

    Args:
        project_name: Project name

    Returns:
        Validated project name

    Raises:
        ValueError: If project name is invalid
    """
    if not project_name:
        raise ValueError("Project name cannot be empty")

    # Project names must be alphanumeric + underscore/hyphen only
    if not re.match(r"^[a-zA-Z0-9_-]+$", project_name):
        raise ValueError(
            f"Project name must be alphanumeric with underscores/hyphens only: {project_name}"
        )

    return project_name
