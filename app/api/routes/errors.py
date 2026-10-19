"""Custom exception handlers for structured error responses.

Provides consistent error response format across the API.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class APIError(Exception):
    """Base class for API errors with structured response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class InvalidUsernameError(APIError):
    """Raised when username validation fails."""

    def __init__(self, username: str, reason: str) -> None:
        super().__init__(
            code="INVALID_USERNAME",
            message=f"Invalid username: {reason}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"username": username, "reason": reason},
        )


class VerificationUnavailableError(APIError):
    """Raised when verification cannot be completed."""

    def __init__(self, reason: str = "verification_unavailable") -> None:
        super().__init__(
            code="VERIFICATION_UNAVAILABLE",
            message="Account verification could not be completed.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"reason": reason},
        )


class RateLimitError(APIError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int | None = None) -> None:
        details: dict = {}
        if retry_after is not None:
            details["retry_after_seconds"] = retry_after

        super().__init__(
            code="RATE_LIMITED",
            message="Rate limit exceeded. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class BatchLimitExceededError(APIError):
    """Raised when batch size exceeds limit."""

    def __init__(self, max_allowed: int = 50) -> None:
        super().__init__(
            code="BATCH_LIMIT_EXCEEDED",
            message=f"Batch verification limited to {max_allowed} usernames.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"max_allowed": max_allowed},
        )


class DuplicateUsernameError(APIError):
    """Raised when duplicate usernames are found in batch request."""

    def __init__(self, username: str) -> None:
        super().__init__(
            code="DUPLICATE_USERNAME",
            message=f"Duplicate username in batch: {username}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"username": username},
        )


def add_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers with the FastAPI app."""

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        """Handle APIError exceptions with structured response."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **({"details": exc.details} if exc.details else {}),
                }
            },
        )

    @app.exception_handler(VerificationUnavailableError)
    async def verification_unavailable_handler(
        request: Request, exc: VerificationUnavailableError
    ) -> JSONResponse:
        """Handle VerificationUnavailableError."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **({"details": exc.details} if exc.details else {}),
                }
            },
        )

    @app.exception_handler(InvalidUsernameError)
    async def invalid_username_handler(
        request: Request, exc: InvalidUsernameError
    ) -> JSONResponse:
        """Handle InvalidUsernameError."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **({"details": exc.details} if exc.details else {}),
                }
            },
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
        """Handle RateLimitError."""
        response = JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **({"details": exc.details} if exc.details else {}),
                }
            },
        )
        if "retry_after_seconds" in exc.details:
            response.headers["Retry-After"] = str(exc.details["retry_after_seconds"])
        return response

    @app.exception_handler(BatchLimitExceededError)
    async def batch_limit_handler(
        request: Request, exc: BatchLimitExceededError
    ) -> JSONResponse:
        """Handle BatchLimitExceededError."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **({"details": exc.details} if exc.details else {}),
                }
            },
        )

    @app.exception_handler(DuplicateUsernameError)
    async def duplicate_username_handler(
        request: Request, exc: DuplicateUsernameError
    ) -> JSONResponse:
        """Handle DuplicateUsernameError."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **({"details": exc.details} if exc.details else {}),
                }
            },
        )
