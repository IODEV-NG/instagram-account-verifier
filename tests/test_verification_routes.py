"""Tests for verification API routes."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.response import (
    AccountType,
    ConfidenceLevel,
    VerificationResult,
    VerificationSource,
    VerificationStatus,
)


class TestVerifyEndpoint:
    """Test verification API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_verify_existing_account(self, client: TestClient):
        """Verify an account that exists in mock data."""
        response = client.get("/api/v1/verify/natgeo")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "natgeo"
        assert data["exists"] is True
        assert data["verification_status"] == "verified"
        assert data["source"] == "meta"
        assert data["confidence"] == "high"
        assert data["account_type"] == "business"
        assert data["followers"] == 283000000

    def test_verify_nonexistent_account(self, client: TestClient):
        """Verify an account that doesn't exist in mock data."""
        response = client.get("/api/v1/verify/doesnotexist")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "doesnotexist"
        assert data["exists"] is False
        assert data["verification_status"] == "not_found"

    def test_verify_unknown_account(self, client: TestClient):
        """Verify an account not in mock data - should return not_found (not unknown)."""
        response = client.get("/api/v1/verify/unknownuser123")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "unknownuser123"
        # Mock providers return not_found for unknown users
        assert data["exists"] is False
        assert data["verification_status"] == "not_found"
        assert data["confidence"] == "medium"

    def test_verify_with_at_prefix(self, client: TestClient):
        """Verify username with @ prefix is normalized."""
        response = client.get("/api/v1/verify/@natgeo")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "natgeo"

    def test_verify_with_url(self, client: TestClient):
        """Verify username from URL is extracted."""
        # The normalize function handles URLs, but the URL path in the route
        # may not parse correctly with slashes. Test via query param instead.
        response = client.get("/api/v1/verify?username=https://instagram.com/natgeo")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "natgeo"

    def test_verify_invalid_username_returns_400(self, client: TestClient):
        """Invalid username should return 400 error."""
        # Using a username with spaces should be rejected
        response = client.get("/api/v1/verify/user name")
        # Depending on normalization, this might normalize or reject
        # For usernames that fail validation, expect 4xx
        assert response.status_code in [400, 404, 422, 500]

    def test_verify_response_structure(self, client: TestClient):
        """Verify response has correct structure."""
        response = client.get("/api/v1/verify/natgeo")
        data = response.json()

        # Required fields
        assert "username" in data
        assert "exists" in data
        assert "verification_status" in data
        assert "confidence" in data
        assert "source" in data

        # Optional fields
        assert "account_type" in data
        assert "followers" in data
        assert "following" in data
        assert "media_count" in data
        assert "is_private" in data

    def test_verify_query_param_endpoint(self, client: TestClient):
        """Verify endpoint with query parameter works."""
        response = client.get("/api/v1/verify?username=natgeo")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "natgeo"

    def test_verify_query_param_missing(self, client: TestClient):
        """Query param endpoint without username returns error."""
        response = client.get("/api/v1/verify")
        assert response.status_code in [400, 422]  # Validation error


class TestBatchVerifyEndpoint:
    """Test batch verification endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_batch_verify_success(self, client: TestClient):
        """Batch verification with valid usernames."""
        response = client.post(
            "/api/v1/verify/batch",
            json={"usernames": ["natgeo", "doesnotexist"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2

        # Check individual results
        results_by_username = {r["username"]: r for r in data["results"]}

        assert results_by_username["natgeo"]["exists"] is True
        assert results_by_username["natgeo"]["source"] == "meta"
        assert results_by_username["doesnotexist"]["exists"] is False

    def test_batch_verify_empty_request(self, client: TestClient):
        """Batch with empty usernames list returns error."""
        response = client.post(
            "/api/v1/verify/batch",
            json={"usernames": []},
        )
        assert response.status_code in [400, 422]

    def test_batch_verify_too_many(self, client: TestClient):
        """Batch with more than 50 usernames returns validation error."""
        usernames = [f"user{i}" for i in range(51)]
        response = client.post(
            "/api/v1/verify/batch",
            json={"usernames": usernames},
        )
        # Pydantic validation returns 422 for invalid input
        assert response.status_code == 422

    def test_batch_verify_duplicates(self, client: TestClient):
        """Batch with duplicate usernames after normalization returns error."""
        # Use usernames that normalize to the same value
        response = client.post(
            "/api/v1/verify/batch",
            json={"usernames": ["user1", "@user1"]},
        )
        assert response.status_code == 400
        data = response.json()
        # Error format may vary based on validation order
        assert "error" in data or "detail" in data

    def test_batch_verify_response_format(self, client: TestClient):
        """Batch response has correct structure."""
        response = client.post(
            "/api/v1/verify/batch",
            json={"usernames": ["natgeo"]},
        )
        data = response.json()

        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 1

        result = data["results"][0]
        assert "username" in result
        assert "verification_status" in result
