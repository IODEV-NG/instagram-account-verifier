"""Tests for rate limiting service."""

import time
import pytest
from unittest.mock import patch, MagicMock

from app.services.rate_limit import (
    RateLimitEntry,
    RateLimitService,
    get_rate_limit_service,
    reset_rate_limit_service,
)


class TestRateLimitEntry:
    """Test basic rate limit entry functionality."""

    def test_entry_add_request(self):
        """Adding requests should increment count."""
        entry = RateLimitEntry()
        entry.add_request(time.time())
        entry.add_request(time.time())

        count = entry.count_in_window(60, time.time())
        assert count == 2

    def test_entry_is_allowed_under_limit(self):
        """Should be allowed when under limit."""
        entry = RateLimitEntry()

        allowed, count, retry_after = entry.is_allowed(
            max_requests=10,
            window_seconds=60,
        )
        assert allowed is True
        assert count == 0

    def test_entry_is_blocked_over_limit(self):
        """Should be blocked when over limit."""
        entry = RateLimitEntry()

        # Fill up to limit
        for _ in range(10):
            entry.add_request(time.time())

        allowed, count, retry_after = entry.is_allowed(
            max_requests=10,
            window_seconds=60,
        )
        assert allowed is False
        assert count == 10
        assert retry_after > 0

    def test_entry_cleanup_old_timestamps(self):
        """Old timestamps should be cleaned up."""
        entry = RateLimitEntry()

        # Add old timestamp
        old_time = time.time() - 120
        entry.add_request(old_time)

        # Add new timestamp
        entry.add_request(time.time())

        # Count should only include recent ones
        count = entry.count_in_window(60, time.time())
        assert count == 1


class TestRateLimitService:
    """Test rate limit service with configuration."""

    def test_check_and_record_request_unauthenticated(self):
        """Unauthenticated requests should use per-minute limit."""
        with patch("app.services.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_per_minute = 100
            mock_settings.return_value.rate_limit_per_hour = 1000

            service = RateLimitService()
            allowed, count, retry_after, limit_type = service.check_and_record_request(
                "test_ip",
                is_authenticated=False,
            )

            assert allowed is True
            assert limit_type == "minute"

    def test_check_and_record_request_authenticated(self):
        """Authenticated requests should use higher limits."""
        with patch("app.services.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_per_minute = 100
            mock_settings.return_value.rate_limit_per_hour = 1000

            service = RateLimitService()
            allowed, count, retry_after, limit_type = service.check_and_record_request(
                "test_api_key",
                is_authenticated=True,
            )

            assert allowed is True
            # Should check both minute and hour limits
            assert limit_type in ("minute", "hour")

    def test_request_count_increments(self):
        """Request count should increment after recording."""
        with patch("app.services.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_per_minute = 100
            mock_settings.return_value.rate_limit_per_hour = 1000

            service = RateLimitService()
            client_id = "test_ip"

            # First request - count should be 0 before recording
            allowed1, count1, _, _ = service.check_and_record_request(client_id)
            assert allowed1 is True
            assert count1 == 0  # Count is before this request

            # Second request - count should be 1 (from first request)
            allowed2, count2, _, _ = service.check_and_record_request(client_id)
            assert allowed2 is True
            assert count2 == 1  # Count includes first request

    def test_rate_limit_headers(self):
        """Rate limit headers should be generated correctly."""
        with patch("app.services.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_per_minute = 100
            mock_settings.return_value.rate_limit_per_hour = 1000

            service = RateLimitService()
            client_id = "test_ip"

            headers = service.get_rate_limit_headers(client_id)
            assert "X-RateLimit-Limit" in headers
            assert "X-RateLimit-Remaining" in headers
            assert "X-RateLimit-Reset" in headers

    def test_disabled_rate_limiting(self):
        """Disabled rate limiting should allow all requests."""
        service = RateLimitService()
        service.enabled = False

        allowed, count, retry_after, limit_type = service.check_and_record_request("test_ip")
        assert allowed is True
        assert count == 0
        assert retry_after == 0.0
        assert limit_type is None



