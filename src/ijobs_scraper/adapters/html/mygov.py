"""MyGov Kenya government job adverts adapter.

MyGov is the Kenyan government portal listing public sector vacancies
in an HTML table at ``/job-adverts``. Pagination is URL-based.

Example::

    source = SourceConfig(
        name="MyGov Kenya",
        slug="mygov",
        adapter="mygov",
        source_type=SourceType.HTML,
        base_url="https://www.mygov.go.ke",
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
_HOST = "mygov.go.ke"


@AdapterRegistry.register("mygov")
class MyGovAdapter(HTMLAdapter):
    """Scrapes government job adverts from MyGov Kenya.

    MyGov lists vacancies in an HTML table at ``/job-adverts``. Each row
    contains a title link, the hiring organization, and a deadline date.
    Pagination is via ``?page=N`` query parameters.
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job adverts from the MyGov Kenya portal.

        Paginates through ``?page=N`` URL parameters, extracting rows
        from the job adverts table.

        Args:
            config: Source configuration with ``base_url`` pointing to
                the MyGov domain.

        Yields:
            A ``RawListing`` for each table row found.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}/job-adverts"
        page = 1

        while page <= MAX_PAGES:
            params = {"page": str(page)} if page > 1 else None
            soup = await self._fetch_page(url, params=params)

            table = soup.select_one(".job-adverts-table")
            if table is None:
                break

            rows = table.select("tbody tr")
            if not rows:
                break

            for row in rows:
                try:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        logger.debug("Skipping row with fewer than 2 cells on page %d", page)
                        continue

                    link = cells[0].find("a")
                    if link is None:
                        logger.debug("Skipping row with no link on page %d", page)
                        continue

                    title = link.get_text(strip=True)
                    href = link.get("href", "")
                    external_url = urljoin(base, str(href)) if href else ""
                    external_url = self._validate_url(external_url, _HOST) or ""

                    if not external_url:
                        logger.debug("Skipping row with no URL on page %d", page)
                        continue

                    organization = cells[1].get_text(strip=True) if len(cells) > 1 else config.name

                    yield RawListing(
                        external_url=external_url,
                        title=title,
                        company_name=organization,
                    )
                except Exception:
                    logger.warning(
                        "Skipping malformed MyGov listing on page %d",
                        page,
                        exc_info=True,
                    )
                    continue

            # Check for next page
            next_link = soup.select_one(".pagination .next")
            if next_link is None:
                break

            page += 1

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch the full job advert detail page and populate ``raw_html``.

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
        detail = soup.select_one(".job-advert-detail")
        html = str(detail) if detail else str(soup)

        return listing.model_copy(update={"raw_html": html})

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to the MyGov Kenya portal.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains the MyGov domain.
        """
        return self._validate_url(url, _HOST) is not None
