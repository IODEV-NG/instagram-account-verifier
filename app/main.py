"""InstaVerify API - Main FastAPI application.

Self-hosted Instagram account verification API with Meta API integration
and public-web fallback. No permanent database storage.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.errors import add_exception_handlers
from app.api.routes.health import router as health_router
from app.api.routes.verify import router as verify_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[dict[str, Any], None]:
    """Application lifespan handler.

    Handles startup and shutdown events.
    For this milestone, no persistent connections are managed.
    """
    """Application lifespan handler.

    Handles startup and shutdown events.
    For this milestone, no persistent connections are managed.
    """
    # Startup: validate configuration
    get_settings()
    yield {}
    # Shutdown: cleanup if needed


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="InstaVerify API",
        description=(
            "Self-hosted Instagram account verification API with official Meta API "
            "integration and public-web fallback. No permanent Instagram data storage."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Add CORS middleware
    if settings.cors_origins == "*":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        origins = [o.strip() for o in settings.cors_origins.split(",")]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Add exception handlers
    add_exception_handlers(app)

    # Include routers
    app.include_router(health_router)
    app.include_router(verify_router)

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        """Root redirect to API documentation."""
        return {
            "name": "InstaVerify API",
            "version": "0.1.0",
            "docs": "/docs",
        }

    return app


# Create the application instance
app = create_app()


def main() -> None:
    """Entry point for running the application directly.

    Run with: python -m app.main
    Or: uvicorn app.main:app
    """
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
