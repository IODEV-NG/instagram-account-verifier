"""Public web verification provider using Playwright.

Uses controlled browser automation to check publicly available Instagram profiles.
This is a fallback for accounts not accessible via Meta's official API.

IMPORTANT: This provider does NOT:
- Bypass authentication
- Bypass CAPTCHA
- Access private profiles
- Circumvent rate limits or anti-bot measures

If Instagram blocks the request, it reports unknown rather than guessing.

Docs: https://playwright.dev/python/
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING, cast

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)

from app.providers.base import InstagramProvider, ProviderUnavailableError
from app.schemas.response import (
    AccountType,
    ConfidenceLevel,
    VerificationResult,
    VerificationSource,
    VerificationStatus,
)

if TYPE_CHECKING:
    from app.config import Settings


class PublicWebProvider(InstagramProvider):
    """Public web verification provider using Playwright.

    Uses controlled browser automation to check publicly available
    Instagram profiles.

    Access only publicly available profile pages through normal browser
    navigation. Does not bypass authentication, CAPTCHA, access controls,
    or rate limits.

    If Instagram blocks the request (login wall, challenge, rate limit),
    returns unknown rather than guessing.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize Public Web provider with settings.

        Args:
            settings: Application settings.
        """
        self._settings = settings
        self._playwright = None
        self._browser: Browser | None = None

    @property
    def name(self) -> str:
        """Provider name."""
        return "public_web"

    @property
    def is_configured(self) -> bool:
        """Check if public web verification is enabled."""
        return self._settings.public_web_enabled

    @property
    def source(self) -> VerificationSource:
        """Verification source."""
        return VerificationSource.PUBLIC_WEB

    async def _get_browser(self) -> Browser:
        """Get or create browser instance."""
        if self._browser is None:
            playwright = self._playwright
            if playwright is None:
                playwright = await async_playwright().start()
                self._playwright = playwright  # type: ignore[assignment]

            timeout = self._settings.public_web_timeout_seconds * 1000

            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                ],
            )
            browser.set_default_timeout(timeout)  # type: ignore[attr-defined]
            self._browser = cast(Browser, browser)

        return self._browser

    async def _get_context(self) -> BrowserContext:
        """Get a new browser context."""
        browser = await self._get_browser()
        return await browser.new_context(
            viewport={"width": 1024, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

    async def verify(self, username: str) -> VerificationResult:
        """Verify an Instagram account via public web.

        Navigates to the Instagram profile page and extracts available
        public information.

        Args:
            username: Normalized Instagram username.

        Returns:
            VerificationResult with the verification outcome.
            Returns unknown/restricted/unavailable when evidence insufficient.
        """
        if not self.is_configured:
            raise ProviderUnavailableError(
                self.name,
                "Public web verification is disabled"
            )

        page: Page | None = None
        context: BrowserContext | None = None

        try:
            browser = await self._get_browser()
            context = await browser.new_context(
                viewport={"width": 1024, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            page = await context.new_page()

            # Navigate to Instagram profile
            profile_url = f"https://www.instagram.com/{username}/"

            # Set navigation timeout
            page.set_default_timeout(self._settings.public_web_timeout_seconds * 1000)

            await page.goto(profile_url, wait_until="domcontentloaded")

            # Check for login wall / authentication required
            if await self._is_login_wall(page):
                return VerificationResult(
                    username=username,
                    exists=None,
                    verification_status=VerificationStatus.UNKNOWN,
                    account_type=None,
                    followers=None,
                    following=None,
                    media_count=None,
                    is_private=None,
                    source=self.source,
                    confidence=ConfidenceLevel.LOW,
                )

            # Check for "Not Found" / "No Posts Yet" page
            not_found = await self._check_not_found(page)
            if not_found:
                return VerificationResult(
                    username=username,
                    exists=False,
                    verification_status=VerificationStatus.NOT_FOUND,
                    account_type=None,
                    followers=None,
                    following=None,
                    media_count=None,
                    is_private=None,
                    source=self.source,
                    confidence=ConfidenceLevel.MEDIUM,
                )

            # Check for restricted/limited profile
            if await self._is_restricted(page):
                return VerificationResult(
                    username=username,
                    exists=True,
                    verification_status=VerificationStatus.RESTRICTED,
                    account_type=None,
                    followers=None,
                    following=None,
                    media_count=None,
                    is_private=None,
                    source=self.source,
                    confidence=ConfidenceLevel.LOW,
                )

            # Extract public profile data
            profile_data = await self._extract_profile_data(page)

            # Determine if account appears to exist
            exists = profile_data.get("exists", False)

            if exists:
                return VerificationResult(
                    username=username,
                    exists=True,
                    verification_status=VerificationStatus.VERIFIED,
                    account_type=(
                        AccountType(profile_data.get("account_type", "unknown"))
                        if profile_data.get("account_type")
                        else None
                    ),
                    followers=profile_data.get("followers"),
                    following=profile_data.get("following"),
                    media_count=profile_data.get("media_count"),
                    is_private=profile_data.get("is_private"),
                    source=self.source,
                    confidence=ConfidenceLevel.MEDIUM,
                )
            else:
                # Couldn't determine - might be private or unusual page
                return VerificationResult(
                    username=username,
                    exists=None,
                    verification_status=VerificationStatus.UNKNOWN,
                    account_type=None,
                    followers=None,
                    following=None,
                    media_count=None,
                    is_private=None,
                    source=self.source,
                    confidence=ConfidenceLevel.LOW,
                )

        except Exception:
            # Any error - return unavailable without leaking details
            return VerificationResult(
                username=username,
                exists=None,
                verification_status=VerificationStatus.UNAVAILABLE,
                account_type=None,
                followers=None,
                following=None,
                media_count=None,
                is_private=None,
                source=self.source,
                confidence=ConfidenceLevel.LOW,
            )
        finally:
            # Cleanup
            if page:
                await page.close()
            if context:
                await context.close()

    async def _is_login_wall(self, page: Page) -> bool:
        """Check if we've hit a login wall or authentication required page.

        Returns:
            True if login/authentication is required.
        """
        # Instagram login page indicators
        login_indicators = [
            'Log in to see photos and videos from your friends.',
            'Log in with Facebook',
            'Phone number, username, or email',
            'Password',
            'Forgot password?',
        ]

        page_text = await page.content()

        for indicator in login_indicators:
            if indicator.lower() in page_text.lower():
                return True

        # Check URL for login page
        return bool(
            "accounts/login" in page.url or "accounts/signup" in page.url
        )

    async def _check_not_found(self, page: Page) -> bool:
        """Check if the profile page indicates 'not found'.

        Returns:
            True if the profile doesn't exist or has no content.
        """
        page_text = await page.content()

        not_found_indicators = [
            "No posts yet",
            "This Account is not available",
            "Sorry, this page isn't available",
            "The link you followed may be broken",
            "This profile is empty",
        ]

        for indicator in not_found_indicators:
            if indicator.lower() in page_text.lower():
                return True

        return False

    async def _is_restricted(self, page: Page) -> bool:
        """Check if the profile has restricted visibility.

        Returns:
            True if profile appears restricted.
        """
        page_text = await page.content()

        restricted_indicators = [
            "This account is temporarily restricted",
            "Content not available",
            "This content isn't available right now",
        ]

        for indicator in restricted_indicators:
            if indicator.lower() in page_text.lower():
                return True

        return False

    async def _extract_profile_data(self, page: Page) -> dict:
        """Extract profile data from the page.

        Returns:
            Dictionary with extracted profile information.
        """
        result: dict = {
            "exists": False,
            "account_type": None,
            "followers": None,
            "following": None,
            "media_count": None,
            "is_private": None,
        }

        try:
            # Wait for main profile elements to load
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Get page content for parsing
            page_text = await page.content()

            # Check if profile exists (has basic structure)
            if 'class="[class="in pseudorandom"]' not in page_text:
                # Basic presence check - page loaded with content
                result["exists"] = True

            # Extract follower count using regex (Instagram's data attributes)
            # Instagram often embeds JSON data in page
            follow_data = self._extract_follow_stats(page_text)
            if follow_data:
                result["followers"] = follow_data.get("followers")
                result["following"] = follow_data.get("following")
                result["media_count"] = follow_data.get("media_count")

            # Check for private account indicator
            if (
                "This Account is Private" in page_text
                or "Log in to see this account" in page_text
            ):
                result["is_private"] = True

            # Check account type indicators
            if '"professional_type":"business"' in page_text:
                result["account_type"] = "business"
            elif '"professional_type":"creator"' in page_text:
                result["account_type"] = "creator"
            elif '"professional_type":"personal"' in page_text:
                result["account_type"] = "personal"

        except Exception:
            # Extraction failed but page loaded - keep what we have
            pass

        return result

    def _extract_follow_stats(self, page_text: str) -> dict | None:
        """Extract follower/following/media counts from page text.

        Instagram often embeds these in JSON-LD or data attributes.

        Returns:
            Dictionary with counts if found, None otherwise.
        """
        result: dict = {}

        # Pattern for JSON-like data in page
        # Look for patterns like: "edge_followed_by":{"count":12345}
        followers_match = re.search(
            r'"edge_followed_by"[\s:{"\[\]]*"count"\s*:\s*(\d+)',
            page_text
        )
        if followers_match:
            result["followers"] = int(followers_match.group(1))

        # Following count
        following_match = re.search(
            r'"edge_follow"[\s:{"\[\]]*"count"\s*:\s*(\d+)',
            page_text
        )
        if following_match:
            result["following"] = int(following_match.group(1))

        # Media count
        media_match = re.search(
            r'"edge_owner_to_timeline_media"[\s:{"\[\]]*"count"\s*:\s*(\d+)',
            page_text
        )
        if media_match:
            result["media_count"] = int(media_match.group(1))

        # Alternative: Look for og:description meta tag which often contains counts
        # e.g., <meta property="og:description" content="username • 1,234 followers"
        og_desc_match = re.search(
            r'og:description["\s:>]*content=["\']([^"\']*)(\d[\d,]*)\s*followers',
            page_text
        )
        if og_desc_match and "followers" not in result:
            follower_str = og_desc_match.group(2).replace(",", "")
            with contextlib.suppress(ValueError):
                result["followers"] = int(follower_str)

        return result if result else None

    async def health_check(self) -> bool:
        """Check public web provider health.

        Returns:
            True if provider is enabled and browser can launch.
        """
        if not self.is_configured:
            return False

        try:
            browser = await self._get_browser()
            # Try to create a simple page to verify browser works
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("about:blank", timeout=5000)
            await page.close()
            await context.close()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        if self._browser is not None:
            with contextlib.suppress(Exception):
                await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
            self._playwright = None
