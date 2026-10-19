"""Provider interface for Instagram verification.

Defines the abstract base class that all verification providers must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.schemas.response import (
    AccountType,
    ConfidenceLevel,
    VerificationResult,
    VerificationSource,
    VerificationStatus,
)

if TYPE_CHECKING:
    from app.config import Settings


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider is not available for use."""

    def __init__(self, provider_name: str, reason: str) -> None:
        self.provider_name = provider_name
        self.reason = reason
        super().__init__(f"Provider '{provider_name}' unavailable: {reason}")


class InstagramProvider(ABC):
    """Abstract base class for Instagram verification providers.

    All verification providers must implement this interface.
    The verification engine uses providers to determine account status.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and reporting."""
        ...

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider has necessary configuration."""
        ...

    @property
    @abstractmethod
    def source(self) -> VerificationSource:
        """Verification source identifier for results."""
        ...

    @abstractmethod
    async def verify(self, username: str) -> VerificationResult:
        """Verify an Instagram account.

        Args:
            username: Normalized Instagram username to verify.

        Returns:
            VerificationResult with the verification outcome.

        Raises:
            ProviderUnavailableError: If the provider cannot perform verification.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the provider is healthy and available.

        Returns:
            True if the provider is available, False otherwise.
        """
        return self.is_configured


class MetaProvider(InstagramProvider):
    """Meta (official Instagram) API provider.

    Uses Meta's official Instagram Business Discovery API to verify
    professional/business accounts and retrieve official data.

    NOTE: Meta's official API does not provide unrestricted lookup of
    arbitrary personal Instagram accounts. This provider only works
    for accounts accessible through Meta's official API.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize Meta provider with settings.

        Args:
            settings: Application settings containing Meta configuration.
        """
        self._settings = settings

    @property
    def name(self) -> str:
        """Provider name."""
        return "meta"

    @property
    def is_configured(self) -> bool:
        """Check if Meta API credentials are configured."""
        return self._settings.meta_configured

    @property
    def source(self) -> VerificationSource:
        """Verification source."""
        return VerificationSource.META

    async def verify(self, username: str) -> VerificationResult:
        """Verify via Meta API.

        For this milestone, returns an unavailable result since we're using
        mocked providers for deterministic testing. In production, this would
        call the Meta Graph API.

        Args:
            username: Normalized Instagram username.

        Returns:
            VerificationResult indicating Meta provider status.
        """
        if not self.is_configured:
            raise ProviderUnavailableError(
                self.name,
                "Meta API credentials not configured"
            )

        # Production implementation would call Meta Graph API here
        # For now, we return a result indicating the provider is configured
        # but the actual verification is handled by the test mocks
        return VerificationResult(
            username=username,
            exists=None,
            verification_status=VerificationStatus.UNKNOWN,
            account_type=None,
            followers=None,
            following=None,
            media_count=None,
            is_private=None,
            source=self.source,
            confidence=ConfidenceLevel.LOW,
        )

    async def health_check(self) -> bool:
        """Check Meta provider health.

        Returns:
            True if configured, False otherwise.
        """
        return self.is_configured


class PublicWebProvider(InstagramProvider):
    """Public web verification provider.

    Uses controlled web access to check publicly available Instagram profiles.
    This is a fallback for accounts not accessible via Meta's official API.

    IMPORTANT: This provider does NOT:
    - Bypass authentication
    - Bypass CAPTCHA
    - Access private profiles
    - Circumvent rate limits or anti-bot measures

    If Instagram blocks the request, it reports unknown rather than guessing.

    NOTE: For this milestone, actual browser automation is stubbed.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize Public Web provider with settings.

        Args:
            settings: Application settings.
        """
        self._settings = settings

    @property
    def name(self) -> str:
        """Provider name."""
        return "public_web"

    @property
    def is_configured(self) -> bool:
        """Check if public web verification is enabled."""
        return self._settings.public_web_enabled

    @property
    def source(self) -> VerificationSource:
        """Verification source."""
        return VerificationSource.PUBLIC_WEB

    async def verify(self, username: str) -> VerificationResult:
        """Verify via public web.

        For this milestone, returns an unknown result since we're using
        mocked providers for deterministic testing.

        Args:
            username: Normalized Instagram username.

        Returns:
            VerificationResult indicating public web provider status.
        """
        if not self.is_configured:
            raise ProviderUnavailableError(
                self.name,
                "Public web verification is disabled"
            )

        # Production implementation would use Playwright here
        # For now, return a result indicating the provider is configured
        return VerificationResult(
            username=username,
            exists=None,
            verification_status=VerificationStatus.UNKNOWN,
            account_type=None,
            followers=None,
            following=None,
            media_count=None,
            is_private=None,
            source=self.source,
            confidence=ConfidenceLevel.LOW,
        )

    async def health_check(self) -> bool:
        """Check public web provider health.

        Returns:
            True if enabled, False otherwise.
        """
        return self.is_configured


class MockMetaProvider(MetaProvider):
    """Mock Meta provider for testing.

    Simulates Meta API responses for deterministic testing.
    Override is_configured to always return True for testing.
    """

    def __init__(self, settings: Settings, mock_results: dict[str, dict]) -> None:
        """Initialize mock Meta provider.

        Args:
            settings: Application settings.
            mock_results: Dictionary mapping usernames to mock response data.
        """
        super().__init__(settings)
        self._mock_results = mock_results

    @property
    def is_configured(self) -> bool:
        """Mock provider is always configured for testing."""
        return True

    async def verify(self, username: str) -> VerificationResult:
        """Return mock verification result.

        Args:
            username: Normalized Instagram username.

        Returns:
            Mock VerificationResult based on configured mock data.
        """
        if username in self._mock_results:
            data = self._mock_results[username]
            return VerificationResult(
                username=username,
                exists=data.get("exists", False),
                verification_status=VerificationStatus.VERIFIED
                if data.get("exists")
                else VerificationStatus.NOT_FOUND,
                account_type=AccountType(data["account_type"])
                if data.get("account_type")
                else None,
                followers=data.get("followers"),
                following=data.get("following"),
                media_count=data.get("media_count"),
                is_private=data.get("is_private"),
                source=self.source,
                confidence=ConfidenceLevel.HIGH,
            )

        # User not in mock data - simulate not found via Meta
        return VerificationResult(
            username=username,
            exists=False,
            verification_status=VerificationStatus.NOT_FOUND,
            account_type=None,
            followers=None,
            following=None,
            media_count=None,
            is_private=None,
            source=self.source,
            confidence=ConfidenceLevel.MEDIUM,
        )


class MockPublicWebProvider(PublicWebProvider):
    """Mock Public Web provider for testing.

    Simulates public web verification responses for deterministic testing.
    Override is_configured to always return True for testing.
    """

    def __init__(self, settings: Settings, mock_results: dict[str, dict]) -> None:
        """Initialize mock public web provider.

        Args:
            settings: Application settings.
            mock_results: Dictionary mapping usernames to mock response data.
        """
        super().__init__(settings)
        self._mock_results = mock_results

    @property
    def is_configured(self) -> bool:
        """Mock provider is always configured for testing."""
        return True

    async def verify(self, username: str) -> VerificationResult:
        """Return mock verification result.

        Args:
            username: Normalized Instagram username.

        Returns:
            Mock VerificationResult based on configured mock data.
        """
        if username in self._mock_results:
            data = self._mock_results[username]
            return VerificationResult(
                username=username,
                exists=data.get("exists"),
                verification_status=VerificationStatus(data["verification_status"]),
                account_type=AccountType(data["account_type"])
                if data.get("account_type")
                else None,
                followers=data.get("followers"),
                following=data.get("following"),
                media_count=data.get("media_count"),
                is_private=data.get("is_private"),
                source=self.source,
                confidence=ConfidenceLevel(data["confidence"]),
            )

        # User not in mock data - simulate not found via public web
        return VerificationResult(
            username=username,
            exists=False,
            verification_status=VerificationStatus.NOT_FOUND,
            account_type=None,
            followers=None,
            following=None,
            media_count=None,
            is_private=None,
            source=self.source,
            confidence=ConfidenceLevel.MEDIUM,
        )
