"""Workday Candidate Experience (CXS) JSON adapter.

The class remains in the historical ``adapters.browser`` module so existing
imports continue to work, but it no longer requires Playwright. Workday career
sites expose the same JSON endpoints used by their web application.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20
DEFAULT_MAX_PAGES = 50
_HOST_SUFFIX = "myworkdayjobs.com"


@AdapterRegistry.register("workday")
class WorkdayAdapter(APIAdapter):
    """Scrape any Workday career site through its CXS JSON endpoints.

    Required config keys:
        tenant: Workday tenant identifier, for example ``"absa"``.
        instance: Candidate site name, for example ``"ABSAcareersite"``.

    Optional config keys:
        applied_facets: Workday facet mapping, such as a Kenya
            ``locationCountry`` identifier.
        locale: Public career-page locale. Defaults to ``"en-US"``.
        page_size: Number of jobs requested per page. Defaults to 20.
        max_pages: Safety cap. Defaults to 50.
    """

    @staticmethod
    def _validated_path(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        if not value.startswith("/job/") or ".." in value or any(c in value for c in ("?", "#")):
            return None
        return value

    def _api_root(self, config: SourceConfig) -> str:
        tenant = self._require_config(config, "tenant")
        instance = self._require_config(config, "instance")
        return f"{config.base_url.rstrip('/')}/wday/cxs/{tenant}/{instance}"

    @staticmethod
    def _applied_facets(config: SourceConfig) -> dict[str, list[str]]:
        configured = config.config.get("applied_facets", {})
        if not isinstance(configured, dict):
            raise AdapterError(
                "workday",
                "Workday 'applied_facets' must be an object",
                retryable=False,
            )

        facets: dict[str, list[str]] = {}
        for key, value in configured.items():
            if not isinstance(key, str) or not isinstance(value, list):
                raise AdapterError(
                    "workday",
                    "Workday facet values must be arrays of strings",
                    retryable=False,
                )
            if not all(isinstance(item, str) for item in value):
                raise AdapterError(
                    "workday",
                    "Workday facet values must be arrays of strings",
                    retryable=False,
                )
            facets[key] = value
        return facets

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Yield all postings from the configured Workday candidate site."""
        instance = self._require_config(config, "instance")
        api_url = f"{self._api_root(config)}/jobs"
        locale = str(config.config.get("locale", "en-US"))
        page_size = max(1, min(int(config.config.get("page_size", DEFAULT_PAGE_SIZE)), 100))
        max_pages = max(1, int(config.config.get("max_pages", DEFAULT_MAX_PAGES)))
        applied_facets = self._applied_facets(config)
        offset = 0
        page = 0

        while page < max_pages:
            data = await self._post(
                api_url,
                json={
                    "appliedFacets": applied_facets,
                    "limit": page_size,
                    "offset": offset,
                    "searchText": str(config.config.get("search_text", "")),
                },
            )
            postings = data.get("jobPostings", [])
            if not isinstance(postings, list) or not postings:
                break

            for posting in postings:
                if not isinstance(posting, dict):
                    continue
                external_path = self._validated_path(posting.get("externalPath"))
                if external_path is None:
                    logger.debug("Skipping Workday posting without a valid externalPath")
                    continue

                bullet_fields = posting.get("bulletFields")
                external_id = None
                if isinstance(bullet_fields, list) and bullet_fields and bullet_fields[0]:
                    external_id = str(bullet_fields[0])

                yield RawListing(
                    external_id=external_id,
                    external_url=(
                        f"{config.base_url.rstrip('/')}/{locale}/{instance}{external_path}"
                    ),
                    title=str(posting["title"]) if posting.get("title") else None,
                    raw_json=posting,
                    company_name=config.name,
                )

            offset += len(postings)
            page += 1
            total = data.get("total")
            if isinstance(total, int) and offset >= total:
                break
            if len(postings) < page_size:
                break

        if (
            page >= max_pages
            and len(postings) >= page_size
            and not (isinstance(total, int) and offset >= total)
        ):
            logger.warning(
                "Reached MAX_PAGES (%d) for source %s — results may be truncated",
                max_pages,
                config.slug,
            )

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch the full job posting through the CXS detail endpoint."""
        if listing.raw_json and listing.raw_json.get("jobDescription"):
            return listing
        if not self._validate_url(listing.external_url, _HOST_SUFFIX):
            logger.warning(
                "Rejecting Workday detail URL outside expected host: %s",
                listing.external_url,
            )
            return listing

        external_path = None
        if listing.raw_json:
            external_path = self._validated_path(listing.raw_json.get("externalPath"))
        if external_path is None:
            return listing

        data = await self._get(f"{self._api_root(config)}{external_path}")
        posting_info = data.get("jobPostingInfo")
        if not isinstance(posting_info, dict):
            logger.warning(
                "Workday detail response missing jobPostingInfo for %s",
                listing.external_url,
            )
            return listing

        return listing.model_copy(
            update={
                "title": posting_info.get("title") or listing.title,
                "raw_html": posting_info.get("jobDescription"),
                "raw_json": posting_info,
            }
        )

    def can_handle_url(self, url: str) -> bool:
        """Return whether *url* belongs to a Workday candidate site."""
        return self._validate_url(url, _HOST_SUFFIX) is not None
