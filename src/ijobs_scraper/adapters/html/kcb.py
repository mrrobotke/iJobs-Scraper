"""KCB Bank careers page adapter.

KCB Group has a custom PHP 7.4 careers module with no JSON endpoints.
Listings are rendered as career cards with title, location, and deadline.

Example::

    source = SourceConfig(
        name="KCB Bank",
        slug="kcb",
        adapter="kcb",
        source_type=SourceType.HTML,
        base_url="https://ke.kcbgroup.com",
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import HTMLAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

MAX_PAGES = 200
_HOST = "kcbgroup.com"


@AdapterRegistry.register("kcb")
class KCBAdapter(HTMLAdapter):
    """Scrapes jobs from KCB Bank Kenya careers page.

    KCB Group uses a custom PHP careers module. Job openings are
    rendered as ``.career-card`` elements under a ``.career-listings``
    container with optional ``?page=N`` pagination.
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch career listings from KCB Bank.

        Paginates through ``?page=N`` URL parameters, extracting career
        cards from the careers page.

        Args:
            config: Source configuration with ``base_url`` pointing to
                the KCB domain.

        Yields:
            A ``RawListing`` for each career card found.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}/about/careers"
        page = 1

        while page <= MAX_PAGES:
            params = {"page": str(page)} if page > 1 else None
            soup = await self._fetch_page(url, params=params)

            cards = soup.select(".career-card")
            if not cards:
                break

            for card in cards:
                try:
                    title_link = card.select_one(".career-card__title a")
                    if title_link is None:
                        logger.debug("Skipping card with no title link on page %d", page)
                        continue

                    title = title_link.get_text(strip=True)
                    href = title_link.get("href", "")
                    external_url = urljoin(base, str(href)) if href else ""
                    external_url = self._validate_url(external_url, _HOST) or ""

                    if not external_url:
                        logger.debug("Skipping listing with no URL on page %d", page)
                        continue

                    yield RawListing(
                        external_url=external_url,
                        title=title,
                        company_name=config.name,
                    )
                except Exception:
                    logger.warning(
                        "Skipping malformed KCB listing on page %d",
                        page,
                        exc_info=True,
                    )
                    continue

            # Check for next page
            next_link = soup.select_one(".next-page")
            if next_link is None:
                break

            page += 1

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch the full career detail page and populate ``raw_html``.

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
        detail = soup.select_one(".career-detail")
        html = str(detail) if detail else str(soup)

        return listing.model_copy(update={"raw_html": html})

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to KCB Group.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains the KCB domain.
        """
        return self._validate_url(url, _HOST) is not None
