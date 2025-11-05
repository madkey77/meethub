"""Custom exception hierarchy for MeetHub with troubleshooting hints."""


class MeetHubError(Exception):
    """Base exception for all MeetHub errors."""

    troubleshooting_hint: str | None = None

    def __init__(self, message: str, details: dict[str, any] | None = None) -> None:
        """Initialize MeetHub error.

        Args:
            message: Human-readable error message
            details: Additional error context (optional)
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of error with troubleshooting hint."""
        parts = [self.message]

        if self.details:
            parts.append(f"Details: {self.details}")

        if self.troubleshooting_hint:
            parts.append(f"Hint: {self.troubleshooting_hint}")

        return " | ".join(parts)


class GoogleAPIError(MeetHubError):
    """Errors related to Google API calls (Meet, Drive)."""

    troubleshooting_hint = (
        "Check Google service account credentials and permissions. "
        "Ensure domain-wide delegation is enabled for admin email."
    )


class GoogleMeetAPIError(GoogleAPIError):
    """Specific errors from Google Meet API."""

    troubleshooting_hint = (
        "Verify Google Workspace admin email has access to Google Meet. "
        "Check that OAuth scopes include 'meet.readonly' and 'calendar.readonly'."
    )


class GoogleDriveAPIError(GoogleAPIError):
    """Specific errors from Google Drive API."""

    troubleshooting_hint = (
        "Verify Drive folder ID exists and service account has write access. "
        "Check OAuth scopes include 'drive.file'."
    )


class AuthenticationError(GoogleAPIError):
    """Service account authentication failures."""

    troubleshooting_hint = (
        "Check that service-account.json file exists and is valid. "
        "Verify domain-wide delegation is enabled in Google Workspace Admin Console."
    )


class RateLimitError(GoogleAPIError):
    """API rate limit exceeded."""

    troubleshooting_hint = (
        "Google API rate limit exceeded. Retry will happen automatically with backoff. "
        "If persistent, consider reducing polling frequency or spreading load."
    )


class QuotaExceededError(GoogleAPIError):
    """API quota exceeded (Drive storage, API calls)."""

    troubleshooting_hint = (
        "Google API quota exceeded. Check Google Cloud Console quotas. "
        "For Drive storage, clean up old transcripts or increase quota."
    )


class TranscriptionError(MeetHubError):
    """Errors during audio transcription."""

    troubleshooting_hint = "Check audio file format and size. Ensure Deepgram API key is valid."


class DeepgramAPIError(TranscriptionError):
    """Errors from Deepgram API."""

    troubleshooting_hint = (
        "Verify DEEPGRAM_API_KEY is correct. Check Deepgram account balance and quota. "
        "Ensure audio file is in supported format (mp3, mp4, wav, etc.)."
    )


class AudioValidationError(TranscriptionError):
    """Audio file validation failures."""

    troubleshooting_hint = (
        "Audio file must be <500MB and <4 hours duration. "
        "Supported formats: mp3, mp4, wav, m4a, flac, ogg."
    )


class TranscriptionTimeoutError(TranscriptionError):
    """Transcription exceeded timeout limit."""

    troubleshooting_hint = (
        "Transcription timeout exceeded. This may happen with very large files. "
        "Consider increasing TRANSCRIPTION_TIMEOUT_SECONDS or reducing audio file size."
    )


class ClassificationError(MeetHubError):
    """Errors during meeting classification."""

    troubleshooting_hint = (
        "Check classification_rules.json and project_folders.json files exist and are valid JSON. "
        "Ensure default project is defined in rules."
    )


class DatabaseError(MeetHubError):
    """Database operation failures."""

    troubleshooting_hint = (
        "Check database file permissions and disk space. "
        "Try running 'alembic upgrade head' to ensure schema is up to date."
    )


class ConfigurationError(MeetHubError):
    """Configuration validation or loading errors."""

    troubleshooting_hint = (
        "Check .env file exists and all required variables are set. "
        "See .env.example for required configuration."
    )


class ProcessingError(MeetHubError):
    """Meeting processing pipeline errors."""

    troubleshooting_hint = (
        "Check logs for specific error details. Common causes: "
        "missing recording, API failures, network issues."
    )


class RetryableError(MeetHubError):
    """Base class for errors that should trigger retry logic."""
    pass


class NetworkError(RetryableError):
    """Network connectivity issues."""
    pass


class TemporaryAPIError(RetryableError):
    """Temporary API failures that can be retried."""
    pass


# ==============================================================================
# RAG-Specific Exceptions
# ==============================================================================


class RAGError(MeetHubError):
    """Base exception for all RAG pipeline errors.

    This is the parent class for all RAG-related exceptions including
    embedding generation, chunking, artifact generation, and vector store operations.

    Use this when the specific error type is unknown or for generic RAG failures.
    """

    troubleshooting_hint = (
        "Check RAG pipeline logs for detailed error information. "
        "Verify LLM provider API keys are configured and valid."
    )


class EmbeddingError(RAGError):
    """Embedding generation failures.

    Raised when embedding generation fails for any reason:
    - LLM provider API failures
    - Invalid input text (too long, empty, invalid encoding)
    - Model configuration issues
    - Network timeouts during embedding API calls

    Example:
        try:
            embeddings = embedding_provider.embed(chunks)
        except EmbeddingError as e:
            logger.error("Failed to generate embeddings", error=str(e))
    """

    troubleshooting_hint = (
        "Check embedding provider configuration (OPENAI_API_KEY, etc.). "
        "Verify text is not empty and within model's token limits. "
        "Ensure embedding model name is valid for the selected provider."
    )


class ChunkingError(RAGError):
    """Chunking process failures.

    Raised when text chunking fails:
    - Invalid chunking strategy configuration
    - Source text parsing errors
    - Metadata extraction failures (speaker, timestamp, page numbers)
    - Chunk size/overlap validation errors

    Example:
        try:
            chunks = chunker.chunk(text, source_metadata)
        except ChunkingError as e:
            logger.error("Chunking failed", file_id=file_id, error=str(e))
    """

    troubleshooting_hint = (
        "Verify chunking strategy is registered and configured correctly. "
        "Check source text is valid and not corrupted. "
        "Ensure chunk_size > chunk_overlap in configuration."
    )


class ArtifactGenerationError(RAGError):
    """Artifact generation failures.

    Raised when artifact generators fail to produce outputs:
    - LLM API failures during generation
    - Invalid prompt templates
    - JSON parsing errors from LLM responses
    - Context too large for model's token limit
    - Generator not found in registry

    Example:
        try:
            artifact = generator.generate(context, llm_provider)
        except ArtifactGenerationError as e:
            logger.error("Artifact generation failed", kind=artifact_kind, error=str(e))
    """

    troubleshooting_hint = (
        "Check artifact generator is registered in plugin registry. "
        "Verify LLM provider is configured and has valid API key. "
        "Ensure context length doesn't exceed model's token limit. "
        "Check prompt template exists and is valid."
    )


class LLMProviderError(RAGError):
    """LLM provider failures.

    Raised when LLM provider operations fail:
    - API authentication failures
    - Rate limiting or quota exceeded
    - Invalid model name or configuration
    - Request/response parsing errors
    - Network timeouts or connectivity issues

    Example:
        try:
            result = llm_provider.generate(messages)
        except LLMProviderError as e:
            logger.error("LLM generation failed", provider=provider_name, error=str(e))
    """

    troubleshooting_hint = (
        "Verify LLM provider API key is set and valid. "
        "Check provider quota and rate limits. "
        "Ensure model name is supported by provider. "
        "Review provider-specific configuration (timeout, max_retries)."
    )


class VectorStoreError(RAGError):
    """ChromaDB/vector store failures.

    Raised when vector store operations fail:
    - Collection not found or creation failures
    - Upsert/delete operation errors
    - Query/retrieval failures
    - Vector dimension mismatches
    - ChromaDB connection or persistence errors

    Example:
        try:
            vector_store.upsert(records)
        except VectorStoreError as e:
            logger.error("Vector store upsert failed", collection=collection_name, error=str(e))
    """

    troubleshooting_hint = (
        "Check ChromaDB is properly initialized at configured path. "
        "Verify vector dimensions match embedding model output. "
        "Ensure sufficient disk space for vector storage. "
        "Check collection name is valid and not corrupted."
    )


class FileIngestionError(RAGError):
    """File processing failures.

    Raised when file ingestion fails:
    - File format validation errors (invalid PDF, DOCX, etc.)
    - File size exceeds limits
    - Content extraction failures (OCR, parsing)
    - Hash computation errors
    - File not found or inaccessible
    - MIME type detection failures

    Example:
        try:
            file_version = ingestion_service.ingest_file(file_path, project_id)
        except FileIngestionError as e:
            logger.error("File ingestion failed", file_path=file_path, error=str(e))
    """

    troubleshooting_hint = (
        "Verify file exists and is readable. "
        "Check file format is supported (PDF, DOCX, TXT, MD, JSON). "
        "Ensure file size is within limits (100MB audio, 50MB documents). "
        "For PDFs, verify not password-protected or corrupted."
    )
