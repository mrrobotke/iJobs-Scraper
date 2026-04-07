"""Kenya Airways iRec ATS API adapter.

Kenya Airways uses the iRec recruitment platform which exposes a public
REST API returning full JSON job data with no authentication required.

The API was migrated from ``/careers/api/v2`` to ``/api/Jobs`` in early
2026.  The new listing endpoint uses page-number based pagination
(``pageNumber`` / ``pageSize``) instead of offset/limit, and returns
results inside a ``data`` array with ``hasNext`` / ``hasPrevious``
pagination flags.

The ``base_url`` in :class:`SourceConfig` drives the API host so the
adapter can be pointed at staging or alternative environments.

Example::

    source = SourceConfig(
        name="Kenya Airways",
        slug="kenya-airways",
        adapter="kenya_airways",
        source_type=SourceType.API,
        base_url="https://api-irec-prod.kenya-airways.com",
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

API_PATH = "/api/Jobs"
DEFAULT_PAGE_SIZE = 50
MAX_PAGES = 200


@AdapterRegistry.register("kenya_airways")
class KenyaAirwaysAdapter(APIAdapter):
    """Scrapes jobs from Kenya Airways via the iRec REST API.

    The iRec platform provides a public JSON API with page-number
    pagination via ``pageNumber`` and ``pageSize`` query parameters.
    No authentication is required.  The endpoint is built from
    ``config.base_url`` so the adapter can target different
    environments.
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch all job listings from Kenya Airways iRec API.

        Args:
            config: Source configuration. ``base_url`` is the iRec API
                host (e.g. ``"https://api-irec-prod.kenya-airways.com"``).

        Yields:
            A ``RawListing`` for each open position.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}{API_PATH}/JobListing"
        page_number = 1
        page_size = DEFAULT_PAGE_SIZE

        while True:
            data: dict[str, Any] = await self._get(
                url, params={"pageNumber": page_number, "pageSize": page_size}
            )

            if "data" not in data:
                logger.warning(
                    "Kenya Airways API response missing 'data' key, keys: %s, source: %s",
                    list(data.keys()),
                    config.slug,
                )

            jobs: list[dict[str, Any]] = data.get("data", [])
            if not jobs:
                break

            for job in jobs:
                try:
                    external_id = str(job["id"]) if "id" in job else None
                    external_url = job.get("url") or job.get("absolute_url", "")
                    if not external_url and external_id:
                        external_url = f"https://careers.kenya-airways.com/jobs/{external_id}"

                    if not external_url:
                        logger.debug(
                            "Skipping listing with no URL: external_id=%s",
                            external_id,
                        )
                        continue

                    if not external_url.startswith(("https://", "http://")):
                        logger.debug("Rejected non-HTTP URL: %s", external_url)
                        continue

                    yield RawListing(
                        external_id=external_id,
                        external_url=external_url,
                        title=job.get("title"),
                        raw_json=job,
                        company_name=config.name,
                    )
                except Exception:
                    logger.warning(
                        "Skipping malformed Kenya Airways listing on page %d",
                        page_number,
                        exc_info=True,
                    )
                    continue

            if not data.get("hasNext", False):
                break
            page_number += 1
            if page_number > MAX_PAGES:
                logger.warning(
                    "Reached MAX_PAGES (%d) for source %s — results may be truncated",
                    MAX_PAGES,
                    config.slug,
                )
                break

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch full job details from the iRec API.

        If the listing already has ``raw_json`` with a ``"description"`` key,
        it is returned as-is.

        Args:
            listing: The listing to enrich with full details.
            config: Source configuration. ``base_url`` is the iRec API host.

        Returns:
            The listing with ``raw_json`` populated with full job data.
        """
        if listing.raw_json and "description" in listing.raw_json:
            logger.debug("Detail already present for %s", listing.external_url)
            return listing

        if listing.external_id is None:
            logger.debug(
                "Cannot fetch detail: no external_id for %s",
                listing.external_url,
            )
            return listing

        ext_id = listing.external_id
        if any(c in ext_id for c in ("\\", "/", "?", "#", "..")):
            logger.warning("Invalid external_id rejected: %s", ext_id)
            return listing

        base = config.base_url.rstrip("/")
        url = f"{base}{API_PATH}/{listing.external_id}"
        data: dict[str, Any] = await self._get(url)

        return listing.model_copy(
            update={
                "raw_json": data,
                "title": data.get("title", listing.title),
            }
        )

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to Kenya Airways careers.

        Args:
            url: The URL to check.

        Returns:
            True if the URL matches a Kenya Airways domain.
        """
        from urllib.parse import urlparse

        hostname = urlparse(url).hostname or ""
        return hostname == "kenya-airways.com" or hostname.endswith(".kenya-airways.com")
