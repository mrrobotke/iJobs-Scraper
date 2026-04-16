"""ReliefWeb API adapter for UN OCHA job listings.

ReliefWeb provides a public REST API for humanitarian job postings.
Requires an ``appname`` for API access registration.

Example::

    source = SourceConfig(
        name="ReliefWeb Kenya",
        slug="reliefweb-kenya",
        adapter="reliefweb",
        source_type=SourceType.API,
        base_url="https://api.reliefweb.int",
        config={"appname": "ijobs-scraper"},
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_PAGES = 200
REQUESTED_FIELDS = [
    "title",
    "body-html",
    "url",
    "source",
    "date.created",
    "date.closing",
    "country",
    "theme",
    "type",
]


@AdapterRegistry.register("reliefweb")
class ReliefWebAdapter(APIAdapter):
    """Scrapes jobs from the ReliefWeb API (api.reliefweb.int).

    ReliefWeb is the UN OCHA humanitarian information portal. The jobs
    API returns listings filtered by country with pagination via
    ``offset`` and ``limit`` parameters. The Kenya country filter is
    currently hardcoded in the query parameters.

    Config keys:
        appname: Registered application name for API access (required).
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from the ReliefWeb API.

        Args:
            config: Source configuration. Must include ``config["appname"]``.

        Yields:
            A ``RawListing`` for each job matching the Kenya filter.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}/v2/jobs"
        appname = self._require_config(config, "appname")
        offset = 0
        page = 0

        while True:
            params: dict[str, Any] = {
                "appname": appname,
                "filter[field]": "country",
                "filter[value][]": "Kenya",
                "limit": DEFAULT_LIMIT,
                "offset": offset,
                "fields[include][]": REQUESTED_FIELDS,
            }

            data: dict[str, Any] = await self._get(url, params=params)

            if "data" not in data:
                logger.warning(
                    "ReliefWeb response missing 'data' key, keys: %s, source: %s",
                    list(data.keys()),
                    config.slug,
                )

            items: list[dict[str, Any]] = data.get("data", [])
            if not items:
                break

            for item in items:
                try:
                    fields: dict[str, Any] = item.get("fields", {})
                    item_id = str(item.get("id", ""))

                    external_url: str = fields.get("url", "")
                    if not external_url and item_id:
                        external_url = f"https://reliefweb.int/job/{item_id}"
                    if not external_url:
                        logger.debug("Skipping listing with no URL: external_id=%s", item_id)
                        continue

                    sources: list[dict[str, Any]] = fields.get("source", [])
                    company = sources[0]["name"] if sources else config.name

                    yield RawListing(
                        external_id=item_id or None,
                        external_url=external_url,
                        title=fields.get("title"),
                        raw_html=fields.get("body-html"),
                        raw_json=item,
                        company_name=company,
                    )
                except Exception:
                    logger.warning(
                        "Failed to parse ReliefWeb listing %s",
                        item.get("id"),
                        exc_info=True,
                    )
                    continue

            total_count = int(data.get("totalCount", 0))
            offset += DEFAULT_LIMIT
            page += 1
            if offset >= total_count:
                break
            if page >= MAX_PAGES:
                logger.warning(
                    "Reached MAX_PAGES (%d) for source %s — results may be truncated",
                    MAX_PAGES,
                    config.slug,
                )
                break

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch full job details from the ReliefWeb API.

        If the listing already has ``raw_html`` content, it is returned
        as-is.

        Args:
            listing: The listing to enrich.
            config: Source configuration with ``appname``.

        Returns:
            The listing with full body HTML populated.
        """
        if listing.raw_html:
            logger.debug("Detail already present for %s", listing.external_url)
            return listing

        if listing.external_id is None:
            logger.debug(
                "Cannot fetch detail: no external_id for %s",
                listing.external_url,
            )
            return listing

        base = config.base_url.rstrip("/")
        url = f"{base}/v2/jobs/{listing.external_id}"
        appname = self._require_config(config, "appname")

        params: dict[str, Any] = {
            "appname": appname,
            "fields[include][]": REQUESTED_FIELDS,
        }
        data: dict[str, Any] = await self._get(url, params=params)

        items: list[dict[str, Any]] = data.get("data", [])
        if not items:
            logger.warning(
                "ReliefWeb returned no data for job %s",
                listing.external_id,
            )
            return listing

        fields: dict[str, Any] = items[0].get("fields", {})
        return listing.model_copy(
            update={
                "raw_html": fields.get("body-html", listing.raw_html),
                "raw_json": items[0],
                "title": fields.get("title", listing.title),
            }
        )

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to ReliefWeb.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains the ReliefWeb domain.
        """
        return "reliefweb.int" in url
