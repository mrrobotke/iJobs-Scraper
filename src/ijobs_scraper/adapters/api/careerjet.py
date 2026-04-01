"""Careerjet API adapter via the official Python SDK.

Careerjet is a job search aggregator that indexes 60+ job sites.
Requires the ``careerjet-api`` optional dependency.

Install with: ``pip install ijobs-scraper[careerjet]``

Example::

    source = SourceConfig(
        name="Careerjet Kenya",
        slug="careerjet-kenya",
        adapter="careerjet",
        source_type=SourceType.API,
        base_url="https://www.careerjet.co.ke",
        config={"affid": "your_affiliate_id", "location": "Kenya"},
    )
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

DEFAULT_PAGESIZE = 99
DEFAULT_LOCATION = "Kenya"
DEFAULT_LOCALE = "en_KE"
MAX_PAGES = 200


@AdapterRegistry.register("careerjet")
class CareerjetAdapter(APIAdapter):
    """Scrapes jobs from Careerjet using the official Python SDK.

    Careerjet indexes 60+ job sites and provides a unified search API.
    The synchronous SDK calls are wrapped in ``asyncio.to_thread()``.

    Config keys:
        affid: Careerjet affiliate ID (required).
        keywords: Search keywords (optional, default ``""``).
        location: Location filter (optional, default ``"Kenya"``).
        locale: SDK locale code (optional, default ``"en_KE"``).
        user_ip: Client IP for API requests (optional, default ``"0.0.0.0"``).
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from Careerjet via the SDK.

        Args:
            config: Source configuration. Must include ``config["affid"]``.

        Yields:
            A ``RawListing`` for each job returned by the search.

        Raises:
            AdapterError: If ``careerjet-api`` is not installed.
        """
        try:
            from careerjet_api import CareerjetAPIClient  # type: ignore[import-untyped]
        except ImportError as exc:
            raise AdapterError(
                "careerjet",
                "careerjet-api is required. Install with: pip install ijobs-scraper[careerjet]",
                retryable=False,
            ) from exc

        affid = self._require_config(config, "affid")
        keywords: str = config.config.get("keywords", "")
        location: str = config.config.get("location", DEFAULT_LOCATION)
        locale: str = config.config.get("locale", DEFAULT_LOCALE)

        cj: Any = CareerjetAPIClient(locale)
        page = 1

        while True:
            search_params: dict[str, Any] = {
                "keywords": keywords,
                "location": location,
                "page": page,
                "pagesize": DEFAULT_PAGESIZE,
                "affid": affid,
                "user_ip": config.config.get("user_ip", "0.0.0.0"),
                "user_agent": "ijobs-scraper/0.1.0",
                "url": config.base_url,
            }

            result: dict[str, Any] = await asyncio.to_thread(cj.search, search_params)

            if result.get("type") == "error":
                raise AdapterError(
                    "careerjet",
                    f"Careerjet API error: {result.get('error', 'unknown')}",
                    retryable=True,
                )

            jobs: list[dict[str, Any]] = result.get("jobs", [])
            if not jobs:
                break

            for job in jobs:
                try:
                    external_url: str = job.get("url", "")
                    if not external_url:
                        logger.debug("Skipping Careerjet listing with no URL")
                        continue

                    yield RawListing(
                        external_id=None,
                        external_url=external_url,
                        title=job.get("title"),
                        raw_json=job,
                        company_name=config.name,
                    )
                except Exception:
                    logger.warning(
                        "Failed to parse Careerjet listing",
                        exc_info=True,
                    )
                    continue

            if len(jobs) < DEFAULT_PAGESIZE:
                break
            page += 1
            if page >= MAX_PAGES:
                logger.warning(
                    "Reached MAX_PAGES (%d) for source %s — results may be truncated",
                    MAX_PAGES,
                    config.slug,
                )
                break

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to Careerjet.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains a Careerjet domain.
        """
        return "careerjet.co.ke" in url or "careerjet.com" in url
