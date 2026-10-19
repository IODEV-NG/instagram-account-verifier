"""Real Meta (Instagram) Graph API provider.

Uses Meta's official Instagram Business Discovery API to verify
professional/business accounts and retrieve official data.

IMPORTANT: Meta's official API does not provide unrestricted lookup of
arbitrary personal Instagram accounts. This provider only works
for accounts accessible through Meta's official API.

Docs:
  https://developers.facebook.com/docs/instagram-platform/
  instagram-api-with-facebook-login/business-discovery

Business Discovery flow:
  GET /{caller_ig_user_id}?fields=
      business_discovery.username({target_username})
      {followers_count,media_count}

Required permissions on the access token:
  - instagram_basic
  - instagram_manage_insights
  - pages_read_engagement
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.providers.base import InstagramProvider, ProviderUnavailableError
from app.schemas.response import (
    AccountType,
    ConfidenceLevel,
    VerificationResult,
    VerificationSource,
    VerificationStatus,
)

if TYPE_CHECKING:
    from app.config import Settings


class MetaApiError(Exception):
    """Base exception for Meta API errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int | None = None,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class MetaAuthError(MetaApiError):
    """Authentication/authorization error (401/403)."""

    pass


class MetaPermissionError(MetaApiError):
    """Insufficient permissions error."""

    pass


class MetaRateLimitError(MetaApiError):
    """Rate limit error (429)."""

    pass


class MetaNotFoundError(MetaApiError):
    """Resource not found (404)."""

    pass


class MetaProvider(InstagramProvider):
    """Meta (official Instagram) API provider.

    Uses Meta's official Instagram Business Discovery API to verify
    professional/business accounts and retrieve official data.

    Business Discovery request pattern:
      GET /{caller_ig_user_id}?fields=
          business_discovery.username({target})
          {followers_count,media_count}

    The caller must be an eligible Instagram professional account
    that has authorized the Meta app. The access token must have
    instagram_basic, instagram_manage_insights, and
    pages_read_engagement permissions.

    Requires settings:
      meta_app_id, meta_app_secret, meta_access_token,
      meta_instagram_account_id
    """,  # noqa: B018

    def __init__(self, settings: Settings) -> None:
        """Initialize Meta provider with settings.

        Args:
            settings: Application settings containing Meta configuration.
        """
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

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

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper configuration."""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=10.0,
                pool=5.0,
            )
            self._client = httpx.AsyncClient(
                base_url=self._settings.meta_api_base_url,
                timeout=timeout,
                follow_redirects=False,
            )
        return self._client

    def _build_business_discovery_url(
        self, username: str,
    ) -> tuple[str, dict[str, str]]:
        """Build the Business Discovery request URL and parameters.

        The endpoint is:
          GET /{caller_ig_user_id}?fields=
              business_discovery.username({target})
              {followers_count,media_count}

        Args:
            username: Normalized target Instagram username.

        Returns:
            Tuple of (url_path, params_dict).
        """
        caller_id = self._settings.meta_instagram_account_id
        if not caller_id:
            raise ProviderUnavailableError(
                self.name,
                "Meta Instagram account ID (caller) not configured. "
                "Set META_INSTAGRAM_ACCOUNT_ID to the caller's "
                "professional account ID.",
            )

        # Build fields expression.
        # business_discovery.username({username}){followers_count,media_count}
        fields = (
            f"business_discovery.username({username})"
            f"{{followers_count,media_count}}"
        )
        token = self._settings.meta_access_token
        if not token:
            raise ProviderUnavailableError(
                self.name,
                "Meta access token is not configured.",
            )
        params: dict[str, str] = {
            "fields": fields,
            "access_token": token,
        }

        # URL path: /{version}/{caller_ig_user_id}
        url_path = (
            f"/{self._settings.meta_api_version}/{caller_id}"
        )
        return url_path, params

    async def verify(self, username: str) -> VerificationResult:
        """Verify an Instagram account via Meta Business Discovery API.

        Uses the Business Discovery field expansion to look up the target
        professional account by username and retrieve available metrics.

        Args:
            username: Normalized Instagram username.

        Returns:
            VerificationResult with the verification outcome.
            Returns unavailable on provider/network failures.

        Raises:
            ProviderUnavailableError: If credentials not configured.
        """
        if not self.is_configured:
            raise ProviderUnavailableError(
                self.name,
                "Meta API credentials not configured. "
                "Set META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN, "
                "and META_INSTAGRAM_ACCOUNT_ID.",
            )

        try:
            url_path, params = self._build_business_discovery_url(username)
            client = await self._get_client()

            response = await client.get(
                url_path,
                params=params,
                timeout=30.0,
            )

            # Handle HTTP errors
            if response.status_code == 401:
                raise MetaAuthError(
                    code="META_AUTH_ERROR",
                    message="Meta API authentication failed. Check access token.",
                    status_code=401,
                )
            elif response.status_code == 403:
                raise MetaPermissionError(
                    code="META_PERMISSION_ERROR",
                    message=(
                        "Meta API permissions insufficient. "
                        "Required: instagram_basic, instagram_manage_insights, "
                        "pages_read_engagement."
                    ),
                    status_code=403,
                )
            elif response.status_code == 404:
                # Target account not found via Business Discovery.
                # This is not "not_found" for the verification;
                # Meta just cannot access it.
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
            elif response.status_code == 429:
                raise MetaRateLimitError(
                    code="META_RATE_LIMITED",
                    message="Meta API rate limit exceeded.",
                    status_code=429,
                )
            elif response.status_code >= 500:
                raise MetaApiError(
                    code="META_UNAVAILABLE",
                    message=f"Meta API server error: {response.status_code}",
                    status_code=response.status_code,
                )
            elif response.status_code != 200:
                raise MetaApiError(
                    code="META_API_ERROR",
                    message=f"Meta API error: {response.status_code}",
                    status_code=response.status_code,
                )

            # Parse successful response
            try:
                data = response.json()
            except ValueError:
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

            return self._parse_business_discovery_response(data, username)

        except MetaApiError:
            raise
        except httpx.TimeoutException:
            return VerificationResult(
                username=username,
                exists=None,
                verification_status=VerificationStatus.UNAVAILABLE,
                account_type=None,
                followers=None,
                following=None,
                media_count=None,
                is_private=None,
                source=self.source,
                confidence=ConfidenceLevel.LOW,
            )
        except httpx.RequestError:
            return VerificationResult(
                username=username,
                exists=None,
                verification_status=VerificationStatus.UNAVAILABLE,
                account_type=None,
                followers=None,
                following=None,
                media_count=None,
                is_private=None,
                source=self.source,
                confidence=ConfidenceLevel.LOW,
            )
        except Exception:
            return VerificationResult(
                username=username,
                exists=None,
                verification_status=VerificationStatus.UNAVAILABLE,
                account_type=None,
                followers=None,
                following=None,
                media_count=None,
                is_private=None,
                source=self.source,
                confidence=ConfidenceLevel.LOW,
            )

    def _parse_business_discovery_response(
        self,
        data: dict,
        username: str,
    ) -> VerificationResult:
        """Parse a Business Discovery API response.

        The response shape is:
            {
                "id": "<caller_ig_user_id>",
                "business_discovery": {
                    "id": "<target_ig_user_id>",
                    "username": "<target_username>",
                    "followers_count": 12345,
                    "media_count": 678,
                }
            }

        We only parse username and followers_count. We do not fabricate
        any values that the API did not actually return.

        Args:
            data: Parsed JSON response body.
            username: The target username we queried.

        Returns:
            VerificationResult reflecting what the API actually supplied.
        """
        business_discovery = data.get("business_discovery")

        # The API may return the caller object without a business_discovery
        # field when the target account is not accessible (e.g., personal,
        # age-gated, or insufficient permissions).
        if not isinstance(business_discovery, dict):
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

        # Extract only the fields the API actually provided
        target_username = business_discovery.get("username")
        followers_count = business_discovery.get("followers_count")
        media_count = business_discovery.get("media_count")
        # target_id is available but not currently used in the response.
        _ = business_discovery.get("id")

        # If the API returned the target username, the account exists and
        # is a professional account accessible through Business Discovery.
        if target_username:
            return VerificationResult(
                username=username,
                exists=True,
                verification_status=VerificationStatus.VERIFIED,
                account_type=AccountType.PROFESSIONAL,
                followers=followers_count if followers_count is not None else None,
                following=None,
                media_count=media_count if media_count is not None else None,
                is_private=None,
                source=self.source,
                confidence=ConfidenceLevel.HIGH,
            )

        # business_discovery present but username missing is unexpected;
        # treat as unknown rather than not_found.
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
        """Check Meta provider health by testing API connectivity.

        Returns:
            True if configured and API is accessible, False otherwise.
        """
        if not self.is_configured:
            return False

        try:
            client = await self._get_client()
            caller_id = self._settings.meta_instagram_account_id
            if not caller_id:
                return False
            response = await client.get(
                f"/{self._settings.meta_api_version}/{caller_id}",
                params={
                    "fields": "id",
                    "access_token": self._settings.meta_access_token,
                },
                timeout=10.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
