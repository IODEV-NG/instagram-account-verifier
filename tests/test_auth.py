"""Tests for API key authentication."""

import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Settings


class TestAuthMissingKey:
    """Test authentication when API key is missing."""

    @pytest.fixture
    def client_with_auth_enabled(self):
        """Create test client with API key configured."""
        settings = Settings()
        settings.api_key = "test_api_key_12345"

        # Patch get_settings in the dependencies module where it's used
        with patch("app.api.dependencies.get_settings", return_value=settings):
            app = create_app()
            yield TestClient(app)

    def test_verify_without_key_returns_401(self, client_with_auth_enabled):
        """Verify endpoint should return 401 when API key missing."""
        response = client_with_auth_enabled.get("/api/v1/verify/natgeo")
        assert response.status_code == 401
        data = response.json()
        # Error is nested under 'detail' for HTTPException
        assert data["detail"]["error"]["code"] == "INVALID_API_KEY"

    def test_batch_without_key_returns_401(self, client_with_auth_enabled):
        """Batch endpoint should return 401 when API key missing."""
        response = client_with_auth_enabled.post(
            "/api/v1/verify/batch",
            json={"usernames": ["natgeo"]},
        )
        assert response.status_code == 401
        data = response.json()
        # Error is nested under 'detail' for HTTPException
        assert data["detail"]["error"]["code"] == "INVALID_API_KEY"

    def test_health_ends_remain_public(self, client_with_auth_enabled):
        """Health endpoints should remain public."""
        response = client_with_auth_enabled.get("/health")
        assert response.status_code == 200

        response = client_with_auth_enabled.get("/health/providers")
        assert response.status_code == 200


class TestAuthInvalidKey:
    """Test authentication with invalid API key."""

    @pytest.fixture
    def client_with_auth_enabled(self):
        """Create test client with API key configured."""
        settings = Settings()
        settings.api_key = "correct_api_key_12345"

        # Patch get_settings in the dependencies module where it's used
        with patch("app.api.dependencies.get_settings", return_value=settings):
            app = create_app()
            yield TestClient(app)

    def test_verify_with_wrong_key_returns_401(self, client_with_auth_enabled):
        """Verify endpoint should return 401 with wrong API key."""
        response = client_with_auth_enabled.get(
            "/api/v1/verify/natgeo",
            headers={"X-API-Key": "wrong_key"},
        )
        assert response.status_code == 401
        data = response.json()
        # Error is nested under 'detail' for HTTPException
        assert data["detail"]["error"]["code"] == "INVALID_API_KEY"

    def test_verify_with_empty_key_returns_401(self, client_with_auth_enabled):
        """Verify endpoint should return 401 with empty API key."""
        response = client_with_auth_enabled.get(
            "/api/v1/verify/natgeo",
            headers={"X-API-Key": ""},
        )
        assert response.status_code == 401
        data = response.json()
        # Error is nested under 'detail' for HTTPException
        assert data["detail"]["error"]["code"] == "INVALID_API_KEY"


class TestAuthValidKey:
    """Test authentication with valid API key."""

    @pytest.fixture
    def client_with_auth_enabled(self):
        """Create test client with API key configured."""
        settings = Settings()
        settings.api_key = "valid_test_key_12345"

        # Patch get_settings in the dependencies module where it's used
        with patch("app.api.dependencies.get_settings", return_value=settings):
            app = create_app()
            yield TestClient(app)

    def test_verify_with_valid_key_succeeds(self, client_with_auth_enabled):
        """Verify endpoint should succeed with valid API key."""
        response = client_with_auth_enabled.get(
            "/api/v1/verify/natgeo",
            headers={"X-API-Key": "valid_test_key_12345"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "natgeo"

    def test_batch_with_valid_key_succeeds(self, client_with_auth_enabled):
        """Batch endpoint should succeed with valid API key."""
        response = client_with_auth_enabled.post(
            "/api/v1/verify/batch",
            json={"usernames": ["natgeo"]},
            headers={"X-API-Key": "valid_test_key_12345"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data


class TestAuthDisabled:
    """Test authentication when API key is not configured."""

    @pytest.fixture
    def client_without_auth(self):
        """Create test client without API key configured."""
        settings = Settings()
        settings.api_key = None

        # Patch get_settings in the dependencies module where it's used
        with patch("app.api.dependencies.get_settings", return_value=settings):
            app = create_app()
            yield TestClient(app)

    def test_verify_works_without_key_when_disabled(self, client_without_auth):
        """Verify endpoint should work without key when auth disabled."""
        response = client_without_auth.get("/api/v1/verify/natgeo")
        assert response.status_code == 200

    def test_health_works_without_key_when_disabled(self, client_without_auth):
        """Health endpoint should work without key."""
        response = client_without_auth.get("/health")
        assert response.status_code == 200
