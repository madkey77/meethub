"""FastAPI dependency injection functions.

This module provides dependency injection for:
- Database sessions (with automatic cleanup)
- LLM provider factory
- Vector store client
- RAG pipeline instances
- File ingestion service
- Authentication (current user)

All dependencies use FastAPI's Depends() pattern for clean injection.
"""

from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.config import settings
from src.models import SessionLocal
from src.services.file_ingestion import FileIngestionService
from src.services.llm.factory import LLMProviderFactory
from src.services.rag_pipeline import RAGPipeline
from src.services.vector_store import ChromaVectorStore
from src.utils.exceptions import AuthenticationError
from src.utils.google_auth import get_google_credentials
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Security scheme for OAuth2
security = HTTPBearer(auto_error=False)


# ==============================================================================
# Database Session Dependency
# ==============================================================================

def get_db() -> Generator[Session, None, None]:
    """Get database session with automatic cleanup.

    Yields:
        SQLAlchemy database session

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit on success
    except Exception:
        db.rollback()  # Rollback on error
        raise
    finally:
        db.close()


# ==============================================================================
# LLM Provider Factory Dependency
# ==============================================================================

def get_llm_factory() -> LLMProviderFactory:
    """Get LLM provider factory instance.

    Returns:
        LLMProviderFactory for creating provider instances

    Usage:
        @app.post("/generate")
        def generate(factory: LLMProviderFactory = Depends(get_llm_factory)):
            provider = factory.create("openai")
            return provider.generate(...)
    """
    return LLMProviderFactory


# ==============================================================================
# Vector Store Dependency
# ==============================================================================

def get_vector_store() -> ChromaVectorStore:
    """Get ChromaDB vector store client.

    Returns:
        ChromaVectorStore instance configured from settings

    Usage:
        @app.get("/search")
        def search(vector_store: ChromaVectorStore = Depends(get_vector_store)):
            results = vector_store.query(vector=..., top_k=10)
            return results
    """
    return ChromaVectorStore()


# ==============================================================================
# RAG Pipeline Dependency
# ==============================================================================

def get_rag_pipeline(
    db: Session = Depends(get_db),
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    llm_factory: LLMProviderFactory = Depends(get_llm_factory),
) -> RAGPipeline:
    """Get RAG pipeline instance with injected dependencies.

    Args:
        db: Database session (injected)
        vector_store: Vector store client (injected)
        llm_factory: LLM provider factory (injected)

    Returns:
        RAGPipeline instance ready for use

    Usage:
        @app.post("/ingest")
        def ingest(pipeline: RAGPipeline = Depends(get_rag_pipeline)):
            job_run = pipeline.process_file(file_version, rules)
            return job_run
    """
    return RAGPipeline(
        db_session=db,
        vector_store=vector_store,
        llm_factory=llm_factory,
    )


# ==============================================================================
# File Ingestion Service Dependency
# ==============================================================================

def get_file_ingestion_service(
    db: Session = Depends(get_db),
) -> FileIngestionService:
    """Get file ingestion service instance.

    Args:
        db: Database session (injected)

    Returns:
        FileIngestionService instance

    Usage:
        @app.post("/files/upload")
        def upload(service: FileIngestionService = Depends(get_file_ingestion_service)):
            file = service.ingest_file(file_path, project_id)
            return file
    """
    return FileIngestionService(db_session=db)


# ==============================================================================
# Authentication Dependency
# ==============================================================================

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Get current authenticated user from OAuth token.

    This is a simplified implementation that validates Google OAuth tokens.
    In production, this should:
        1. Extract token from Authorization header
        2. Verify token signature
        3. Check token expiration
        4. Extract user info (email, user_id)
        5. Return user object

    For MVP, we check if credentials exist and if auth mode is configured.

    Args:
        credentials: HTTP Bearer token (injected from Authorization header)

    Returns:
        User info dictionary with email and user_id

    Raises:
        HTTPException: 401 if authentication fails

    Usage:
        @app.get("/protected")
        def protected_route(user: dict = Depends(get_current_user)):
            return {"user_email": user["email"]}
    """
    # Skip auth for health endpoint (handled in middleware)
    # This dependency is only called for protected routes

    # Check if OAuth mode is enabled
    if settings.__dict__.get("google_auth_mode", "service_account") == "oauth":
        # In OAuth mode, validate token
        if not credentials:
            logger.warning("auth.missing_credentials")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid authentication credentials required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token (simplified - in production use google.oauth2.id_token.verify_oauth2_token)
        token = credentials.credentials

        try:
            # This is a placeholder - in production, verify token with Google
            # For now, just check that a token exists
            if not token:
                raise AuthenticationError("Invalid token")

            # In production, extract user info from verified token
            # For MVP, return a mock user
            user = {
                "user_id": "test_user",
                "email": "user@example.com",
                "authenticated": True,
            }

            logger.info("auth.user_authenticated", user_email=user["email"])
            return user

        except Exception as e:
            logger.error("auth.validation_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    else:
        # Service account mode - no per-user authentication
        # Return system user
        return {
            "user_id": "system",
            "email": settings.google_workspace_admin_email or "admin@system",
            "authenticated": True,
            "mode": "service_account",
        }


# ==============================================================================
# Optional Authentication Dependency
# ==============================================================================

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Get current user if authenticated, None otherwise.

    Useful for endpoints that work differently for authenticated vs anonymous users.

    Args:
        credentials: HTTP Bearer token (injected)

    Returns:
        User info dict if authenticated, None otherwise

    Usage:
        @app.get("/items")
        def get_items(user: Optional[dict] = Depends(get_current_user_optional)):
            if user:
                # Return personalized items
                pass
            else:
                # Return public items
                pass
    """
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None
