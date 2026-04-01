"""Base adapter classes for job portal sources.

Provides APIAdapter (httpx), HTMLAdapter (BeautifulSoup), and
BrowserAdapter (Playwright) with built-in rate limiting.
"""

from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx
from bs4 import BeautifulSoup

from ijobs_scraper.exceptions import AdapterError, RateLimitError
from ijobs_scraper.models import RawListing, SourceConfig

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


class APIAdapter(BaseAdapter):
    """Base for REST API sources. Provides httpx client with rate limiting."""

    def __init__(self, request_delay: float = 1.0) -> None:
        self._request_delay = request_delay
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
        """HTTP GET with rate limiting. Raises RateLimitError on 429."""
        await self._rate_limit()
        client = await self._ensure_client()
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(
                self.__class__.__name__,
                int(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    async def _post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """HTTP POST with rate limiting. Raises RateLimitError on 429."""
        await self._rate_limit()
        client = await self._ensure_client()
        resp = await client.post(url, json=json, headers=headers)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(
                self.__class__.__name__,
                int(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class HTMLAdapter(BaseAdapter):
    """Base for BeautifulSoup HTML scraping with rate limiting and jitter."""

    def __init__(self, request_delay: float = 2.0, jitter: float = 1.0) -> None:
        self._request_delay = request_delay
        self._jitter = jitter
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

    async def _rate_limit(self) -> None:
        """Enforce delay + random jitter between requests."""
        elapsed = time.monotonic() - self._last_request_time
        delay = self._request_delay + random.uniform(0, self._jitter)
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request_time = time.monotonic()

    async def _fetch_page(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> BeautifulSoup:
        """Fetch URL and return parsed BeautifulSoup document."""
        await self._rate_limit()
        client = await self._ensure_client()
        resp = await client.get(url, params=params)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(
                self.__class__.__name__,
                int(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class BrowserAdapter(BaseAdapter):
    """Base for Playwright browser automation with navigation delays."""

    def __init__(self, page_timeout: float = 30.0, nav_delay: float = 3.0) -> None:
        self._page_timeout = page_timeout
        self._nav_delay = nav_delay
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

        pw = await async_playwright().start()
        self._browser = await pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context()
        page: Any = await self._context.new_page()
        page.set_default_timeout(self._page_timeout * 1000)
        return page

    async def _navigate(self, page: Any, url: str) -> None:
        """Navigate to URL with delay between navigations."""
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(self._nav_delay)

    async def _close_browser(self) -> None:
        """Close browser and cleanup resources."""
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
