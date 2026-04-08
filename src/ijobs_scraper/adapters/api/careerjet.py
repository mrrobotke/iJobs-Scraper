"""Careerjet v4 API adapter.

Careerjet is a job search aggregator that indexes 60+ job sites.
Uses the v4 search API with Basic Auth.

Example::

    source = SourceConfig(
        name="Careerjet Kenya",
        slug="careerjet-kenya",
        adapter="careerjet",
        source_type=SourceType.API,
        base_url="https://www.careerjet.co.ke",
        config={"api_key": "your_publisher_api_key", "location": "Kenya"},
    )
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Any

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

CAREERJET_API_URL = "https://search.api.careerjet.net/v4/query"
DEFAULT_PAGESIZE = 20  # API ignores page_size param; always returns 20
DEFAULT_LOCATION = "Kenya"
DEFAULT_LOCALE = "en_GB"
MAX_PAGES = 10  # Results repeat after page 10


@AdapterRegistry.register("careerjet")
class CareerjetAdapter(APIAdapter):
    """Scrapes jobs from Careerjet using the v4 search API.

    Careerjet indexes 60+ job sites and provides a unified search API.
    Uses httpx via the base class ``_get()`` method for async requests.

    Config keys:
        api_key: Careerjet Publisher API key (required).
        keywords: Search keywords (optional, default ``""``).
        location: Location filter (optional, default ``"Kenya"``).
        locale: API locale code (optional, default ``"en_GB"``).
        user_ip: Client IP for API requests (required).
    """

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from Careerjet via the v4 API.

        Args:
            config: Source configuration. Must include ``config["api_key"]``.

        Yields:
            A ``RawListing`` for each job returned by the search.

        Raises:
            AdapterError: If the Careerjet API returns an error response.
        """
        api_key = self._require_config(config, "api_key")
        keywords: str = config.config.get("keywords", "")
        location: str = config.config.get("location", DEFAULT_LOCATION)
        locale: str = config.config.get("locale", DEFAULT_LOCALE)

        user_ip: str | None = config.config.get("user_ip")
        if not user_ip:
            raise AdapterError(
                "careerjet",
                "Careerjet adapter requires 'user_ip' in source config",
                retryable=False,
            )

        credentials = base64.b64encode(f"{api_key}:".encode()).decode()
        auth_headers: dict[str, str] = {
            "Authorization": f"Basic {credentials}",
            "Referer": config.base_url,
        }

        page = 1

        while True:
            search_params: dict[str, Any] = {
                "keywords": keywords,
                "location": location,
                "page": page,
                "user_ip": user_ip,
                "user_agent": "ijobs-scraper/0.1.0",
                "locale_code": locale,
            }

            result: dict[str, Any] = await self._get(
                CAREERJET_API_URL, params=search_params, headers=auth_headers
            )

            if result.get("type") == "ERROR":
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
            if page >= MAX_PAGES:
                logger.warning(
                    "Reached MAX_PAGES (%d) for source %s — results may be truncated",
                    MAX_PAGES,
                    config.slug,
                )
                break
            page += 1

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to Careerjet.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains a Careerjet domain.
        """
        return "careerjet.co.ke" in url or "careerjet.com" in url
