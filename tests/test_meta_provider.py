"""Tests for Meta provider with mocked HTTP responses.

Tests the Meta Business Discovery flow:
  GET /{caller_ig_user_id}?fields=business_discovery.username({target}){followers_count,media_count}

All HTTP interactions are mocked. No live requests or real credentials.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.config import create_settings
from app.providers.meta import (
    MetaProvider,
    MetaAuthError,
    MetaPermissionError,
    MetaRateLimitError,
    MetaApiError,
)


def _make_settings(**overrides):
    """Create Meta-configured settings for tests."""
    base = {
        "meta_app_id": "test_app_id",
        "meta_app_secret": "test_app_secret",
        "meta_access_token": "test_access_token",
        "meta_instagram_account_id": "17841405309211844",
    }
    base.update(overrides)
    return create_settings(**base)


class TestMetaProviderConfigured:
    """Test Meta provider behavior when configured."""

    @pytest.fixture
    def settings(self):
        """Create settings with Meta credentials."""
        return _make_settings()

    @pytest.fixture
    def provider(self, settings):
        """Create Meta provider with settings."""
        return MetaProvider(settings)

    def test_provider_name(self, provider):
        """Provider should have correct name."""
        assert provider.name == "meta"

    def test_provider_source(self, provider):
        """Provider should have correct source."""
        assert provider.source.value == "meta"

    def test_provider_is_configured(self, provider):
        """Provider should be configured with credentials."""
        assert provider.is_configured is True

    def test_provider_unconfigured_without_account_id(self):
        """Provider should not be configured without caller account ID."""
        settings = create_settings(
            meta_app_id="test_app_id",
            meta_app_secret="test_app_secret",
            meta_access_token="test_access_token",
            # meta_instagram_account_id omitted
        )
        provider = MetaProvider(settings)
        assert provider.is_configured is False

    def test_provider_unconfigured_without_credentials(self):
        """Provider should not be configured without any credentials."""
        settings = create_settings()
        provider = MetaProvider(settings)
        assert provider.is_configured is False

    def test_verify_raises_when_unconfigured(self):
        """Verify should raise when not configured."""
        settings = create_settings()
        provider = MetaProvider(settings)

        with pytest.raises(Exception):  # ProviderUnavailableError
            import asyncio
            asyncio.run(provider.verify("testuser"))

    def test_build_url_uses_caller_account_id(self):
        """Business Discovery URL must use the caller IG user ID."""
        settings = _make_settings(meta_instagram_account_id="123456789")
        provider = MetaProvider(settings)
        url_path, params = provider._build_business_discovery_url("bluebottle")

        assert url_path == "/v19.0/123456789"
        assert params["access_token"] == "test_access_token"
        assert "business_discovery.username(bluebottle)" in params["fields"]
        assert "followers_count" in params["fields"]
        assert "media_count" in params["fields"]

    def test_build_url_raises_when_caller_id_missing(self):
        """Building the URL must raise when caller account ID is missing."""
        settings = _make_settings(meta_instagram_account_id=None)
        provider = MetaProvider(settings)

        from app.providers.base import ProviderUnavailableError

        with pytest.raises(ProviderUnavailableError):
            provider._build_business_discovery_url("bluebottle")


class TestMetaProviderVerify:
    """Test Meta provider verify method with mocked HTTP."""

    @pytest.fixture
    def settings(self):
        """Create settings with Meta credentials."""
        return _make_settings()

    @pytest.fixture
    def provider(self, settings):
        """Create Meta provider with settings."""
        return MetaProvider(settings)

    @pytest.mark.asyncio
    async def test_verify_successful_business_discovery(self, provider):
        """Verify should return verified with followers_count when discovered."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "id": "17841405309211844",
            "business_discovery": {
                "id": "17841401441775531",
                "username": "bluebottle",
                "followers_count": 267793,
                "media_count": 1205,
            },
        })

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.verify("bluebottle")

            assert result.username == "bluebottle"
            assert result.exists is True
            assert result.verification_status.value == "verified"
            assert result.account_type.value == "professional"
            assert result.followers == 267793
            assert result.media_count == 1205
            assert result.followers is not None
            assert result.source.value == "meta"
            assert result.confidence.value == "high"

    @pytest.mark.asyncio
    async def test_verify_followers_count_may_be_missing(self, provider):
        """Response without followers_count must not fabricate a value."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "id": "17841405309211844",
            "business_discovery": {
                "id": "17841401441775531",
                "username": "bluebottle",
                "media_count": 1205,
                # followers_count deliberately absent
            },
        })

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.verify("bluebottle")

            assert result.exists is True
            assert result.followers is None
            assert result.media_count == 1205

    @pytest.mark.asyncio
    async def test_verify_no_business_discovery_returns_unknown(self, provider):
        """Response without business_discovery must not claim not_found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "id": "17841405309211844",
            # No business_discovery field
        })

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.verify("someuser")

            assert result.exists is None
            assert result.verification_status.value == "unknown"
            assert result.confidence.value == "low"

    @pytest.mark.asyncio
    async def test_verify_malformed_json_returns_unknown(self, provider):
        """Malformed JSON response must return unknown, not raise."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(side_effect=ValueError("invalid json"))

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.verify("bluebottle")

            assert result.exists is None
            assert result.verification_status.value == "unknown"

    @pytest.mark.asyncio
    async def test_verify_401_raises_auth_error(self, provider):
        """Verify should raise auth error for 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(MetaAuthError):
                await provider.verify("bluebottle")

    @pytest.mark.asyncio
    async def test_verify_403_raises_permission_error(self, provider):
        """Verify should raise permission error for 403."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(MetaPermissionError):
                await provider.verify("bluebottle")

    @pytest.mark.asyncio
    async def test_verify_404_returns_unknown(self, provider):
        """Verify should return unknown for 404 (Meta cannot access target)."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.verify("nonexistent")

            assert result.exists is None
            assert result.verification_status.value == "unknown"
            assert result.confidence.value == "low"

    @pytest.mark.asyncio
    async def test_verify_429_raises_rate_limit_error(self, provider):
        """Verify should raise rate limit error for 429."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(MetaRateLimitError):
                await provider.verify("bluebottle")

    @pytest.mark.asyncio
    async def test_verify_500_raises_error(self, provider):
        """Verify should raise MetaApiError for 500 errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json = MagicMock()

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(MetaApiError) as exc_info:
                await provider.verify("bluebottle")
            assert exc_info.value.code == "META_UNAVAILABLE"
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_verify_timeout_returns_unavailable(self, provider):
        """Verify should return unavailable on timeout."""
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_get_client.return_value = mock_client

            result = await provider.verify("bluebottle")

            assert result.verification_status.value == "unavailable"
            assert result.exists is None

    @pytest.mark.asyncio
    async def test_verify_connection_error_returns_unavailable(self, provider):
        """Verify should return unavailable on connection errors."""
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.RequestError("connection failed")
            )
            mock_get_client.return_value = mock_client

            result = await provider.verify("bluebottle")

            assert result.verification_status.value == "unavailable"
            assert result.exists is None


class TestMetaProviderHealthCheck:
    """Test Meta provider health check."""

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self):
        """Health check should return False when unconfigured."""
        settings = create_settings()
        provider = MetaProvider(settings)
        assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_missing_caller_id(self):
        """Health check should return False when caller account ID is missing."""
        settings = _make_settings(meta_instagram_account_id=None)
        provider = MetaProvider(settings)
        assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_configured_success(self):
        """Health check should return True when configured and API works."""
        settings = _make_settings()
        provider = MetaProvider(settings)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(provider, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_configured_failure(self):
        """Health check should return False when API call fails."""
        settings = _make_settings()
        provider = MetaProvider(settings)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("API error"))
            mock_get_client.return_value = mock_client

            result = await provider.health_check()
            assert result is False
