"""SmartRecruiters public API adapter.

Reusable for any employer using SmartRecruiters as their ATS.
Configure with ``company_slug`` in ``SourceConfig.config``.

Example::

    source = SourceConfig(
        name="Amref Health Africa",
        slug="amref",
        adapter="smartrecruiters",
        source_type=SourceType.API,
        base_url="https://api.smartrecruiters.com",
        config={"company_slug": "AmrefHealthAfrica4"},
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


DEFAULT_LIMIT = 100


@AdapterRegistry.register("smartrecruiters")
class SmartRecruitersAdapter(APIAdapter):
    """Scrapes jobs from any SmartRecruiters-powered career board.

    SmartRecruiters exposes a public API that returns JSON job postings.
    Each employer has a unique ``company_slug`` (e.g. ``"AmrefHealthAfrica4"``).

    Config keys:
        company_slug: The employer's SmartRecruiters company identifier (required).
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch all job postings from a SmartRecruiters company.

        Paginates through all results using ``offset`` and ``limit``
        query parameters until all postings are retrieved.

        Args:
            config: Source configuration. Must include
                ``config["company_slug"]``.

        Yields:
            A ``RawListing`` for each posting.
        """
        company_slug: str = config.config["company_slug"]
        base = config.base_url.rstrip("/")
        url = f"{base}/v1/companies/{company_slug}/postings"
        offset = 0

        while True:
            data: dict[str, Any] = await self._get(
                url, params={"offset": offset, "limit": DEFAULT_LIMIT}
            )

            postings = data.get("content", [])
            total_found: int = data.get("totalFound", 0)

            for posting in postings:
                posting_id = str(posting["id"])
                external_url = f"https://jobs.smartrecruiters.com/{company_slug}/{posting_id}"

                yield RawListing(
                    external_id=posting_id,
                    external_url=external_url,
                    title=posting.get("name"),
                    raw_json=posting,
                    company_name=config.name,
                )

            offset += len(postings)
            if not postings or offset >= total_found:
                break

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch full posting details including the job description.

        If the listing already has ``raw_json`` with a ``"jobAd"`` key,
        it is returned as-is (detail already fetched).

        Args:
            listing: The listing to enrich with full details.
            config: Source configuration with ``company_slug``.

        Returns:
            The listing with ``raw_json`` populated with full posting data.
        """
        if listing.raw_json and "jobAd" in listing.raw_json:
            return listing

        if listing.external_id is None:
            return listing

        company_slug: str = config.config["company_slug"]
        base = config.base_url.rstrip("/")
        url = f"{base}/v1/companies/{company_slug}/postings/{listing.external_id}"
        data: dict[str, Any] = await self._get(url)

        return listing.model_copy(
            update={
                "raw_json": data,
                "title": data.get("name", listing.title),
            }
        )

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to a SmartRecruiters career page.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains a SmartRecruiters domain.
        """
        return "smartrecruiters.com" in url
