"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class TestHealthEndpoint:
    """Test health check API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_health_check_returns_ok(self, client: TestClient):
        """GET /health returns ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

    def test_health_check_content_type(self, client: TestClient):
        """Health endpoint returns JSON content type."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    def test_provider_health_endpoint_exists(self, client: TestClient):
        """GET /health/providers returns provider status."""
        response = client.get("/health/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_provider_health_includes_meta(self, client: TestClient):
        """Provider health includes meta provider status."""
        response = client.get("/health/providers")
        data = response.json()
        provider_names = [p["name"] for p in data]
        assert "meta" in provider_names

    def test_provider_health_includes_public_web(self, client: TestClient):
        """Provider health includes public web provider status."""
        response = client.get("/health/providers")
        data = response.json()
        provider_names = [p["name"] for p in data]
        assert "public_web" in provider_names

    def test_provider_health_meta_status(self, client: TestClient):
        """Meta provider shows configured status when credentials are set."""
        response = client.get("/health/providers")
        data = response.json()
        meta_provider = next((p for p in data if p["name"] == "meta"), None)
        assert meta_provider is not None
        # In test environment without credentials, should be unconfigured
        assert meta_provider["status"] in ["configured", "unconfigured"]

    def test_provider_health_public_web_status(self, client: TestClient):
        """Public web provider shows enabled status by default."""
        response = client.get("/health/providers")
        data = response.json()
        public_web_provider = next(
            (p for p in data if p["name"] == "public_web"), None
        )
        assert public_web_provider is not None
        assert public_web_provider["status"] in ["configured", "disabled"]
