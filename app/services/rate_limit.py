"""In-memory rate limiting service.

Provides simple per-IP rate limiting without requiring Redis.
Rate limits are not shared across workers in multi-process deployments.

For distributed rate limiting, Redis would be needed but is optional.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

from app.config import get_settings

# Type alias for backward compatibility
Callable = object


@dataclass
class RateLimitEntry:
    """Tracks request timestamps for a single key (IP or API key)."""

    timestamps: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_request(self, now: float) -> None:
        """Add a request timestamp."""
        with self.lock:
            self.timestamps.append(now)
            # Keep only recent timestamps within the window
            self.timestamps = [t for t in self.timestamps if now - t < 60]

    def count_in_window(self, window_seconds: int, now: float) -> int:
        """Count requests in the given time window."""
        with self.lock:
            cutoff = now - window_seconds
            return sum(1 for t in self.timestamps if t > cutoff)

    def is_allowed(
        self,
        max_requests: int,
        window_seconds: int,
        now: float | None = None,
    ) -> tuple[bool, int, float]:
        """Check if request is allowed under rate limit.

        Args:
            max_requests: Maximum requests allowed in window.
            window_seconds: Time window in seconds.
            now: Current time (defaults to time.time()).

        Returns:
            Tuple of (is_allowed, current_count, retry_after_seconds).
        """
        if now is None:
            now = time.time()

        with self.lock:
            cutoff = now - window_seconds
            # Clean old timestamps
            self.timestamps = [t for t in self.timestamps if t > cutoff]

            current_count = len(self.timestamps)
            is_allowed = current_count < max_requests

            if not is_allowed:
                # Calculate when the oldest request expires
                oldest = min(self.timestamps) if self.timestamps else now
                retry_after = oldest + window_seconds - now
                retry_after = max(1.0, retry_after)  # At least 1 second
            else:
                retry_after = 0.0

            return is_allowed, current_count, retry_after


class RateLimiter:
    """In-memory rate limiter.

    Tracks requests per key (typically IP address or API key).
    Not shared across workers in multi-process deployments.

    For distributed rate limiting, use Redis backend instead.
    """

    def __init__(self) -> None:
        """Initialize rate limiter."""
        self._entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._lock = threading.Lock()

    def get_entry(self, key: str) -> RateLimitEntry:
        """Get or create rate limit entry for a key."""
        with self._lock:
            if key not in self._entries:
                self._entries[key] = RateLimitEntry()
            return self._entries[key]

    def check_request(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: float | None = None,
    ) -> tuple[bool, int, float]:
        """Check if a request is allowed under rate limit.

        Args:
            key: Identifier for the client.
            max_requests: Maximum requests allowed in window.
            window_seconds: Time window in seconds.
            now: Current time (defaults to time.time()).

        Returns:
            Tuple of (is_allowed, current_count, retry_after_seconds).
        """
        entry = self.get_entry(key)
        return entry.is_allowed(max_requests, window_seconds, now)

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: float | None = None,
    ) -> tuple[bool, int, float]:
        """Check if a request is allowed under rate limit.

        Args:
            key: Identifier for the client (IP or API key).
            max_requests: Maximum requests allowed in window.
            window_seconds: Time window in seconds.
            now: Current time (defaults to time.time()).

        Returns:
            Tuple of (is_allowed, current_count, retry_after_seconds).
        """
        entry = self.get_entry(key)
        return entry.is_allowed(max_requests, window_seconds, now)

    def add_request(self, key: str, now: float | None = None) -> None:
        """Record a request for a key.

        Args:
            key: Identifier for the client.
            now: Current time (defaults to time.time()).
        """
        if now is None:
            now = time.time()
        entry = self.get_entry(key)
        entry.add_request(now)

    def cleanup(self, max_age_seconds: int = 300) -> int:
        """Remove stale entries.

        Args:
            max_age_seconds: Remove entries older than this.

        Returns:
            Number of entries removed.
        """
        now = time.time()
        cutoff = now - max_age_seconds

        with self._lock:
            keys_to_remove = [
                key for key, entry in self._entries.items()
                if entry.timestamps and min(entry.timestamps) < cutoff
            ]
            for key in keys_to_remove:
                del self._entries[key]
            return len(keys_to_remove)


class RateLimitService:
    """Service for applying rate limits to requests.

    Uses configurable limits from settings.
    """

    def __init__(self) -> None:
        """Initialize rate limit service."""
        self._limiter = RateLimiter()
        self._enabled = True

    @property
    def enabled(self) -> bool:
        """Whether rate limiting is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable rate limiting."""
        self._enabled = value

    def check_and_record_request(
        self,
        client_id: str,
        is_authenticated: bool = False,
    ) -> tuple[bool, int, float, str | None]:
        """Check if a request is allowed and record it.

        Args:
            client_id: Client identifier (IP or API key).
            is_authenticated: Whether the client authenticated with API key.

        Returns:
            Tuple of (is_allowed, current_count, retry_after_seconds, limit_type).
            limit_type is 'minute' or 'hour' depending on which limit applies.
        """
        if not self._enabled:
            return True, 0, 0.0, None

        settings = get_settings()

        if is_authenticated:
            # Authenticated clients get higher limits
            max_per_hour = settings.rate_limit_per_hour
            allowed, count, retry_after = self._limiter.check_request(
                client_id,
                max_requests=max_per_hour,
                window_seconds=3600,
            )
            if not allowed:
                return False, count, retry_after, "hour"
            # Also check per-minute limit
            max_per_minute = settings.rate_limit_per_minute * 2  # Higher for auth
            allowed, count, retry_after = self._limiter.check_request(
                client_id,
                max_requests=max_per_minute,
                window_seconds=60,
            )
            # Record the request after checking
            self._limiter.add_request(client_id)
            return allowed, count, retry_after, "minute"
        else:
            # Unauthenticated clients get lower limits
            max_per_minute = settings.rate_limit_per_minute
            allowed, count, retry_after = self._limiter.check_request(
                client_id,
                max_requests=max_per_minute,
                window_seconds=60,
            )
            # Record the request after checking
            self._limiter.add_request(client_id)
            return allowed, count, retry_after, "minute"

    def record_request(self, client_id: str) -> None:
        """Record a request for a client (alias for add_request).

        Args:
            client_id: Client identifier.
        """
        self._limiter.add_request(client_id)

    def add_request(self, client_id: str) -> None:
        """Record a request for a client.

        Args:
            client_id: Client identifier.
        """
        self._limiter.add_request(client_id)

    def get_rate_limit_headers(
        self,
        client_id: str,
        is_authenticated: bool = False,
    ) -> dict[str, str]:
        """Get rate limit headers for response.

        Args:
            client_id: Client identifier.
            is_authenticated: Whether client is authenticated.

        Returns:
            Dictionary of rate limit headers.
        """
        if not self._enabled:
            return {}

        settings = get_settings()

        if is_authenticated:
            limit = settings.rate_limit_per_hour
            window = 3600
        else:
            limit = settings.rate_limit_per_minute
            window = 60

        count = self._limiter.get_entry(client_id).count_in_window(window, time.time())

        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, limit - count)),
            "X-RateLimit-Reset": str(int(time.time() + window)),
        }


# Global rate limit service instance
_rate_limit_service: RateLimitService | None = None
_service_lock = threading.Lock()


def get_rate_limit_service() -> RateLimitService:
    """Get the global rate limit service instance."""
    global _rate_limit_service

    if _rate_limit_service is None:
        with _service_lock:
            if _rate_limit_service is None:
                _rate_limit_service = RateLimitService()

    return _rate_limit_service


def reset_rate_limit_service() -> None:
    """Reset the rate limit service (for testing)."""
    global _rate_limit_service
    with _service_lock:
        _rate_limit_service = RateLimitService()
