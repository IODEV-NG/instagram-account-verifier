"""Username normalization and validation.

Handles multiple input formats:
- @username
- username
- https://instagram.com/username
- https://www.instagram.com/username/
"""

import re
from typing import Final

# Instagram username pattern: alphanumeric, underscores, dots, 1-30 chars
# Instagram's actual rules: 1-30 characters, letters, numbers, underscores, dots
# but a dot cannot be the first or last character, and cannot be consecutive
USERNAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9_][a-zA-Z0-9_.]{0,28}[a-zA-Z0-9_]$|^[a-zA-Z0-9_]{1,2}$"
)

MAX_USERNAME_LENGTH: Final[int] = 30

# URL patterns for extracting usernames from Instagram URLs
INSTAGRAM_URL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?$"
)


class UsernameValidationError(ValueError):
    """Raised when a username fails validation."""

    def __init__(self, username: str, reason: str = "invalid_username") -> None:
        self.username = username
        self.reason = reason
        super().__init__(f"Invalid username '{username}': {reason}")


def normalize_username(raw_input: str | None) -> str:
    """Normalize a username from various input formats.

    Args:
        raw_input: Raw username input. Can be:
            - A plain username: "john"
            - With @ prefix: "@john"
            - Instagram URL: "https://instagram.com/john"
            - Instagram URL with trailing slash: "https://instagram.com/john/"

    Returns:
        Normalized username string (lowercase? No, case preserved).

    Raises:
        UsernameValidationError: If the input is empty, invalid, or exceeds
            length limits.
    """
    if raw_input is None:
        raise UsernameValidationError("", "empty_input")

    # Strip whitespace
    cleaned = raw_input.strip()

    if not cleaned:
        raise UsernameValidationError("", "empty_input")

    # Handle @ prefix
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]

    # Handle Instagram URL
    url_match = INSTAGRAM_URL_PATTERN.match(cleaned)
    if url_match:
        cleaned = url_match.group(1)

    # Strip any remaining whitespace after extraction
    cleaned = cleaned.strip()

    if not cleaned:
        raise UsernameValidationError(raw_input, "empty_after_normalization")

    # Validate length
    if len(cleaned) > MAX_USERNAME_LENGTH:
        raise UsernameValidationError(
            cleaned, f"exceeds_max_length_{MAX_USERNAME_LENGTH}"
        )

    # Validate pattern: alphanumeric, underscores, dots only
    # Must start and end with alphanumeric or underscore (no leading/trailing dots)
    if not _is_valid_username_pattern(cleaned):
        raise UsernameValidationError(cleaned, "invalid_characters")

    return cleaned


def _is_valid_username_pattern(username: str) -> bool:
    """Check if username matches Instagram's pattern rules.

    Rules:
    - 1-30 characters
    - Letters (a-z, A-Z), numbers (0-9), underscores (_), dots (.)
    - Cannot start or end with a dot
    - Cannot have consecutive dots
    """
    if not username:
        return False

    if len(username) > MAX_USERNAME_LENGTH:
        return False

    # Check for invalid characters
    if not re.match(r"^[a-zA-Z0-9_.]+$", username):
        return False

    # Check for leading or trailing dots
    if username.startswith(".") or username.endswith("."):
        return False

    # Check for consecutive dots
    return ".." not in username
