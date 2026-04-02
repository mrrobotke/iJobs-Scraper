"""World Vision Kenya browser adapter.

World Vision uses a Rails application with Hotwire Turbo for enhanced
navigation. The job listing pages use Turbo Frames for pagination,
requiring browser rendering to access the full content.

Example::

    source = SourceConfig(
        name="World Vision",
        slug="world-vision",
        adapter="world_vision",
        source_type=SourceType.BROWSER,
        base_url="https://careers.wvi.org",
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
_JOB_CARD_SELECTOR = (
    "a.job-listing, .job-card a, "
    ".opportunity a[href*='/careers/'], "
    "a[href*='/job/'], a[href*='/jobs/']"
)
_NEXT_LINK_SELECTOR = "a[rel='next'], .pagination a.next, .pagination li.next a"


@AdapterRegistry.register("world_vision")
class WorldVisionAdapter(BrowserAdapter):
    """Scrapes jobs from World Vision Kenya careers.

    World Vision uses Rails with Hotwire Turbo for page navigation.
    Turbo Frames handle pagination without full page reloads, which
    requires Playwright to interact with the dynamic content.
    """

    _host_suffix = "wvi.org"
    _detail_selector = ".job-description, .job-detail, article, main"
    _detail_min_length = 200

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from World Vision careers.

        Navigates to the careers page, extracts job cards from
        the Turbo-enhanced DOM, and paginates through results.

        Args:
            config: Source configuration with ``base_url`` pointing to
                the World Vision careers domain.

        Yields:
            A ``RawListing`` for each job card found.
        """
        base = config.base_url.rstrip("/")
        location_filter = config.config.get("location", "Kenya")
        url = f"{base}/jobs?location={location_filter}"
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
                        if not href:
                            continue

                        external_url = urljoin(base + "/", href)
                        external_url = self._validate_url(external_url, self._host_suffix) or ""
                        if not external_url:
                            continue

                        # Extract title
                        title_el = await card.query_selector("h2, h3, .job-title, .title")
                        if title_el:
                            title = await title_el.text_content()
                        else:
                            title = await card.text_content()

                        if not title or not title.strip():
                            continue
                        title = title.strip()

                        # Try to extract location
                        location = None
                        loc_el = await card.query_selector(".location, .job-location")
                        if loc_el:
                            loc_text = await loc_el.text_content()
                            if loc_text and loc_text.strip():
                                location = loc_text.strip()

                        from html import escape as html_escape

                        raw_html_parts = [f"<h1>{html_escape(title)}</h1>"]
                        if location:
                            raw_html_parts.append(f"<p>{html_escape(location)}</p>")

                        yield RawListing(
                            external_url=external_url,
                            title=title,
                            raw_html="\n".join(raw_html_parts),
                            company_name=config.name,
                        )
                    except Exception:
                        logger.warning(
                            "Skipping malformed World Vision listing on page %d",
                            page_num,
                            exc_info=True,
                        )
                        continue

                # Try Turbo-enhanced pagination
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
