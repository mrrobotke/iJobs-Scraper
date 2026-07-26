"""Base adapter classes for job portal sources.

Provides APIAdapter (httpx), HTMLAdapter (BeautifulSoup), and
BrowserAdapter (Playwright) with built-in rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from ijobs_scraper.exceptions import AdapterError, RateLimitError
from ijobs_scraper.models import RawListing, SourceConfig

logger = logging.getLogger(__name__)

_TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class BaseAdapter(ABC):
    """Abstract base for all portal adapters."""

    @abstractmethod
    def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Yield raw job listings from the source."""
        ...  # pragma: no cover

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Optionally fetch full job details. Default: return as-is."""
        return listing

    def can_handle_url(self, url: str) -> bool:
        """Return True if this adapter can parse the given URL (for manual scraper)."""
        return False

    def _require_config(self, config: SourceConfig, key: str) -> str:
        """Extract a required string config value, raising AdapterError if missing.

        Args:
            config: The source configuration to read from.
            key: The config key to look up in ``config.config``.

        Returns:
            The config value as a string.

        Raises:
            AdapterError: If the key is missing or not a string.
        """
        value = config.config.get(key)
        if value is None:
            raise AdapterError(
                self.__class__.__name__,
                f"Missing required config key '{key}'. "
                f"Provide it in SourceConfig(config={{'{key}': '...'}})",
                retryable=False,
            )
        if not isinstance(value, str):
            raise AdapterError(
                self.__class__.__name__,
                f"Config key '{key}' must be a string, got {type(value).__name__}",
                retryable=False,
            )
        return value

    @staticmethod
    def _validate_url(url: str, expected_host: str) -> str | None:
        """Validate that a URL uses HTTP(S) and matches the expected host.

        Prevents SSRF by rejecting URLs with non-HTTP schemes or
        unexpected hosts that may have been injected via malicious
        ``href`` attributes in scraped HTML. Uses suffix matching
        on the netloc to prevent spoofing via subdomains like
        ``expected_host.evil.com``.

        Args:
            url: The URL to validate.
            expected_host: The expected host suffix for the URL
                (e.g. ``"brightermonday.co.ke"``).

        Returns:
            The URL if valid, or ``None`` if it fails validation.
        """
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        if parsed.scheme not in ("http", "https"):
            return None
        netloc = (parsed.netloc or "").split(":")[0]
        if netloc != expected_host and not netloc.endswith("." + expected_host):
            return None
        return url


class APIAdapter(BaseAdapter):
    """Base for REST API sources. Provides httpx client with rate limiting."""

    def __init__(
        self,
        request_delay: float = 1.0,
        *,
        max_attempts: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
        retry_jitter: float = 0.0,
    ) -> None:
        self._request_delay = request_delay
        self._max_attempts = max(1, max_attempts)
        self._retry_base_delay = max(0.0, retry_base_delay)
        self._retry_max_delay = max(self._retry_base_delay, retry_max_delay)
        self._retry_jitter = max(0.0, retry_jitter)
        self._last_request_time: float = 0.0
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Lazily create and return the httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._request_delay:
            await asyncio.sleep(self._request_delay - elapsed)
        self._last_request_time = time.monotonic()

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """HTTP GET with rate limiting and bounded transient retries."""
        return await self._request_json("GET", url, params=params, headers=headers)

    async def _post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """HTTP POST with rate limiting and bounded transient retries."""
        return await self._request_json("POST", url, json=json, headers=headers)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Issue a JSON request, retrying transient responses and transport errors."""
        client = await self._ensure_client()

        for attempt in range(1, self._max_attempts + 1):
            await self._rate_limit()
            try:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                )
            except httpx.TransportError:
                if attempt >= self._max_attempts:
                    raise
                await asyncio.sleep(self._retry_delay(attempt))
                continue

            if response.status_code not in _TRANSIENT_STATUS_CODES:
                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result

            if attempt < self._max_attempts:
                await asyncio.sleep(self._retry_delay(attempt, response))
                continue

            if response.status_code == 429:
                raise RateLimitError(
                    self.__class__.__name__,
                    self._retry_after_seconds(response),
                )
            response.raise_for_status()

        raise RuntimeError("unreachable")  # pragma: no cover

    def _retry_delay(self, attempt: int, response: httpx.Response | None = None) -> float:
        """Return bounded exponential delay, preferring Retry-After."""
        if response is not None:
            retry_after = self._retry_after_seconds(response)
            if retry_after is not None:
                return min(float(retry_after), self._retry_max_delay)
        exponential = self._retry_base_delay * (2.0 ** (attempt - 1))
        jitter = random.uniform(0, self._retry_jitter) if self._retry_jitter else 0.0
        return min(exponential + jitter, self._retry_max_delay)

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> int | None:
        """Parse Retry-After as delta seconds or an HTTP date."""
        value = response.headers.get("Retry-After")
        if not value:
            return None
        if value.isdigit():
            return max(0, int(value))
        try:
            retry_at = parsedate_to_datetime(value)
            date_header = response.headers.get("Date")
            now = parsedate_to_datetime(date_header) if date_header else datetime.now(UTC)
            return max(0, int((retry_at - now).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return None

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class HTMLAdapter(BaseAdapter):
    """Base for BeautifulSoup HTML scraping with rate limiting and jitter.

    The ``detail_delay`` parameter controls the rate limit for detail page
    fetches, which are called once per listing. A shorter delay is safe for
    portals that tolerate higher request rates on detail pages.
    """

    MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB
    DEFAULT_MAX_PAGES = 200

    def __init__(
        self,
        request_delay: float = 2.0,
        jitter: float = 1.0,
        detail_delay: float | None = None,
        *,
        max_attempts: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
        retry_jitter: float = 0.0,
    ) -> None:
        self._request_delay = request_delay
        self._jitter = jitter
        self._detail_delay = detail_delay if detail_delay is not None else request_delay
        self._max_attempts = max(1, max_attempts)
        self._retry_base_delay = max(0.0, retry_base_delay)
        self._retry_max_delay = max(self._retry_base_delay, retry_max_delay)
        self._retry_jitter = max(0.0, retry_jitter)
        self._last_request_time: float = 0.0
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Lazily create and return the httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
                headers={"User-Agent": "ijobs-scraper/0.1.0"},
            )
        return self._client

    async def _rate_limit(self, *, detail: bool = False) -> None:
        """Enforce delay + random jitter between requests.

        Args:
            detail: If True, use the shorter ``detail_delay`` instead
                of the standard ``request_delay``.
        """
        elapsed = time.monotonic() - self._last_request_time
        base = self._detail_delay if detail else self._request_delay
        delay = base + random.uniform(0, self._jitter)
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request_time = time.monotonic()

    async def _fetch_page(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        detail: bool = False,
    ) -> BeautifulSoup:
        """Fetch URL and return parsed BeautifulSoup document.

        Uses streaming to reject oversized responses before reading the
        full body into memory.

        Args:
            url: The URL to fetch.
            params: Optional query parameters.
            detail: If True, use the shorter ``detail_delay`` for rate
                limiting (used by ``fetch_detail`` calls).

        Raises:
            AdapterError: If the response body exceeds ``MAX_RESPONSE_SIZE``.
            RateLimitError: If the server returns HTTP 429.
        """
        body, encoding = await self._fetch_bytes(url, params=params, detail=detail)
        return BeautifulSoup(body.decode(encoding, errors="replace"), "lxml")

    async def _fetch_bytes(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        detail: bool = False,
    ) -> tuple[bytes, str]:
        """Fetch a bounded response body for HTML or binary document adapters."""
        client = await self._ensure_client()
        for attempt in range(1, self._max_attempts + 1):
            await self._rate_limit(detail=detail)
            try:
                async with client.stream("GET", url, params=params) as resp:
                    if resp.status_code in _TRANSIENT_STATUS_CODES:
                        if attempt < self._max_attempts:
                            await asyncio.sleep(self._retry_delay(attempt, resp))
                            continue
                        if resp.status_code == 429:
                            raise RateLimitError(
                                self.__class__.__name__,
                                APIAdapter._retry_after_seconds(resp),
                            )
                    resp.raise_for_status()
                    content_length = resp.headers.get("content-length")
                    if (
                        content_length
                        and content_length.isdigit()
                        and int(content_length) > self.MAX_RESPONSE_SIZE
                    ):
                        raise AdapterError(
                            self.__class__.__name__,
                            (
                                f"Response too large ({content_length} bytes, "
                                f"max {self.MAX_RESPONSE_SIZE})"
                            ),
                            retryable=False,
                        )
                    body = await resp.aread()
            except httpx.TransportError:
                if attempt >= self._max_attempts:
                    raise
                await asyncio.sleep(self._retry_delay(attempt))
                continue

            if len(body) > self.MAX_RESPONSE_SIZE:
                raise AdapterError(
                    self.__class__.__name__,
                    f"Response too large ({len(body)} bytes, max {self.MAX_RESPONSE_SIZE})",
                    retryable=False,
                )
            return body, resp.encoding or "utf-8"

        raise RuntimeError("unreachable")  # pragma: no cover

    def _retry_delay(self, attempt: int, response: httpx.Response | None = None) -> float:
        """Return bounded retry delay for transient HTML responses."""
        if response is not None:
            retry_after = APIAdapter._retry_after_seconds(response)
            if retry_after is not None:
                return min(float(retry_after), self._retry_max_delay)
        exponential = self._retry_base_delay * (2.0 ** (attempt - 1))
        jitter = random.uniform(0, self._retry_jitter) if self._retry_jitter else 0.0
        return min(exponential + jitter, self._retry_max_delay)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class BrowserAdapter(BaseAdapter):
    """Base for Playwright browser automation with navigation delays.

    Subclasses should set the following class attributes to enable the
    default ``fetch_detail`` and ``can_handle_url`` implementations:

    Attributes:
        _host_suffix: Domain suffix used for URL validation
            (e.g. ``"myworkdayjobs.com"``).
        _detail_selector: CSS selector for the job detail container.
        _detail_min_length: Minimum ``raw_html`` length to skip refetch.
    """

    _host_suffix: str = ""
    _detail_selector: str = ""
    _detail_min_length: int = 0

    def __init__(self, page_timeout: float = 30.0, nav_delay: float = 3.0) -> None:
        self._page_timeout = page_timeout
        self._nav_delay = nav_delay
        self._pw: Any = None
        self._browser: Any = None
        self._context: Any = None

    async def _launch_browser(self) -> Any:
        """Launch headless Playwright browser. Returns a Page instance."""
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise AdapterError(
                self.__class__.__name__,
                "playwright is required. Install with: pip install ijobs-scraper[browser]",
                retryable=False,
            ) from exc

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context()
        page: Any = await self._context.new_page()
        page.set_default_timeout(self._page_timeout * 1000)
        return page

    async def _navigate(self, page: Any, url: str) -> None:
        """Navigate to URL with delay between navigations."""
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(self._nav_delay)

    async def _close_browser(self) -> None:
        """Close browser and cleanup resources.

        Each resource is closed independently so that a failure in one
        step does not prevent the remaining resources from being cleaned
        up. Timeouts prevent hanging on unresponsive Playwright instances.
        """
        for name, resource, method_name in [
            ("context", self._context, "close"),
            ("browser", self._browser, "close"),
            ("playwright", self._pw, "stop"),
        ]:
            if resource is not None:
                try:
                    await asyncio.wait_for(
                        getattr(resource, method_name)(),
                        timeout=10.0,
                    )
                except TimeoutError:
                    logger.warning("Timeout closing %s", name)
                except Exception:
                    logger.warning("Failed to close %s", name, exc_info=True)
        self._context = None
        self._browser = None
        self._pw = None

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch the full job detail page via a separate Playwright session.

        Uses a standalone browser session (local variables only) so that
        the shared ``_pw``/``_browser``/``_context`` instance state used
        by ``fetch_listings`` is never touched. This prevents browser
        leaks when the engine calls ``fetch_detail`` during an active
        ``fetch_listings`` async-for loop.

        Subclasses typically do not need to override this method; instead,
        set the ``_host_suffix``, ``_detail_selector``, and
        ``_detail_min_length`` class attributes.

        Args:
            listing: The listing to enrich with full HTML content.
            config: Source configuration.

        Returns:
            The listing with ``raw_html`` populated from the detail page,
            or the original listing if detail fetching is not configured,
            not needed, or fails.
        """
        if not self._detail_selector or not self._host_suffix:
            return listing
        if listing.raw_html and len(listing.raw_html) > self._detail_min_length:
            return listing
        if not self._validate_url(listing.external_url, self._host_suffix):
            logger.warning(
                "Rejecting detail URL outside expected host: %s",
                listing.external_url,
            )
            return listing

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return listing

        pw: Any = None
        browser: Any = None
        context: Any = None
        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context()
            page: Any = await context.new_page()
            page.set_default_timeout(self._page_timeout * 1000)
            await page.goto(listing.external_url, wait_until="domcontentloaded")
            await asyncio.sleep(self._nav_delay)

            detail: Any = await page.query_selector(self._detail_selector)
            if detail:
                html: str = await detail.inner_html()
                return listing.model_copy(update={"raw_html": html})
            else:
                logger.warning(
                    "Detail element not found for %s (selector: %s)",
                    listing.external_url,
                    self._detail_selector,
                )
                return listing
        except Exception:
            logger.warning(
                "Failed to fetch detail for %s",
                listing.external_url,
                exc_info=True,
            )
            return listing
        finally:
            for name, resource, method in [
                ("context", context, "close"),
                ("browser", browser, "close"),
                ("playwright", pw, "stop"),
            ]:
                if resource is not None:
                    try:
                        await asyncio.wait_for(
                            getattr(resource, method)(),
                            timeout=10.0,
                        )
                    except Exception:
                        logger.debug("Cleanup failed for detail %s", name)

    def can_handle_url(self, url: str) -> bool:
        """Check if this adapter can handle the given URL.

        Uses the ``_host_suffix`` class attribute for domain matching.

        Args:
            url: The URL to check.

        Returns:
            True if the URL matches the adapter's expected host domain.
        """
        if not self._host_suffix:
            return False
        return self._validate_url(url, self._host_suffix) is not None
