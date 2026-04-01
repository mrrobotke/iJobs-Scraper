"""BrighterMonday Kenya HTML adapter.

BrighterMonday is a Laravel-based job board with Cloudflare protection
and CSRF tokens. The adapter extracts CSRF tokens from ``<meta>`` tags
and maintains session cookies across paginated requests.

Example::

    source = SourceConfig(
        name="BrighterMonday",
        slug="brightermonday",
        adapter="brightermonday",
        source_type=SourceType.HTML,
        base_url="https://www.brightermonday.co.ke",
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import HTMLAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

MAX_PAGES = 200
_HOST = "brightermonday.co.ke"


@AdapterRegistry.register("brightermonday")
class BrighterMondayAdapter(HTMLAdapter):
    """Scrapes jobs from BrighterMonday Kenya.

    BrighterMonday uses Laravel with CSRF protection. The adapter
    extracts CSRF tokens from ``<meta name="csrf-token">`` tags and
    maintains session cookies across paginated requests via the shared
    httpx client.
    """

    def __init__(self, request_delay: float = 2.0, jitter: float = 1.0) -> None:
        super().__init__(request_delay=request_delay, jitter=jitter)
        self._csrf_token: str | None = None

    @staticmethod
    def _extract_csrf_token(soup: BeautifulSoup) -> str | None:
        """Extract CSRF token from a parsed page's meta tags.

        Args:
            soup: The parsed HTML page.

        Returns:
            The CSRF token string, or ``None`` if not found.
        """
        meta = soup.find("meta", attrs={"name": "csrf-token"})
        if meta:
            content = meta.get("content")
            if content and isinstance(content, str):
                return content
        return None

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from BrighterMonday Kenya.

        Paginates through ``?page=N`` URL parameters, extracting job
        cards from the search results page. CSRF tokens are extracted
        from the first page and maintained via session cookies.

        Args:
            config: Source configuration with ``base_url`` pointing to
                the BrighterMonday domain.

        Yields:
            A ``RawListing`` for each job card found.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}/jobs"

        page = 1
        while page <= MAX_PAGES:
            params = {"page": str(page)} if page > 1 else None
            soup = await self._fetch_page(url, params=params)

            # Extract CSRF token from the first page response
            if page == 1:
                self._csrf_token = self._extract_csrf_token(soup)
                if self._csrf_token:
                    logger.debug("Session initialized for %s", config.slug)

            cards = soup.select('a[data-cy="listing-title-link"]')
            if not cards:
                # Fallback for older layouts
                cards = soup.select(".job-card .job-card__title a")
            if not cards:
                break

            for title_link in cards:
                try:
                    title = title_link.get_text(strip=True)
                    href = title_link.get("href", "")
                    external_url = urljoin(base, str(href)) if href else ""
                    external_url = self._validate_url(external_url, _HOST) or ""

                    if not external_url:
                        logger.debug(
                            "Skipping listing with no valid URL on page %d",
                            page,
                        )
                        continue

                    # Find nearest sibling company link to this title
                    company = config.name
                    sibling = title_link.find_next("a", attrs={"data-cy": "listing-company-link"})
                    if sibling is None:
                        sibling = title_link.find_next("a", href=lambda h: h and "/company/" in h)
                    if sibling:
                        company = sibling.get_text(strip=True) or config.name

                    yield RawListing(
                        external_url=external_url,
                        title=title,
                        company_name=company,
                    )
                except Exception:
                    logger.warning(
                        "Skipping malformed BrighterMonday listing on page %d",
                        page,
                        exc_info=True,
                    )
                    continue

            # Check for next page
            next_link = soup.select_one("a[rel='next']")
            if next_link is None:
                break

            page += 1

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch the full job detail page and populate ``raw_html``.

        Args:
            listing: The listing to enrich with full HTML content.
            config: Source configuration.

        Returns:
            The listing with ``raw_html`` populated from the detail page.
        """
        if listing.raw_html:
            logger.debug("Detail already present for %s", listing.external_url)
            return listing

        if not self._validate_url(listing.external_url, _HOST):
            logger.warning("Rejecting detail URL outside expected host: %s", listing.external_url)
            return listing

        soup = await self._fetch_page(listing.external_url)
        detail = soup.select_one(".job-details")
        html = str(detail) if detail else str(soup)

        return listing.model_copy(update={"raw_html": html})

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to BrighterMonday Kenya.

        Args:
            url: The URL to check.

        Returns:
            True if the URL matches the BrighterMonday domain.
        """
        return self._validate_url(url, _HOST) is not None
