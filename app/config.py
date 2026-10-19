"""Application configuration from environment variables.

Uses Pydantic Settings for type-safe configuration loading.
No secrets are logged or exposed.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_host: str = Field(default="0.0.0.0", description="API host binding")
    app_port: int = Field(default=8000, description="API port")

    # API Authentication
    api_key: str | None = Field(
        default=None,
        description="API key for authenticated requests (env-managed)"
    )

    # Meta (Instagram) API Configuration
    meta_app_id: str | None = Field(
        default=None,
        description="Meta App ID from developers.facebook.com",
    )
    meta_app_secret: str | None = Field(
        default=None,
        description="Meta App Secret (NEVER commit)",
    )
    meta_access_token: str | None = Field(
        default=None,
        description=(
            "Meta Access Token with instagram_basic, "
            "instagram_manage_insights, pages_read_engagement"
        ),
    )
    meta_api_version: str = Field(
        default="v19.0",
        description="Meta Graph API version (e.g., v19.0)",
    )
    meta_api_base_url: str = Field(
        default="https://graph.facebook.com",
        description="Meta Graph API base URL",
    )
    # The Instagram professional account ID of the caller (your app's user).
    # Required for Business Discovery queries.
    meta_instagram_account_id: str | None = Field(
        default=None,
        description=(
            "Caller's Instagram professional account ID "
            "for Business Discovery queries"
        ),
    )

    # Rate Limiting
    rate_limit_per_minute: int = Field(
        default=100,
        description="Max requests per minute per IP (unauthenticated)"
    )
    rate_limit_per_hour: int = Field(
        default=1000,
        description="Max requests per hour per API key (authenticated)"
    )

    # Redis (Optional - not required for basic operation)
    redis_url: str | None = Field(
        default=None,
        description="Redis URL for optional caching. If unset, caching disabled."
    )
    cache_ttl_seconds: int = Field(
        default=600,
        description="Cache TTL in seconds (default: 10 minutes)"
    )

    # Public Web Provider
    public_web_enabled: bool = Field(
        default=True,
        description="Enable public web verification fallback"
    )
    public_web_timeout_seconds: int = Field(
        default=30,
        description="Playwright browser timeout in seconds"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )

    # CORS
    cors_origins: str = Field(
        default="*",
        description="CORS allowed origins (comma-separated, or * for all)"
    )

    # Proxy Configuration
    # Set to True only when behind a trusted reverse proxy.
    # When True, X-Forwarded-For header is used for client IP.
    # When False, the direct connection IP is used (safer default).
    trust_proxy_headers: bool = Field(
        default=False,
        description="Trust X-Forwarded-For header from reverse proxy"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {valid_levels}")
        return v.upper()

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Validate CORS origins format."""
        if v == "*":
            return v
        # Simple validation: should be comma-separated URLs
        origins = [o.strip() for o in v.split(",") if o.strip()]
        if not origins:
            raise ValueError("cors_origins must not be empty if not '*'")
        return v

    @property
    def meta_configured(self) -> bool:
        """Check if Meta API is properly configured."""
        return bool(
            self.meta_app_id
            and self.meta_app_secret
            and self.meta_access_token
            and self.meta_instagram_account_id
        )

    @property
    def redis_available(self) -> bool:
        """Check if Redis is configured and available."""
        return bool(self.redis_url)

    def __str__(self) -> str:
        """Return a safe string representation without secrets."""
        safe = {
            "app_host": self.app_host,
            "app_port": self.app_port,
            "meta_configured": self.meta_configured,
            "redis_available": self.redis_available,
            "public_web_enabled": self.public_web_enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "log_level": self.log_level,
        }
        return f"Settings({safe})"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Returns:
        Settings instance loaded from environment.

    Raises:
        ValidationError: If required configuration is invalid.
    """
    try:
        return Settings()
    except ValidationError as e:
        # Re-raise with a clear message about missing configuration
        raise RuntimeError(
            "Invalid application configuration. "
            "Check your .env file or environment variables. "
            "See .env.example for required settings."
        ) from e


# Module-level convenience function for testing
def create_settings(**overrides: str | int | bool | None) -> Settings:
    """Create settings with overrides for testing.

    Args:
        **overrides: Setting names and values to override.

    Returns:
        Settings instance with the specified overrides applied.
    """
    settings = Settings()
    for key, value in overrides.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    return settings
