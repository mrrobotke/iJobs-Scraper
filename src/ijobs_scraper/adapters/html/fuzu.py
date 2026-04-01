"""Fuzu Kenya HTML adapter.

Fuzu is a Ruby on Rails job platform that serves server-rendered HTML.
All ``/api/`` routes return 403, so HTML scraping is required.

Example::

    source = SourceConfig(
        name="Fuzu Kenya",
        slug="fuzu",
        adapter="fuzu",
        source_type=SourceType.HTML,
        base_url="https://www.fuzu.com",
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
_HOST = "fuzu.com"


@AdapterRegistry.register("fuzu")
class FuzuAdapter(HTMLAdapter):
    """Scrapes jobs from Fuzu Kenya.

    Fuzu is a Rails app with server-rendered HTML. Job cards are in a
    ``.job-listings`` container with ``?page=N`` pagination. All
    ``/api/`` routes return 403 so only HTML scraping works.
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from Fuzu Kenya.

        Paginates through ``?page=N`` URL parameters, extracting job
        cards from the listings page.

        Args:
            config: Source configuration with ``base_url`` pointing to
                the Fuzu domain.

        Yields:
            A ``RawListing`` for each job card found.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}/kenya/jobs"
        page = 1

        while page <= MAX_PAGES:
            params = {"page": str(page)} if page > 1 else None
            soup = await self._fetch_page(url, params=params)

            cards = soup.select(".job-card")
            if not cards:
                break

            for card in cards:
                try:
                    link = card.select_one(".job-card__link")
                    if link is None:
                        logger.debug("Skipping card with no link on page %d", page)
                        continue

                    title_el = card.select_one(".job-card__title")
                    title = title_el.get_text(strip=True) if title_el else None

                    href = link.get("href", "")
                    external_url = urljoin(base, str(href)) if href else ""
                    external_url = self._validate_url(external_url, _HOST) or ""

                    if not external_url:
                        logger.debug("Skipping listing with no URL on page %d", page)
                        continue

                    company_el = card.select_one(".job-card__company")
                    company = company_el.get_text(strip=True) if company_el else config.name

                    job_id = card.get("data-id")
                    external_id = str(job_id) if job_id else None

                    yield RawListing(
                        external_id=external_id,
                        external_url=external_url,
                        title=title,
                        company_name=company,
                    )
                except Exception:
                    logger.warning(
                        "Skipping malformed Fuzu listing on page %d",
                        page,
                        exc_info=True,
                    )
                    continue

            # Check for next page
            next_link = soup.select_one(".pagination__next[rel='next']")
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
        detail = soup.select_one(".job-detail")
        html = str(detail) if detail else str(soup)

        return listing.model_copy(update={"raw_html": html})

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to Fuzu.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains the Fuzu domain.
        """
        return _HOST in url
