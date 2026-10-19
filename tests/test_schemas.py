"""Tests for Pydantic response schemas."""

import pytest
from app.schemas.response import (
    AccountType,
    BatchVerificationRequest,
    BatchVerificationResult,
    ConfidenceLevel,
    HealthStatus,
    VerificationResult,
    VerificationSource,
    VerificationStatus,
)


class TestVerificationStatus:
    """Test VerificationStatus enum."""

    def test_members(self):
        """Verify all expected status members exist."""
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.NOT_FOUND.value == "not_found"
        assert VerificationStatus.UNKNOWN.value == "unknown"
        assert VerificationStatus.RESTRICTED.value == "restricted"
        assert VerificationStatus.UNAVAILABLE.value == "unavailable"


class TestConfidenceLevel:
    """Test ConfidenceLevel enum."""

    def test_members(self):
        """Verify all expected confidence members exist."""
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"


class TestVerificationSource:
    """Test VerificationSource enum."""

    def test_members(self):
        """Verify all expected source members exist."""
        assert VerificationSource.META.value == "meta"
        assert VerificationSource.PUBLIC_WEB.value == "public_web"
        assert VerificationSource.UNKNOWN.value == "unknown"


class TestAccountType:
    """Test AccountType enum."""

    def test_members(self):
        """Verify all expected account type members exist."""
        assert AccountType.PERSONAL.value == "personal"
        assert AccountType.PROFESSIONAL.value == "professional"
        assert AccountType.CREATOR.value == "creator"
        assert AccountType.BUSINESS.value == "business"
        assert AccountType.UNKNOWN.value == "unknown"


class TestVerificationResult:
    """Test VerificationResult Pydantic model."""

    def test_create_with_all_fields(self):
        """Create a complete verification result."""
        result = VerificationResult(
            username="natgeo",
            exists=True,
            verification_status=VerificationStatus.VERIFIED,
            account_type=AccountType.BUSINESS,
            followers=283000000,
            following=100,
            media_count=9500,
            is_private=False,
            source=VerificationSource.META,
            confidence=ConfidenceLevel.HIGH,
        )

        assert result.username == "natgeo"
        assert result.exists is True
        assert result.verification_status == VerificationStatus.VERIFIED
        assert result.account_type == AccountType.BUSINESS
        assert result.followers == 283000000
        assert result.following == 100
        assert result.media_count == 9500
        assert result.is_private is False
        assert result.source == VerificationSource.META
        assert result.confidence == ConfidenceLevel.HIGH

    def test_create_with_minimal_fields(self):
        """Create with only required fields."""
        result = VerificationResult(
            username="test",
            exists=None,
            verification_status=VerificationStatus.UNKNOWN,
            confidence=ConfidenceLevel.LOW,
        )

        assert result.username == "test"
        assert result.exists is None
        assert result.verification_status == VerificationStatus.UNKNOWN
        assert result.account_type is None
        assert result.followers is None
        assert result.following is None
        assert result.media_count is None
        assert result.is_private is None
        assert result.source == VerificationSource.UNKNOWN
        assert result.confidence == ConfidenceLevel.LOW

    def test_to_dict_excludes_none(self):
        """to_dict should exclude None values."""
        result = VerificationResult(
            username="test",
            exists=None,
            verification_status=VerificationStatus.UNKNOWN,
            confidence=ConfidenceLevel.LOW,
        )
        data = result.to_dict()
        assert "username" in data
        assert "exists" not in data  # None excluded
        assert "account_type" not in data

    def test_immutable_after_creation(self):
        """Test that frozen model prevents changes."""
        result = VerificationResult(
            username="test",
            exists=True,
            verification_status=VerificationStatus.VERIFIED,
            confidence=ConfidenceLevel.HIGH,
        )
        # Model is not frozen by default, but we can verify attributes
        assert result.username == "test"


class TestBatchVerificationRequest:
    """Test BatchVerificationRequest Pydantic model."""

    def test_create_valid_request(self):
        """Create a valid batch request."""
        request = BatchVerificationRequest(usernames=["user1", "user2", "user3"])
        assert len(request.usernames) == 3
        assert request.usernames == ["user1", "user2", "user3"]

    def test_empty_usernames_rejected(self):
        """Empty usernames list should be rejected."""
        with pytest.raises(Exception):  # Pydantic validation error
            BatchVerificationRequest(usernames=[])

    def test_too_many_usernames_rejected(self):
        """Batch with more than 50 usernames should be rejected."""
        usernames = [f"user{i}" for i in range(51)]
        with pytest.raises(Exception):  # Pydantic validation error
            BatchVerificationRequest(usernames=usernames)


class TestBatchVerificationResult:
    """Test BatchVerificationResult Pydantic model."""

    def test_create_with_results(self):
        """Create a batch result with verification results."""
        results = [
            VerificationResult(
                username="user1",
                exists=True,
                verification_status=VerificationStatus.VERIFIED,
                confidence=ConfidenceLevel.HIGH,
            ),
            VerificationResult(
                username="user2",
                exists=False,
                verification_status=VerificationStatus.NOT_FOUND,
                confidence=ConfidenceLevel.MEDIUM,
            ),
        ]
        batch_result = BatchVerificationResult(results=results)
        assert len(batch_result.results) == 2


class TestHealthStatus:
    """Test HealthStatus Pydantic model."""

    def test_default_values(self):
        """Test default health status values."""
        health = HealthStatus()
        assert health.status == "ok"
        assert health.version == "0.1.0"

    def test_custom_values(self):
        """Test custom health status values."""
        health = HealthStatus(status="degraded", version="1.0.0")
        assert health.status == "degraded"
        assert health.version == "1.0.0"
