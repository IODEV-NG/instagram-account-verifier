"""API dependencies for authentication and authorization.

Provides dependency injection for API key verification and other
cross-cutting concerns.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

# API key header name
API_KEY_HEADER_NAME = "X-API-Key"

# Create API key header security scheme
api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME,
    auto_error=False,  # We handle missing/invalid ourselves
)


async def verify_api_key(
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER_NAME)] = None,
) -> str:
    """Verify API key from request header.

    Args:
        api_key: API key from X-API-Key header.

    Returns:
        The verified API key string.

    Raises:
        HTTPException: If API key is missing or invalid (401).
    """
    settings = get_settings()

    # If no API key is configured, skip auth (development mode)
    if not settings.api_key:
        return ""

    # If API key is required but not provided
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "API key is required. Provide X-API-Key header.",
                }
            },
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "Invalid API key.",
                }
            },
        )

    return api_key


async def optional_api_key(
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER_NAME)] = None,
) -> str | None:
    """Optional API key verification.

    Returns the key if valid, None if missing or invalid.
    Does not raise on invalid/missing key.

    Args:
        api_key: API key from X-API-Key header.

    Returns:
        Validated API key or None.
    """
    settings = get_settings()

    if not settings.api_key or not api_key:
        return None

    if hmac.compare_digest(api_key, settings.api_key):
        return api_key

    return None
