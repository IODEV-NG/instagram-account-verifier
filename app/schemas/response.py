"""Pydantic schemas for API responses.

Defines verification states, confidence levels, and response models.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VerificationStatus(StrEnum):
    """Verification outcome states.

    Distinguishes between confirmed results, confirmed not-found, and inconclusive.
    """

    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"
    RESTRICTED = "restricted"
    UNAVAILABLE = "unavailable"


class ConfidenceLevel(StrEnum):
    """Confidence level for a verification result."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VerificationSource(StrEnum):
    """Source of verification data."""

    META = "meta"
    PUBLIC_WEB = "public_web"
    UNKNOWN = "unknown"


class AccountType(StrEnum):
    """Instagram account types."""

    PERSONAL = "personal"
    PROFESSIONAL = "professional"
    CREATOR = "creator"
    BUSINESS = "business"
    UNKNOWN = "unknown"


class VerificationResult(BaseModel):
    """Normalized verification result for a single username."""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(
        ..., description="Normalized Instagram username"
    )
    exists: bool | None = Field(
        None,
        description="Whether the account exists. True, False, or None for inconclusive."
    )
    verification_status: VerificationStatus = Field(
        ...,
        description="Verification outcome state"
    )
    account_type: AccountType | None = Field(
        None,
        description="Account type if known, None otherwise"
    )
    followers: int | None = Field(
        None,
        description="Follower count if available from official source, None otherwise"
    )
    following: int | None = Field(
        None,
        description="Following count if available, None otherwise"
    )
    media_count: int | None = Field(
        None,
        description="Media/post count if available, None otherwise"
    )
    is_private: bool | None = Field(
        None,
        description="Whether account is private if known, None otherwise"
    )
    source: VerificationSource = Field(
        VerificationSource.UNKNOWN,
        description="Source of the verification data"
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level for this result"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json", exclude_none=True)


class BatchVerificationRequest(BaseModel):
    """Request model for batch verification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    usernames: list[str] = Field(
        ...,
        description="List of usernames to verify",
        min_length=1,
        max_length=50,
    )


class BatchVerificationResult(BaseModel):
    """Response model for batch verification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    results: list[VerificationResult] = Field(
        ...,
        description="Verification results for each requested username"
    )


class HealthStatus(BaseModel):
    """API health check response."""

    model_config = ConfigDict(str_strip_whitespace=True)

    status: str = Field(
        "ok",
        description="Overall API health status"
    )
    version: str = Field(
        "0.1.0",
        description="API version"
    )


class ProviderHealth(BaseModel):
    """Individual provider health status."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        description="Provider name"
    )
    status: str = Field(
        ...,
        description="Provider status: configured, available, unavailable, disabled"
    )
