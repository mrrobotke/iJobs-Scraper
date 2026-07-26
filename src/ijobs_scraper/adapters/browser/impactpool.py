"""Impactpool server-rendered HTML adapter.

The module path remains stable for existing consumers, but the current
Impactpool search and detail pages do not require browser automation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import HTMLAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

DEFAULT_COUNTRY_ID = "115"
DEFAULT_MAX_PAGES = 50
_HOST_SUFFIX = "impactpool.org"


@AdapterRegistry.register("impactpool")
class ImpactpoolAdapter(HTMLAdapter):
    """Scrape Impactpool's server-rendered search results for Kenya."""

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Yield Impactpool job cards and follow its Show more pagination."""
        base = config.base_url.rstrip("/")
        url = f"{base}/search"
        country_id = str(config.config.get("country_id", DEFAULT_COUNTRY_ID))
        max_pages = max(1, int(config.config.get("max_pages", DEFAULT_MAX_PAGES)))
        seen_urls: set[str] = set()

        for page in range(1, max_pages + 1):
            soup = await self._fetch_page(
                url,
                params={
                    "wl[]": country_id,
                    "page": str(page),
                    "per_page": "40",
                },
            )
            cards = soup.select("main#job_list .job > a[href*='/jobs/']")
            if not cards:
                break

            for card in cards:
                href = card.get("href")
                if not isinstance(href, str):
                    continue
                external_url = urljoin(base + "/", href)
                if not self._validate_url(external_url, _HOST_SUFFIX):
                    continue
                if external_url in seen_urls:
                    continue

                title_element = card.select_one('[type="cardTitle"]')
                title = title_element.get_text(" ", strip=True) if title_element else ""
                if not title:
                    continue

                organization_element = card.select_one('[type="bodyEmphasis"]')
                company_name = (
                    organization_element.get_text(" ", strip=True)
                    if organization_element
                    else config.name
                )
                path_parts = [part for part in urlparse(external_url).path.split("/") if part]
                external_id = path_parts[-1] if path_parts else None
                seen_urls.add(external_url)

                yield RawListing(
                    external_id=external_id,
                    external_url=external_url,
                    title=title,
                    company_name=company_name or config.name,
                )

            more_link = soup.select_one("#search_results_more_button a[href]")
            if more_link is None:
                break
        else:
            logger.warning(
                "Reached MAX_PAGES (%d) for source %s — results may be truncated",
                max_pages,
                config.slug,
            )

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch the server-rendered Impactpool job description."""
        if listing.raw_html:
            return listing
        if not self._validate_url(listing.external_url, _HOST_SUFFIX):
            logger.warning(
                "Rejecting Impactpool detail URL outside expected host: %s",
                listing.external_url,
            )
            return listing

        soup = await self._fetch_page(listing.external_url, detail=True)
        detail = soup.select_one("#job-description")
        if detail is None:
            logger.warning("Impactpool detail container missing for %s", listing.external_url)
            return listing
        return listing.model_copy(update={"raw_html": str(detail)})

    def can_handle_url(self, url: str) -> bool:
        """Return whether *url* belongs to Impactpool."""
        return self._validate_url(url, _HOST_SUFFIX) is not None
