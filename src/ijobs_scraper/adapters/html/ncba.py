"""NCBA Group official careers-page adapter."""

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

_HOST_SUFFIX = "ncbagroup.com"
_CARD_SELECTOR = ".vacancy-card, .job-card, .career-card, .job-listing"


@AdapterRegistry.register("ncba")
class NCBAAdapter(HTMLAdapter):
    """Scrape NCBA's current first-party careers surface.

    The official page sometimes contains no open positions. That is treated
    as a successful empty result instead of an adapter failure.
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Yield current vacancy cards when NCBA publishes them."""
        base = config.base_url.rstrip("/")
        soup = await self._fetch_page(f"{base}/careers/")
        for card in soup.select(_CARD_SELECTOR):
            link = card.select_one("h1 a[href], h2 a[href], h3 a[href], a[href]")
            if link is None:
                continue
            href = link.get("href")
            if not isinstance(href, str):
                continue
            external_url = urljoin(base + "/", href)
            if not self._validate_url(external_url, _HOST_SUFFIX):
                continue
            title = link.get_text(" ", strip=True)
            if not title:
                continue

            yield RawListing(
                external_url=external_url,
                title=title,
                company_name=config.name,
            )

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch a published NCBA vacancy page."""
        if listing.raw_html:
            return listing
        if not self._validate_url(listing.external_url, _HOST_SUFFIX):
            logger.warning(
                "Rejecting NCBA detail URL outside expected host: %s",
                listing.external_url,
            )
            return listing

        soup = await self._fetch_page(listing.external_url, detail=True)
        detail = soup.select_one(".job-detail, .vacancy-detail, article, main")
        if detail is None:
            return listing
        return listing.model_copy(update={"raw_html": str(detail)})

    def can_handle_url(self, url: str) -> bool:
        """Return whether *url* belongs to NCBA Group."""
        return self._validate_url(url, _HOST_SUFFIX) is not None
