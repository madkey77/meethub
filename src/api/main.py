"""FastAPI application initialization and configuration.

This module sets up the FastAPI app with:
- CORS middleware for cross-origin requests
- Request logging middleware with correlation IDs
- Global exception handlers for consistent error responses
- API v1 router mounting at /api/v1
- Health check endpoint at /health
- OpenAPI documentation at /docs

The app is production-ready with proper observability, error handling, and security.
"""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import settings
from src.models import init_db
from src.utils.exceptions import MeetHubError
from src.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events.

    Startup:
        - Initialize database tables
        - Log application start

    Shutdown:
        - Clean up resources
        - Log application shutdown
    """
    # Startup
    logger.info(
        "fastapi.startup",
        app_name=settings.app_name,
        environment=settings.environment,
    )

    # Initialize database
    try:
        init_db()
        logger.info("fastapi.database_initialized")
    except Exception as e:
        logger.error(
            "fastapi.database_init_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise

    yield

    # Shutdown
    logger.info("fastapi.shutdown")


# Create FastAPI app
app = FastAPI(
    title="RAG-Enhanced Meeting Intelligence System API",
    description=(
        "FastAPI REST API for intelligent meeting transcription and RAG-powered document analysis. "
        "Supports multi-source file ingestion, dual-provider LLM integration (OpenAI, Anthropic), "
        "declarative artifact generation, and RAG chat with citations."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ==============================================================================
# CORS Configuration
# ==============================================================================

# Get allowed origins from environment (comma-separated list)
allowed_origins = [
    origin.strip()
    for origin in settings.__dict__.get("cors_origins", "http://localhost:3000,http://localhost:8501").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("fastapi.cors_configured", allowed_origins=allowed_origins)


# ==============================================================================
# Middleware
# ==============================================================================

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Request logging middleware with correlation IDs and timing.

    Adds:
        - X-Request-ID header (correlation ID)
        - Request/response logging
        - Request duration tracking
        - User ID extraction (if authenticated)
    """
    # Generate correlation ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Log request start
    start_time = time.time()
    logger.info(
        "fastapi.request_start",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        query_params=str(request.query_params),
        client_host=request.client.host if request.client else None,
    )

    # Process request
    try:
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log request completion
        logger.info(
            "fastapi.request_complete",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=f"{duration_ms:.2f}",
        )

        # Add correlation ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception as e:
        # Log request failure
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "fastapi.request_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=f"{duration_ms:.2f}",
        )
        raise


# ==============================================================================
# Exception Handlers
# ==============================================================================

@app.exception_handler(MeetHubError)
async def meethub_error_handler(request: Request, exc: MeetHubError):
    """Handle custom MeetHub errors with structured responses.

    Maps MeetHub exceptions to appropriate HTTP status codes:
        - AuthenticationError: 401
        - ConfigurationError: 500
        - FileIngestionError: 400
        - RAGError subclasses: 500
    """
    # Determine HTTP status code based on error type
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    error_type = type(exc).__name__
    if "Authentication" in error_type or "Unauthorized" in error_type:
        status_code = status.HTTP_401_UNAUTHORIZED
    elif "NotFound" in error_type:
        status_code = status.HTTP_404_NOT_FOUND
    elif "Validation" in error_type or "FileIngestion" in error_type:
        status_code = status.HTTP_400_BAD_REQUEST

    # Build error response
    error_response = {
        "error": error_type,
        "message": exc.message,
        "details": exc.details,
    }

    # Add troubleshooting hint if available
    if exc.troubleshooting_hint:
        error_response["hint"] = exc.troubleshooting_hint

    logger.error(
        "fastapi.meethub_error",
        error_type=error_type,
        message=exc.message,
        details=exc.details,
        status_code=status_code,
    )

    return JSONResponse(
        status_code=status_code,
        content=error_response,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent error format."""
    error_response = {
        "error": "HTTPException",
        "message": exc.detail,
        "details": {},
    }

    logger.warning(
        "fastapi.http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with detailed field information."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    error_response = {
        "error": "ValidationError",
        "message": "Request validation failed",
        "details": {"errors": errors},
    }

    logger.warning(
        "fastapi.validation_error",
        path=request.url.path,
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with safe error messages."""
    error_response = {
        "error": "InternalServerError",
        "message": "An unexpected error occurred",
        "details": {
            "error_type": type(exc).__name__,
        },
    }

    # Include error details in development only
    if settings.environment == "development":
        error_response["details"]["error_message"] = str(exc)

    logger.error(
        "fastapi.unexpected_error",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response,
    )


# ==============================================================================
# Health Check Endpoint
# ==============================================================================

@app.get(
    "/health",
    tags=["System"],
    response_model=Dict[str, Any],
    summary="Health check endpoint",
    description="Check system health and availability of critical dependencies",
)
async def health_check():
    """Health check endpoint (no authentication required).

    Checks:
        - Database connectivity
        - ChromaDB availability
        - LLM provider status (OpenAI, Anthropic)
        - Disk space

    Returns:
        Health status with component availability
    """
    from src.models import SessionLocal
    from src.services.vector_store import ChromaVectorStore
    from src.services.llm.factory import LLMProviderFactory
    import shutil

    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database_connected": False,
        "chromadb_reachable": False,
        "llm_providers": {},
        "disk_space_gb": 0.0,
    }

    # Check database
    try:
        db = SessionLocal()
        # Simple query to test connection
        db.execute("SELECT 1")
        db.close()
        health_status["database_connected"] = True
    except Exception as e:
        logger.error("health_check.database_failed", error=str(e))
        health_status["status"] = "degraded"

    # Check ChromaDB
    try:
        vector_store = ChromaVectorStore()
        # Try to list collections
        vector_store.list_collections()
        health_status["chromadb_reachable"] = True
    except Exception as e:
        logger.error("health_check.chromadb_failed", error=str(e))
        health_status["status"] = "degraded"

    # Check LLM providers
    for provider_name in ["openai", "anthropic"]:
        try:
            # Just check if provider can be instantiated
            provider = LLMProviderFactory.create(provider_name)
            health_status["llm_providers"][provider_name] = "available"
        except Exception as e:
            logger.warning(
                "health_check.llm_provider_unavailable",
                provider=provider_name,
                error=str(e),
            )
            health_status["llm_providers"][provider_name] = "unavailable"

    # Check disk space
    try:
        stat = shutil.disk_usage("/")
        health_status["disk_space_gb"] = round(stat.free / (1024 ** 3), 2)

        # Warn if disk space is low (< 5GB)
        if health_status["disk_space_gb"] < 5.0:
            health_status["status"] = "degraded"
            logger.warning("health_check.low_disk_space", free_gb=health_status["disk_space_gb"])
    except Exception as e:
        logger.error("health_check.disk_space_failed", error=str(e))

    # Determine final status
    if not health_status["database_connected"] or not health_status["chromadb_reachable"]:
        health_status["status"] = "unhealthy"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status,
        )

    return health_status


# ==============================================================================
# API v1 Router
# ==============================================================================

# Import and mount API v1 routes
from src.api.routes import files

app.include_router(files.router, prefix="/api/v1", tags=["Files"])

# Other routes to be added later:
# from src.api.routes import jobs, artifacts, chat, backfill, projects, rules
# app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
# app.include_router(artifacts.router, prefix="/api/v1", tags=["Artifacts"])
# app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
# app.include_router(backfill.router, prefix="/api/v1", tags=["Backfill"])
# app.include_router(projects.router, prefix="/api/v1", tags=["Projects"])
# app.include_router(rules.router, prefix="/api/v1", tags=["Rules"])

logger.info("fastapi.app_initialized")
