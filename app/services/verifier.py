"""Verification service that orchestrates provider-based verification.

The verifier tries providers in order and returns the best available result.
It handles provider failures gracefully and never fabricates results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.providers.base import (
    InstagramProvider,
    ProviderUnavailableError,
)
from app.schemas.response import (
    ConfidenceLevel,
    VerificationResult,
    VerificationSource,
    VerificationStatus,
)

if TYPE_CHECKING:
    from app.config import Settings


class VerificationService:
    """Service that orchestrates Instagram account verification.

    Uses a prioritized list of providers and returns the best available result.
    Never fabricates results; if no provider can verify, returns inconclusive.
    """

    def __init__(
        self,
        meta_provider: InstagramProvider | None = None,
        public_web_provider: InstagramProvider | None = None,
    ) -> None:
        """Initialize verifier with optional providers.

        Args:
            meta_provider: Meta API provider (optional).
            public_web_provider: Public web provider (optional).
        """
        self._meta_provider = meta_provider
        self._public_web_provider = public_web_provider

    @property
    def meta_provider(self) -> InstagramProvider | None:
        """Get the Meta provider."""
        return self._meta_provider

    @property
    def public_web_provider(self) -> InstagramProvider | None:
        """Get the public web provider."""
        return self._public_web_provider

    async def verify(self, username: str) -> VerificationResult:
        """Verify an Instagram account using available providers.

        Strategy:
        1. Try Meta provider first (highest confidence, official data)
        2. Fall back to public web provider if Meta unavailable/not found
        3. Return inconclusive if no provider can verify

        Args:
            username: Normalized Instagram username.

        Returns:
            VerificationResult with the verification outcome.
        """
        # Try Meta provider first
        if self._meta_provider and self._meta_provider.is_configured:
            try:
                result = await self._meta_provider.verify(username)
                if result.verification_status != VerificationStatus.UNKNOWN:
                    return result
            except ProviderUnavailableError:
                # Meta provider is not available, continue to next
                pass

        # Try public web provider
        if self._public_web_provider and self._public_web_provider.is_configured:
            try:
                result = await self._public_web_provider.verify(username)
                if result.verification_status != VerificationStatus.UNKNOWN:
                    return result
            except ProviderUnavailableError:
                # Public web provider is not available
                pass

        # No provider could verify - return inconclusive
        return VerificationResult(
            username=username,
            exists=None,
            verification_status=VerificationStatus.UNKNOWN,
            account_type=None,
            followers=None,
            following=None,
            media_count=None,
            is_private=None,
            source=VerificationSource.UNKNOWN,
            confidence=ConfidenceLevel.LOW,
        )

    async def verify_batch(self, usernames: list[str]) -> list[VerificationResult]:
        """Verify multiple Instagram accounts.

        Args:
            usernames: List of normalized usernames to verify.

        Returns:
            List of VerificationResult for each username.
        """
        results = []
        for username in usernames:
            result = await self.verify(username)
            results.append(result)
        return results


class VerificationServiceFactory:
    """Factory for creating configured verifier services.

    This allows dependency injection and testing with mock providers.
    """

    @staticmethod
    def create(
        settings: Settings,
        meta_provider: InstagramProvider | None = None,
        public_web_provider: InstagramProvider | None = None,
    ) -> VerificationService:
        """Create a verifier service with the given providers.

        Args:
            settings: Application settings.
            meta_provider: Optional Meta provider (uses MockMetaProvider if None).
            public_web_provider: Optional public web provider (uses
                MockPublicWebProvider if None).

        Returns:
            Configured VerifierService instance.
        """
        if meta_provider is None:
            # Default to mock for testing/demo
            from app.providers.base import MockMetaProvider

            mock_results = {
                "natgeo": {
                    "exists": True,
                    "account_type": "business",
                    "followers": 283000000,
                    "following": 100,
                    "media_count": 9500,
                    "is_private": False,
                },
            }
            meta_provider = MockMetaProvider(settings, mock_results)

        if public_web_provider is None:
            # Default to mock for testing/demo
            from app.providers.base import MockPublicWebProvider

            mock_results = {
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
            public_web_provider = MockPublicWebProvider(settings, mock_results)

        return VerificationService(
            meta_provider=meta_provider,
            public_web_provider=public_web_provider,
        )
