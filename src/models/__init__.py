"""Database models and session management for MeetHub."""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Import all models for Alembic to detect them
from src.models.meeting import Meeting, MeetingStatus, RAGIngestionStatus  # noqa: E402
from src.models.transcript import Transcript  # noqa: E402
from src.models.participant import Participant  # noqa: E402
from src.models.project import Project  # noqa: E402
from src.models.processing_job import ProcessingJob, JobStatus  # noqa: E402

# NEW: RAG models
from src.models.file import File, FileSourceType  # noqa: E402
from src.models.file_version import FileVersion  # noqa: E402
from src.models.chunk import Chunk  # noqa: E402
from src.models.embedding import Embedding  # noqa: E402
from src.models.job_run import JobRun, JobRunStatus  # noqa: E402
from src.models.job_step import JobStep, JobStepStatus  # noqa: E402
from src.models.artifact import Artifact, ArtifactVersion  # noqa: E402
from src.models.artifact_link import ArtifactLink, LinkRoleType  # noqa: E402
from src.models.backfill_job import BackfillJob, BackfillStatus  # noqa: E402

__all__ = [
    "Base",
    # Existing models
    "Meeting",
    "MeetingStatus",
    "RAGIngestionStatus",
    "Transcript",
    "Participant",
    "Project",
    "ProcessingJob",
    "JobStatus",
    # NEW: RAG models
    "File",
    "FileSourceType",
    "FileVersion",
    "Chunk",
    "Embedding",
    "JobRun",
    "JobRunStatus",
    "JobStep",
    "JobStepStatus",
    "Artifact",
    "ArtifactVersion",
    "ArtifactLink",
    "LinkRoleType",
    "BackfillJob",
    "BackfillStatus",
    # Database utilities
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
]


# Create database engine
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn: any, connection_record: any) -> None:
    """Set SQLite pragmas for better performance and concurrency.

    Enables WAL mode for better concurrent access.
    """
    if "sqlite" in settings.database_url:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        logger.info("SQLite WAL mode enabled")


# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """Get database session (dependency injection).

    Yields:
        Database session

    Example:
        with get_db() as db:
            # Use db session
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables.

    Creates all tables defined in models.
    Should be called on application startup.
    """
    logger.info("Initializing database")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")
