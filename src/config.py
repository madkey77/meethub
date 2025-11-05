"""Application configuration using Pydantic Settings."""

from pathlib import Path
from typing import Optional

from pydantic import Field, FieldValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="meethub", description="Application name")
    environment: str = Field(default="development", description="Environment (development/production)")

    # Google API Authentication Mode
    google_auth_mode: str = Field(
        default="service_account",
        description="Authentication mode: 'service_account' (admin/org-wide) or 'oauth' (personal)",
    )

    # Google API - Service Account Mode (for organization-wide access)
    google_service_account_path: Path = Field(
        default=Path("./service-account.json"),
        description="Path to Google service account JSON file",
    )
    google_workspace_admin_email: Optional[str] = Field(
        default=None,
        description="Google Workspace admin email for domain-wide delegation",
    )

    # Google API - OAuth Mode (for personal account access)
    google_oauth_credentials_path: Path = Field(
        default=Path("./credentials.json"),
        description="Path to Google OAuth client credentials JSON file (for personal mode)",
    )
    google_oauth_token_path: Path = Field(
        default=Path("./token.json"),
        description="Path to store OAuth token (for personal mode)",
    )

    # Google Drive
    drive_root_folder_id: str = Field(
        ...,
        description="Google Drive root folder ID for transcript storage",
    )

    # Deepgram API
    deepgram_api_key: str = Field(
        ...,
        description="Deepgram API key for transcription",
    )

    # LLM Provider selection
    llm_provider_preference: str = Field(
        default="openai",
        description="Preferred LLM provider (openai|anthropic)",
    )

    # Polling
    poll_interval_minutes: int = Field(
        default=15,
        ge=1,
        le=60,
        description="Meeting polling interval in minutes",
    )
    last_poll_time: Optional[str] = Field(
        default=None,
        description="Last poll timestamp (ISO format)",
    )

    # Processing
    max_concurrent_jobs: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent meeting processing jobs",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum retry attempts for failed jobs",
    )
    retry_initial_delay_seconds: int = Field(
        default=120,
        ge=10,
        description="Initial retry delay in seconds",
    )
    retry_max_delay_seconds: int = Field(
        default=480,
        ge=60,
        description="Maximum retry delay in seconds",
    )
    retry_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        description="Exponential backoff multiplier",
    )

    # Transcription
    transcription_language: str = Field(
        default="pt",
        description="Transcription language code (e.g., 'pt', 'en')",
    )
    transcription_timeout_seconds: int = Field(
        default=300,
        ge=60,
        description="Transcription timeout in seconds",
    )
    deepgram_model: str = Field(
        default="nova-2",
        description="Deepgram model to use for transcription",
    )
    enable_diarization: bool = Field(
        default=True,
        description="Enable speaker diarization",
    )
    enable_punctuation: bool = Field(
        default=True,
        description="Enable automatic punctuation",
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./meethub.db",
        description="Database connection URL",
    )
    database_echo: bool = Field(
        default=False,
        description="Enable SQL query logging",
    )

    # Vector store & chunking
    chromadb_path: Path = Field(
        default=Path("./data/chroma_db"),
        description="Filesystem path to persistent ChromaDB storage",
    )
    chromadb_collection_name: str = Field(
        default="meethub_embeddings",
        description="ChromaDB collection name for primary embeddings",
    )
    rag_chunk_size: int = Field(
        default=1200,
        ge=200,
        description="Character length for each chunk produced during ingestion",
    )
    rag_chunk_overlap: int = Field(
        default=200,
        ge=0,
        description="Character overlap between consecutive chunks",
    )
    rag_top_k_retrieval: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of chunks to retrieve for RAG queries",
    )
    rag_min_similarity: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity required for retrieved chunks",
    )

    # OpenAI configuration
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for GPT and embedding calls",
    )
    openai_chat_model: str = Field(
        default="gpt-4o",
        description="Default OpenAI chat model",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Default OpenAI embedding model",
    )
    openai_timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Request timeout for OpenAI API calls",
    )
    openai_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts for OpenAI API calls",
    )

    # Anthropic configuration
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude models",
    )
    anthropic_chat_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Default Anthropic Claude model",
    )
    anthropic_timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Request timeout for Anthropic API calls",
    )
    anthropic_max_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum retry attempts for Anthropic API calls",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL)",
    )
    log_format: str = Field(
        default="json",
        description="Log format (json/console)",
    )

    # CORS Configuration (for FastAPI)
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8501",
        description="Comma-separated list of allowed CORS origins",
    )

    @property
    def is_service_account_mode(self) -> bool:
        """Check if using service account authentication."""
        return self.google_auth_mode == "service_account"

    @property
    def is_personal_mode(self) -> bool:
        """Check if using OAuth (personal) authentication."""
        return self.google_auth_mode == "oauth"

    @field_validator("rag_chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, value: int, info: FieldValidationInfo) -> int:
        """Ensure chunk overlap is smaller than chunk size."""

        chunk_size = info.data.get("rag_chunk_size")
        if isinstance(chunk_size, int) and chunk_size > 0 and value >= chunk_size:
            msg = "rag_chunk_overlap must be smaller than rag_chunk_size"
            raise ValueError(msg)
        return value


# Global settings instance
settings = Settings()
