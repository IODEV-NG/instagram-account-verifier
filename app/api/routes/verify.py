"""Verification API routes for Instagram account verification."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.dependencies import verify_api_key
from app.config import get_settings
from app.schemas.response import (
    BatchVerificationRequest,
    BatchVerificationResult,
    VerificationResult,
)
from app.services.normalizer import UsernameValidationError, normalize_username
from app.services.rate_limit import get_rate_limit_service
from app.services.verifier import VerificationService

router = APIRouter(prefix="/api/v1", tags=["verification"])


def get_verification_service() -> VerificationService:
    """Get verification service dependency.

    Returns:
        VerificationService configured with application settings.
    """
    from app.providers.base import MockMetaProvider, MockPublicWebProvider

    settings = get_settings()

    # For this milestone, use mock providers for deterministic testing
    # In production, this would use real MetaProvider and PublicWebProvider

    mock_meta_results: dict[str, dict[str, object]] = {
        "natgeo": {
            "exists": True,
            "account_type": "business",
            "followers": 283000000,
            "following": 100,
            "media_count": 9500,
            "is_private": False,
        },
        "doesnotexist": {
            "exists": False,
        },
    }

    mock_web_results: dict[str, dict[str, object]] = {
        "testuser": {
            "exists": True,
            "verification_status": "verified",
            "account_type": "personal",
            "followers": None,
            "following": None,
            "media_count": None,
            "is_private": None,
            "confidence": "medium",
        },
    }

    meta_provider = MockMetaProvider(settings, mock_meta_results)
    public_web_provider = MockPublicWebProvider(settings, mock_web_results)

    return VerificationService(
        meta_provider=meta_provider,
        public_web_provider=public_web_provider,
    )


@router.get(
    "/verify/{username}",
    response_model=VerificationResult,
    summary="Verify Instagram Account",
    description="Verify an Instagram username and retrieve available account info.",
)
async def verify_account(
    username: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
    api_key: Annotated[str, Depends(verify_api_key)] = "",
    x_forwarded_for: Annotated[str | None, Header()] = None,
) -> VerificationResult:
    """Verify an Instagram account.

    - Normalizes the username (handles @ prefixes, URLs, etc.)
    - Attempts verification through available providers
    - Returns a structured result with verification status and confidence

    Requires API key authentication via X-API-Key header.

    Args:
        username: Instagram username to verify (can include @, URL, or plain username)
        service: Injected verification service
        api_key: Verified API key from dependency
        x_forwarded_for: X-Forwarded-For header for rate limiting behind proxy

    Returns:
        VerificationResult with the verification outcome
    """
    # Get client IP for rate limiting
    settings = get_settings()
    client_ip = _get_client_ip(
        x_forwarded_for,
        trust_proxy=settings.trust_proxy_headers,
    )

    # Check rate limit
    rate_limit_service = get_rate_limit_service()
    is_allowed, count, retry_after, limit_type = (
        rate_limit_service.check_and_record_request(
            client_ip,
            is_authenticated=bool(api_key),
        )
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Rate limit exceeded. Please try again later.",
                    "details": {
                        "retry_after_seconds": int(retry_after),
                        "limit_type": limit_type,
                        "current_limit": (
                            rate_limit_service._limiter.get_entry(client_ip).count_in_window(
                                3600 if limit_type == "hour" else 60,
                                0,
                            )
                            if limit_type
                            else 0
                        ),
                    },
                }
            },
            headers={"Retry-After": str(int(retry_after))},
        )

    # Record the request
    rate_limit_service.record_request(client_ip)

    try:
        normalized_username = normalize_username(username)
    except UsernameValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_USERNAME",
                    "message": f"Invalid username: {e.reason}",
                    "details": {"username": e.username, "reason": e.reason},
                }
            },
        ) from None

    try:
        result = await service.verify(normalized_username)
        return result
    except Exception as e:
        # Log the error in production
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "VERIFICATION_UNAVAILABLE",
                    "message": "Account verification could not be completed.",
                    "detail": str(e) if str(e) else None,
                }
            },
        ) from None


@router.get(
    "/verify",
    response_model=VerificationResult,
    summary="Verify Instagram Account (query param)",
    description="Alternative endpoint for verification using query parameter.",
)
async def verify_account_query(
    username: Annotated[str, Query(min_length=1, max_length=30, alias="username")],
    service: Annotated[VerificationService, Depends(get_verification_service)],
    api_key: Annotated[str, Depends(verify_api_key)] = "",
    x_forwarded_for: Annotated[str | None, Header()] = None,
) -> VerificationResult:
    """Verify an Instagram account using query parameter.

    Same as /verify/{username} but accepts username as query parameter.
    Requires API key authentication.

    Args:
        username: Instagram username to verify
        service: Injected verification service
        api_key: Verified API key from dependency
        x_forwarded_for: X-Forwarded-For header for rate limiting

    Returns:
        VerificationResult with the verification outcome
    """
    return await verify_account(username, service, api_key, x_forwarded_for)


@router.post(
    "/verify/batch",
    response_model=BatchVerificationResult,
    summary="Batch Verify Instagram Accounts",
    description="Verify multiple Instagram usernames in a single request.",
)
async def batch_verify(
    request: BatchVerificationRequest,
    service: Annotated[VerificationService, Depends(get_verification_service)],
    api_key: Annotated[str, Depends(verify_api_key)] = "",
    x_forwarded_for: Annotated[str | None, Header()] = None,
) -> BatchVerificationResult:
    """Verify multiple Instagram accounts in batch.

    Maximum batch size: 50 usernames.
    Requires API key authentication.

    Args:
        request: Batch verification request with list of usernames
        service: Injected verification service
        api_key: Verified API key from dependency
        x_forwarded_for: X-Forwarded-For header for rate limiting

    Returns:
        BatchVerificationResult with results for each username
    """
    # Get client IP for rate limiting
    settings = get_settings()
    client_ip = _get_client_ip(
        x_forwarded_for,
        trust_proxy=settings.trust_proxy_headers,
    )

    # Check rate limit
    rate_limit_service = get_rate_limit_service()
    is_allowed, count, retry_after, limit_type = (
        rate_limit_service.check_and_record_request(
            client_ip,
            is_authenticated=bool(api_key),
        )
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Rate limit exceeded. Please try again later.",
                    "details": {
                        "retry_after_seconds": int(retry_after),
                        "limit_type": limit_type,
                    },
                }
            },
            headers={"Retry-After": str(int(retry_after))},
        )

    # Record the request
    rate_limit_service.record_request(client_ip)

    if len(request.usernames) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "BATCH_LIMIT_EXCEEDED",
                    "message": "Batch verification limited to 50 usernames.",
                }
            },
        )

    # Normalize and check for duplicates
    normalized_usernames = []
    seen = set()
    for username in request.usernames:
        try:
            normalized = normalize_username(username)
        except UsernameValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_USERNAME",
                        "message": f"Invalid username: {e.reason}",
                        "details": {"username": e.username, "reason": e.reason},
                    }
                },
            ) from None

        if normalized in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "DUPLICATE_USERNAME",
                        "message": f"Duplicate username in batch: {normalized}",
                    }
                },
            )
        seen.add(normalized)
        normalized_usernames.append(normalized)

    results = await service.verify_batch(normalized_usernames)
    return BatchVerificationResult(results=results)


def _get_client_ip(
    x_forwarded_for: str | None,
    trust_proxy: bool = False,
    client_host: str | None = None,
) -> str:
    """Extract client IP from headers or direct connection.

    Args:
        x_forwarded_for: X-Forwarded-For header value.
        trust_proxy: Whether to trust proxy headers.
        client_host: Direct client IP from connection.

    Returns:
        Client IP address string.
    """
    if trust_proxy and x_forwarded_for:
        # Take the first IP in the chain (original client)
        return x_forwarded_for.split(",")[0].strip()
    # Use direct connection IP or default for test environments
    if client_host:
        return client_host
    return "127.0.0.1"
