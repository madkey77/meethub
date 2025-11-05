"""Custom middleware for FastAPI application.

This module provides middleware for:
- Request logging with correlation IDs
- Authentication (OAuth2 token verification)
- User context extraction

Note: Request logging middleware is already implemented in main.py.
This module provides additional middleware functions if needed.
"""

import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.utils.exceptions import AuthenticationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware with correlation IDs and structured logging.

    Adds:
        - X-Request-ID header (correlation ID) to all requests/responses
        - Request/response logging with timing
        - User ID extraction (if authenticated)

    Note: This is an alternative implementation using BaseHTTPMiddleware.
    The main.py already implements this using @app.middleware("http") decorator.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging.

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response from downstream handlers
        """
        # Generate or extract correlation ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Store in request state for access in route handlers
        request.state.request_id = request_id

        # Log request start
        logger.info(
            "middleware.request_start",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_host=request.client.host if request.client else None,
        )

        # Process request
        import time
        start_time = time.time()

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log request completion
            logger.info(
                "middleware.request_complete",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=f"{duration_ms:.2f}",
            )

            # Add correlation ID to response
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Log request failure
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "middleware.request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=f"{duration_ms:.2f}",
            )
            raise


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for OAuth2 token verification.

    Verifies tokens on all endpoints except:
        - /health
        - /docs
        - /redoc
        - /openapi.json

    Extracts user info from token and stores in request.state.user.

    Note: In production, this should use proper token verification with Google's
    OAuth2 libraries. For MVP, we use the get_current_user dependency instead.
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication check.

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response from downstream handlers

        Raises:
            HTTPException: 401 if authentication fails
        """
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for static files
        if request.url.path.startswith("/static"):
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")

        # Check if OAuth mode is enabled
        if settings.__dict__.get("google_auth_mode", "service_account") == "oauth":
            # In OAuth mode, require authentication
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning(
                    "middleware.auth_failed",
                    path=request.url.path,
                    reason="missing_token",
                )
                # Return 401 response
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Unauthorized",
                        "message": "Valid authentication credentials required",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Extract token
            token = auth_header.split(" ")[1]

            # Verify token (simplified - in production use google.oauth2.id_token)
            try:
                # This is a placeholder - in production, verify with Google
                # For now, just check that token exists
                if not token:
                    raise AuthenticationError("Invalid token")

                # In production, extract user info from verified token
                user = {
                    "user_id": "test_user",
                    "email": "user@example.com",
                    "authenticated": True,
                }

                # Store user in request state
                request.state.user = user

                logger.debug(
                    "middleware.user_authenticated",
                    user_email=user["email"],
                    path=request.url.path,
                )

            except Exception as e:
                logger.error(
                    "middleware.token_verification_failed",
                    error=str(e),
                    path=request.url.path,
                )
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Unauthorized",
                        "message": "Invalid or expired token",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )

        else:
            # Service account mode - no per-user authentication
            request.state.user = {
                "user_id": "system",
                "email": settings.google_workspace_admin_email or "admin@system",
                "authenticated": True,
                "mode": "service_account",
            }

        # Continue to next middleware/handler
        return await call_next(request)


def get_request_id(request: Request) -> str:
    """Extract correlation ID from request state.

    Args:
        request: FastAPI request

    Returns:
        Correlation ID (X-Request-ID)

    Usage:
        @app.get("/items")
        def get_items(request: Request):
            request_id = get_request_id(request)
            logger.info("Processing items", request_id=request_id)
    """
    return getattr(request.state, "request_id", "unknown")


def get_user_from_request(request: Request) -> Optional[dict]:
    """Extract user info from request state (set by auth middleware).

    Args:
        request: FastAPI request

    Returns:
        User info dict if authenticated, None otherwise

    Usage:
        @app.get("/protected")
        def protected_route(request: Request):
            user = get_user_from_request(request)
            if user:
                return {"user_email": user["email"]}
            else:
                raise HTTPException(status_code=401)
    """
    return getattr(request.state, "user", None)
