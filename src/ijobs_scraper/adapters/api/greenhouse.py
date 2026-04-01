"""Greenhouse Boards API adapter.

Reusable for any employer using Greenhouse as their ATS.
Configure with ``board_token`` in ``SourceConfig.config``.

Example::

    source = SourceConfig(
        name="One Acre Fund",
        slug="one-acre-fund",
        adapter="greenhouse",
        source_type=SourceType.API,
        base_url="https://boards-api.greenhouse.io",
        config={"board_token": "oneacrefund"},
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


BOARDS_API = "https://boards-api.greenhouse.io/v1/boards"


@AdapterRegistry.register("greenhouse")
class GreenhouseAdapter(APIAdapter):
    """Scrapes jobs from any Greenhouse-powered career board.

    Greenhouse exposes a public boards API that returns JSON job listings.
    Each employer has a unique ``board_token`` (e.g. ``"oneacrefund"``).

    Config keys:
        board_token: The employer's Greenhouse board token (required).
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch all job listings from a Greenhouse board.

        Args:
            config: Source configuration. Must include ``config["board_token"]``.

        Yields:
            A ``RawListing`` for each job on the board.
        """
        board_token = self._require_config(config, "board_token")
        url = f"{BOARDS_API}/{board_token}/jobs"

        data: dict[str, Any] = await self._get(url, params={"content": "true"})

        for job in data.get("jobs", []):
            yield RawListing(
                external_id=str(job["id"]),
                external_url=job["absolute_url"],
                title=job.get("title"),
                raw_json=job,
                company_name=config.name,
            )

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch full job details from the Greenhouse API.

        If the listing already has ``raw_json`` with a ``"content"`` key,
        it is returned as-is (the list endpoint with ``content=true``
        already provides full details).

        Args:
            listing: The listing to enrich with full details.
            config: Source configuration with ``board_token``.

        Returns:
            The listing with ``raw_json`` populated with full job data.
        """
        if listing.raw_json and "content" in listing.raw_json:
            logger.debug("Detail already present for %s", listing.external_url)
            return listing

        board_token = self._require_config(config, "board_token")
        if listing.external_id is None:
            logger.debug(
                "Cannot fetch detail: no external_id for %s",
                listing.external_url,
            )
            return listing

        url = f"{BOARDS_API}/{board_token}/jobs/{listing.external_id}"
        data: dict[str, Any] = await self._get(url)

        return listing.model_copy(
            update={
                "raw_json": data,
                "title": data.get("title", listing.title),
            }
        )

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to a Greenhouse career board.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains a Greenhouse domain.
        """
        return "greenhouse.io" in url or "boards-api.greenhouse.io" in url
