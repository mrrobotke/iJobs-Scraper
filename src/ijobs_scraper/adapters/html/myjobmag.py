"""MyJobMag Kenya HTML adapter.

MyJobMag is a PHP-based job board with Cloudflare headers.
Straightforward HTML scraping with URL-based pagination.

Example::

    source = SourceConfig(
        name="MyJobMag Kenya",
        slug="myjobmag",
        adapter="myjobmag",
        source_type=SourceType.HTML,
        base_url="https://www.myjobmag.co.ke",
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import Tag

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import HTMLAdapter
from ijobs_scraper.application_destination import is_safe_application_destination
from ijobs_scraper.exceptions import RateLimitError
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 200
MAX_APPLICATION_REDIRECTS = 3
_HOST = "myjobmag.co.ke"


@AdapterRegistry.register("myjobmag")
class MyJobMagAdapter(HTMLAdapter):
    """Scrapes jobs from MyJobMag Kenya.

    MyJobMag is a PHP site with Cloudflare headers. Job listings are
    rendered as ``<li>`` elements within a ``.job-list__items`` container,
    with URL-based pagination via ``?page=N``.
    """

    async def _resolve_application_url(
        self,
        detail: Tag | None,
        *,
        listing_url: str,
    ) -> str | None:
        """Resolve MyJobMag's internal apply redirect without visiting its target.

        MyJobMag hides the employer's precise application destination behind an
        internal ``/apply-now/<id>`` redirect. Request only that same-origin URL with
        redirect following disabled, then validate the ``Location`` header before
        exposing it as a candidate-facing destination.
        """
        if detail is None:
            return None

        link = detail.select_one('a[href*="/apply-now/"]')
        if link is None:
            return None

        href = str(link.get("href", "")).strip()
        redirect_url = urljoin(listing_url, href)
        if not self._validate_url(redirect_url, _HOST):
            logger.warning("Rejecting application redirect outside MyJobMag: %s", redirect_url)
            return None

        client = await self._ensure_client()
        current_url = redirect_url
        for _ in range(MAX_APPLICATION_REDIRECTS):
            await self._rate_limit(detail=True)
            response = await client.get(current_url, follow_redirects=False)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise RateLimitError(
                    self.__class__.__name__,
                    int(retry_after) if retry_after and retry_after.isdigit() else None,
                )
            if response.status_code not in {301, 302, 303, 307, 308}:
                logger.warning(
                    "MyJobMag application endpoint returned %d for %s",
                    response.status_code,
                    current_url,
                )
                return None

            location = response.headers.get("Location")
            if not isinstance(location, str) or not location:
                return None

            candidate_url = urljoin(current_url, location)
            if is_safe_application_destination(candidate_url, source_url=listing_url):
                return candidate_url

            # MyJobMag may first canonicalise its own hostname before exposing the
            # employer target. Follow only another same-origin /apply-now/ hop.
            if not self._validate_url(candidate_url, _HOST):
                logger.warning("Rejecting unsafe MyJobMag application target: %s", candidate_url)
                return None
            if not urlsplit(candidate_url).path.startswith("/apply-now/"):
                logger.warning(
                    "Rejecting non-application MyJobMag redirect target: %s",
                    candidate_url,
                )
                return None
            current_url = candidate_url

        logger.warning(
            "MyJobMag application redirect exceeded %d same-source hops for %s",
            MAX_APPLICATION_REDIRECTS,
            redirect_url,
        )
        return None

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from MyJobMag Kenya.

        Paginates through ``?page=N`` URL parameters, extracting job
        entries from the list page.

        Args:
            config: Source configuration with ``base_url`` pointing to
                the MyJobMag domain.

        Yields:
            A ``RawListing`` for each job entry found.
        """
        base = config.base_url.rstrip("/")
        url = f"{base}/jobs"
        max_pages = int(config.config.get("max_pages", DEFAULT_MAX_PAGES))
        page = 1

        while page <= max_pages:
            params = {"page": str(page)} if page > 1 else None
            soup = await self._fetch_page(url, params=params)

            # Primary: .job-item links; fallback: anchor links to /job/ slugs
            item_list = list(soup.select(".job-item a[href*='/job/']"))
            if not item_list:
                item_list = [
                    a
                    for a in soup.select('a[href*="/job/"]')
                    if a.get_text(strip=True)
                    and len(str(a.get("href", ""))) > 5  # has slug after /job/
                ]
            items = item_list
            if not items:
                break

            for title_el in items:
                try:
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    external_url = urljoin(base, str(href)) if href else ""
                    external_url = self._validate_url(external_url, _HOST) or ""

                    if not external_url:
                        logger.debug("Skipping listing with no URL on page %d", page)
                        continue

                    company = config.name

                    yield RawListing(
                        external_url=external_url,
                        title=title,
                        company_name=company,
                    )
                except Exception:
                    logger.warning(
                        "Skipping malformed MyJobMag listing on page %d",
                        page,
                        exc_info=True,
                    )
                    continue

            # Check for next page
            next_link = soup.select_one(".pagination__next")
            if next_link is None:
                break

            page += 1

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch the full job detail page and populate ``raw_html``.

        Args:
            listing: The listing to enrich with full HTML content.
            config: Source configuration.

        Returns:
            The listing with ``raw_html`` populated from the detail page.
        """
        if listing.raw_html:
            logger.debug("Detail already present for %s", listing.external_url)
            return listing

        if not self._validate_url(listing.external_url, _HOST):
            logger.warning("Rejecting detail URL outside expected host: %s", listing.external_url)
            return listing

        soup = await self._fetch_page(listing.external_url, detail=True)
        detail = soup.select_one(".job-detail")
        html = str(detail) if detail else str(soup.body or soup)

        application_url = None
        try:
            application_url = await self._resolve_application_url(
                detail,
                listing_url=listing.external_url,
            )
        except httpx.HTTPError:
            logger.warning(
                "Unable to resolve MyJobMag application redirect for %s",
                listing.external_url,
                exc_info=True,
            )

        return listing.model_copy(update={"raw_html": html, "application_url": application_url})

    def can_handle_url(self, url: str) -> bool:
        """Check if this URL belongs to MyJobMag Kenya.

        Args:
            url: The URL to check.

        Returns:
            True if the URL contains the MyJobMag domain.
        """
        return self._validate_url(url, _HOST) is not None
