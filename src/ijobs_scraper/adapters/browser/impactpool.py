"""Impactpool Kenya browser adapter.

Impactpool is a Rails application using Stimulus controllers for
interactivity. The job listing pages use JavaScript-enhanced content
that requires browser rendering. The adapter navigates to the Kenya
jobs page and extracts listings from the rendered DOM.

Example::

    source = SourceConfig(
        name="Impactpool",
        slug="impactpool",
        adapter="impactpool",
        source_type=SourceType.BROWSER,
        base_url="https://www.impactpool.org",
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import BrowserAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_DEFAULT_MAX_PAGES = 50
_JOB_CARD_SELECTOR = "a.job-listing, .job-card a, .search-result a[href*='/jobs/']"
_NEXT_LINK_SELECTOR = "a[rel='next'], .pagination a.next, .pagination li.next a"


@AdapterRegistry.register("impactpool")
class ImpactpoolAdapter(BrowserAdapter):
    """Scrapes jobs from Impactpool Kenya.

    Impactpool is a Rails application with Stimulus controllers that
    enhance the job listing pages with JavaScript. The adapter uses
    Playwright to render the pages and extract job data.
    """

    _host_suffix = "impactpool.org"
    _detail_selector = ".job-detail, .job-description, article, main"
    _detail_min_length = 0

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from Impactpool.

        Navigates to the Kenya jobs page, extracts job cards from
        the rendered HTML, and paginates through results.

        Args:
            config: Source configuration with ``base_url`` pointing to
                the Impactpool domain.

        Yields:
            A ``RawListing`` for each job card found.
        """
        base = config.base_url.rstrip("/")
        country_filter = config.config.get("country", "kenya")
        url = f"{base}/jobs?country={country_filter}"
        max_pages = int(config.config.get("max_pages", _DEFAULT_MAX_PAGES))

        try:
            page: Any = await self._launch_browser()
            await self._navigate(page, url)

            for page_num in range(1, max_pages + 1):
                # Wait for job listing content to render
                try:
                    await page.wait_for_selector(
                        _JOB_CARD_SELECTOR,
                        timeout=self._page_timeout * 1000,
                    )
                except Exception as exc:
                    if page_num == 1:
                        logger.warning(
                            "No job cards found on first page for %s: %s",
                            config.slug,
                            exc,
                        )
                    else:
                        logger.debug(
                            "No more job cards on page %d for %s: %s",
                            page_num,
                            config.slug,
                            exc,
                        )
                    break

                cards = await page.query_selector_all(_JOB_CARD_SELECTOR)
                if not cards:
                    break

                for card in cards:
                    try:
                        href = await card.get_attribute("href")
                        if not href or "/jobs/" not in href:
                            continue

                        external_url = urljoin(base + "/", href)
                        external_url = self._validate_url(external_url, self._host_suffix) or ""
                        if not external_url:
                            continue

                        # Extract title from link text or nested heading
                        title_el = await card.query_selector("h2, h3, .job-title, .title")
                        if title_el:
                            title = await title_el.text_content()
                        else:
                            title = await card.text_content()

                        if not title or not title.strip():
                            continue
                        title = title.strip()

                        # Try to extract organization name
                        org = config.name
                        org_el = await card.query_selector(".organization, .company, .employer")
                        if org_el:
                            org_text = await org_el.text_content()
                            if org_text and org_text.strip():
                                org = org_text.strip()

                        yield RawListing(
                            external_url=external_url,
                            title=title,
                            company_name=org,
                        )
                    except Exception:
                        logger.warning(
                            "Skipping malformed Impactpool listing on page %d",
                            page_num,
                            exc_info=True,
                        )
                        continue

                # Try to navigate to next page
                next_link = await page.query_selector(_NEXT_LINK_SELECTOR)
                if next_link is None:
                    break

                await next_link.click()
                try:
                    await page.wait_for_selector(
                        _JOB_CARD_SELECTOR,
                        timeout=self._page_timeout * 1000,
                    )
                except Exception as exc:
                    logger.debug(
                        "Pagination ended on page %d for %s: %s",
                        page_num,
                        config.slug,
                        exc,
                    )
                    break
        finally:
            await self._close_browser()
