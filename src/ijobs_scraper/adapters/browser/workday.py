"""Workday browser adapter (reusable for Absa, NCBA, etc.).

Workday Candidate Experience Sites (CXS) are fully JavaScript-rendered
and have no public API. This adapter uses Playwright to load the careers
page, wait for job cards to render, and extract listing data from the DOM.

Example (Absa Bank)::

    source = SourceConfig(
        name="Absa Bank",
        slug="absa",
        adapter="workday",
        source_type=SourceType.BROWSER,
        base_url="https://absa.wd3.myworkdayjobs.com",
        config={"tenant": "absa", "instance": "AbsaCareers"},
    )

Example (NCBA Bank)::

    source = SourceConfig(
        name="NCBA Bank",
        slug="ncba",
        adapter="workday",
        source_type=SourceType.BROWSER,
        base_url="https://ncba.wd3.myworkdayjobs.com",
        config={"tenant": "ncba", "instance": "NCBACareers"},
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import BrowserAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_DEFAULT_MAX_PAGES = 50
_JOB_CARD_SELECTOR = 'a[data-automation-id="jobTitle"]'
_NEXT_BUTTON_SELECTOR = 'button[data-uxi-element-id="next"]'


@AdapterRegistry.register("workday")
class WorkdayAdapter(BrowserAdapter):
    """Scrapes jobs from Workday-powered career sites.

    Workday CXS pages are fully JavaScript-rendered single-page
    applications. The adapter navigates to the careers page, waits
    for job cards to appear, and paginates through results using
    the "next" button.

    This adapter is reusable for any Workday employer by providing
    different ``tenant`` and ``instance`` values in the source config.

    Required config keys:
        - ``tenant``: The Workday tenant identifier (e.g. ``"absa"``).
        - ``instance``: The career site instance name (e.g. ``"AbsaCareers"``).
    """

    _host_suffix = "myworkdayjobs.com"
    _detail_selector = '[data-automation-id="jobPostingDescription"]'
    _detail_min_length = 200

    def _build_careers_url(self, config: SourceConfig) -> str:
        """Build the Workday careers listing URL from config.

        Args:
            config: Source configuration with tenant and instance.

        Returns:
            The full URL to the Workday careers listing page.
        """
        base = config.base_url.rstrip("/")
        instance = self._require_config(config, "instance")
        return f"{base}/en-US/{instance}/jobs"

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Fetch job listings from a Workday careers site.

        Navigates to the careers page, waits for JavaScript to render
        job cards, extracts listing data, and paginates through results.

        Args:
            config: Source configuration with ``base_url``, ``tenant``,
                and ``instance`` in the config dict.

        Yields:
            A ``RawListing`` for each job card found.
        """
        from html import escape as html_escape

        url = self._build_careers_url(config)
        max_pages = int(config.config.get("max_pages", _DEFAULT_MAX_PAGES))
        seen_urls: set[str] = set()

        try:
            page: Any = await self._launch_browser()
            await self._navigate(page, url)

            for page_num in range(1, max_pages + 1):
                # Wait for job cards to render
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
                        title = await card.text_content()
                        href = await card.get_attribute("href")

                        if not title or not href:
                            continue

                        title = title.strip()
                        base = config.base_url.rstrip("/")
                        external_url = f"{base}{href}" if href.startswith("/") else href

                        external_url = self._validate_url(external_url, self._host_suffix) or ""
                        if not external_url:
                            logger.debug(
                                "Skipping Workday listing with invalid URL: %s",
                                href,
                            )
                            continue

                        if external_url in seen_urls:
                            continue
                        seen_urls.add(external_url)

                        # Try to extract location from sibling elements
                        location = None
                        parent = await card.evaluate_handle(
                            "el => el.closest('li') || el.parentElement"
                        )
                        if parent:
                            loc_el = await parent.query_selector(
                                '[data-automation-id="jobLocation"],[data-automation-id="subtitle"]'
                            )
                            if loc_el:
                                location = await loc_el.text_content()

                        raw_html_parts = [f"<h1>{html_escape(title)}</h1>"]
                        if location:
                            raw_html_parts.append(f"<p>{html_escape(location.strip())}</p>")

                        yield RawListing(
                            external_url=external_url,
                            title=title,
                            raw_html="\n".join(raw_html_parts),
                            company_name=config.name,
                        )
                    except Exception:
                        logger.warning(
                            "Skipping malformed Workday listing on page %d",
                            page_num,
                            exc_info=True,
                        )
                        continue

                # Try to navigate to next page
                next_btn = await page.query_selector(_NEXT_BUTTON_SELECTOR)
                if next_btn is None:
                    break
                is_disabled = await next_btn.get_attribute("disabled")
                if is_disabled is not None:
                    break

                await next_btn.click()
                # Wait for new results to load after clicking next
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
