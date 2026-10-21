"""Tests for username normalization."""

import pytest
from app.services.normalizer import normalize_username, UsernameValidationError


class TestNormalizeUsername:
    """Test username normalization from various input formats."""

    def test_plain_username_preserved(self):
        """Plain usernames without prefix/suffix remain unchanged."""
        assert normalize_username("john") == "john"
        assert normalize_username("natgeo") == "natgeo"
        assert normalize_username("test123") == "test123"

    def test_at_prefix_stripped(self):
        """Usernames with @ prefix have it stripped."""
        assert normalize_username("@john") == "john"
        assert normalize_username("@natgeo") == "natgeo"

    def test_https_instagram_com_url_extracted(self):
        """https://instagram.com/username URLs extract the username."""
        assert normalize_username("https://instagram.com/john") == "john"
        assert normalize_username("https://instagram.com/natgeo") == "natgeo"

    def test_https_www_instagram_com_url_extracted(self):
        """https://www.instagram.com/username/ URLs extract the username."""
        assert normalize_username("https://www.instagram.com/john/") == "john"
        assert normalize_username("https://www.instagram.com/natgeo") == "natgeo"

    def test_http_urls_also_work(self):
        """HTTP URLs are handled the same as HTTPS."""
        assert normalize_username("http://instagram.com/john") == "john"
        assert normalize_username("http://www.instagram.com/john/") == "john"

    def test_url_with_trailing_slash_normalized(self):
        """URLs with trailing slashes are normalized correctly."""
        assert normalize_username("https://instagram.com/john/") == "john"
        assert normalize_username("https://www.instagram.com/john/") == "john"

    def test_whitespace_stripped(self):
        """Leading and trailing whitespace is removed."""
        assert normalize_username("  john  ") == "john"
        assert normalize_username("\t@john\n") == "john"

    def test_empty_username_raises_error(self):
        """Empty or whitespace-only input raises validation error."""
        with pytest.raises(UsernameValidationError):
            normalize_username("")
        with pytest.raises(UsernameValidationError):
            normalize_username("   ")
        with pytest.raises(UsernameValidationError):
            normalize_username(None)  # type: ignore[arg-type]

    def test_invalid_username_characters_rejected(self):
        """Usernames with invalid characters raise validation error."""
        with pytest.raises(UsernameValidationError):
            normalize_username("user name")  # spaces
        with pytest.raises(UsernameValidationError):
            normalize_username("user@name")  # @ in middle
        with pytest.raises(UsernameValidationError):
            normalize_username("user/name")  # slash

    def test_very_long_username_rejected(self):
        """Extremely long usernames are rejected."""
        long_username = "a" * 100
        with pytest.raises(UsernameValidationError):
            normalize_username(long_username)

    def test_short_username_accepted(self):
        """Short but valid usernames are accepted."""
        assert normalize_username("a") == "a"
        assert normalize_username("ab") == "ab"
        assert normalize_username("abc") == "abc"

    def test_mixed_case_preserved(self):
        """Username case is preserved after normalization."""
        assert normalize_username("@JohnDoe") == "JohnDoe"
        assert normalize_username("https://instagram.com/JohnDoe") == "JohnDoe"


class TestInstagramShareLinks:
    """Share links copied from the Instagram app must normalize cleanly.

    The app and web share sheet append a tracking query string (`?igsh=...`)
    or a fragment. Those links used to fail validation with a misleading
    "exceeds max length" error, so the username was never checked.
    """

    def test_url_with_query_string_extracts_username(self):
        assert (
            normalize_username("https://instagram.com/john?igsh=abc123")
            == "john"
        )
        assert (
            normalize_username("https://www.instagram.com/natgeo/?igsh=MTY5")
            == "natgeo"
        )

    def test_url_with_fragment_extracts_username(self):
        assert normalize_username("https://instagram.com/john#top") == "john"

    def test_url_with_dot_username_and_query(self):
        assert (
            normalize_username("https://www.instagram.com/john.doe/?igsh=x")
            == "john.doe"
        )

    def test_query_string_does_not_bypass_validation(self):
        with pytest.raises(UsernameValidationError):
            normalize_username("https://instagram.com/john..doe?igsh=x")
