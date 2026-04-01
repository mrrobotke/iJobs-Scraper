"""MyJobMag Kenya HTML adapter.

MyJobMag is a PHP-based job board with Cloudflare headers.
Straightforward HTML scraping with URL-based pagination.

Example::

    source = SourceConfig(
        name="MyJobMag Kenya",
        slug="myjobmag",
        adapter="myjobmag",
        source_type=SourceType.HTML,
        base_url="https://www.myjobmag.co.ke",
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


@AdapterRegistry.register("myjobmag")
class MyJobMagAdapter(HTMLAdapter):
    """Scrapes jobs from MyJobMag Kenya.

    MyJobMag is a PHP site with Cloudflare headers. Job listings are
    rendered as ``<li>`` elements within a ``.job-list__items`` container,
    with URL-based pagination via ``?page=N``.
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from MyJobMag Kenya.

        Paginates through ``?page=N`` URL parameters, extracting job
        entries from the list page.

        Args:
            config: Source configuration with ``base_url`` pointing to
                the MyJobMag domain.

        Yields:
            A ``RawListing`` for each job entry found.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}/jobs"
        page = 1

        while page <= MAX_PAGES:
            params = {"page": str(page)} if page > 1 else None
            soup = await self._fetch_page(url, params=params)

            items = soup.select(".job-list__item")
            if not items:
                break

            for item in items:
                try:
                    title_el = item.select_one(".job-info__title a")
                    if title_el is None:
                        logger.debug("Skipping entry with no title link on page %d", page)
                        continue

                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    external_url = urljoin(base, str(href)) if href else ""

                    if not external_url:
                        logger.debug("Skipping listing with no URL on page %d", page)
                        continue

                    company_el = item.select_one(".job-info__company")
                    company = company_el.get_text(strip=True) if company_el else config.name

                    yield RawListing(
                        external_url=external_url,
                        title=title,
                        company_name=company,
                    )
                except Exception:
                    logger.warning(
                        "Skipping malformed MyJobMag listing on page %d",
                        page,
                        exc_info=True,
                    )
                    continue

            # Check for next page
            next_link = soup.select_one(".pagination__next")
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

        soup = await self._fetch_page(listing.external_url)
        detail = soup.select_one(".job-detail")
        html = str(detail) if detail else str(soup)

        return listing.model_copy(update={"raw_html": html})

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to MyJobMag Kenya.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains the MyJobMag domain.
        """
        return "myjobmag.co.ke" in url
