"""FastAPI REST API for RAG-Enhanced Meeting Intelligence System.

This package provides a production-ready REST API with:
- CORS middleware for cross-origin requests
- Request logging with correlation IDs
- Global exception handlers
- Dependency injection for services
- Pydantic schemas for request/response validation
- Health check endpoints
- OpenAPI documentation

Main Components:
    - main.py: FastAPI app initialization
    - dependencies.py: Dependency injection functions
    - middleware.py: Custom middleware (logging, auth)
    - schemas/: Pydantic request/response schemas
    - routes/: API route handlers (to be implemented)

Usage:
    To run the API server:

        $ uvicorn src.api.main:app --reload --port 8000

    API documentation available at:
        - Swagger UI: http://localhost:8000/docs
        - ReDoc: http://localhost:8000/redoc
        - OpenAPI JSON: http://localhost:8000/openapi.json
"""

from src.api.main import app

__all__ = ["app"]
