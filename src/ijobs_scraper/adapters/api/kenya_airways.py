"""Kenya Airways iRec ATS API adapter.

Kenya Airways uses the iRec recruitment platform which exposes a public
REST API returning full JSON job data with no authentication required.

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

from typing import TYPE_CHECKING, Any

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


CAREERS_API = "https://api-irec-prod.kenya-airways.com/careers/api/v2"
DEFAULT_LIMIT = 50


@AdapterRegistry.register("kenya_airways")
class KenyaAirwaysAdapter(APIAdapter):
    """Scrapes jobs from Kenya Airways via the iRec REST API.

    The iRec platform provides a public JSON API with pagination support
    via ``offset`` and ``limit`` query parameters. No authentication
    is required.
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch all job listings from Kenya Airways iRec API.

        Args:
            config: Source configuration with ``base_url`` pointing to the
                iRec API host.

        Yields:
            A ``RawListing`` for each open position.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}/careers/api/v2/jobs"
        offset = 0
        limit = DEFAULT_LIMIT

        while True:
            data: dict[str, Any] = await self._get(url, params={"offset": offset, "limit": limit})

            jobs = data.get("jobs", [])
            if not jobs:
                break

            for job in jobs:
                external_id = str(job["id"]) if "id" in job else None
                external_url = job.get("url") or job.get("absolute_url", "")
                if not external_url and external_id:
                    external_url = f"https://careers.kenya-airways.com/jobs/{external_id}"

                yield RawListing(
                    external_id=external_id,
                    external_url=external_url,
                    title=job.get("title"),
                    raw_json=job,
                    company_name=config.name,
                )

            if len(jobs) < limit:
                break
            offset += limit

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch full job details from the iRec API.

        If the listing already has ``raw_json`` with a ``"description"`` key,
        it is returned as-is.

        Args:
            listing: The listing to enrich with full details.
            config: Source configuration.

        Returns:
            The listing with ``raw_json`` populated with full job data.
        """
        if listing.raw_json and "description" in listing.raw_json:
            return listing

        if listing.external_id is None:
            return listing

        base = config.base_url.rstrip("/")
        url = f"{base}/careers/api/v2/jobs/{listing.external_id}"
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
            True if the URL contains a Kenya Airways domain.
        """
        return "kenya-airways.com" in url
