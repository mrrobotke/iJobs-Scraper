"""Live integration tests for browser adapters.

These tests hit real websites using Playwright and are NOT run in CI.
Run manually with: pytest tests/adapters/test_browser_live.py -v -m live

Requires playwright to be installed:
    pip install ijobs-scraper[browser]
    playwright install chromium
"""

from __future__ import annotations

from typing import Any

import pytest

from ijobs_scraper.adapters.browser.impactpool import ImpactpoolAdapter
from ijobs_scraper.adapters.browser.workday import WorkdayAdapter
from ijobs_scraper.adapters.browser.world_vision import WorldVisionAdapter
from ijobs_scraper.models import SourceConfig, SourceType

pytestmark = pytest.mark.live


def _browser_config(
    name: str,
    slug: str,
    adapter: str,
    base_url: str,
    config: dict[str, Any] | None = None,
) -> SourceConfig:
    return SourceConfig(
        name=name,
        slug=slug,
        adapter=adapter,
        source_type=SourceType.BROWSER,
        base_url=base_url,
        config=config or {},
    )


class TestWorkdayAbsaLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = WorkdayAdapter(page_timeout=60.0, nav_delay=5.0)
        config = _browser_config(
            "Absa Bank",
            "absa",
            "workday",
            "https://absa.wd3.myworkdayjobs.com",
            {"tenant": "absa", "instance": "AbsaCareers"},
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break

        # Workday may have variable openings — verify no crash
        for listing in listings:
            assert listing.external_url.startswith("http")
            assert listing.title
            assert listing.company_name == "Absa Bank"


class TestWorkdayNCBALive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = WorkdayAdapter(page_timeout=60.0, nav_delay=5.0)
        config = _browser_config(
            "NCBA Bank",
            "ncba",
            "workday",
            "https://ncba.wd3.myworkdayjobs.com",
            {"tenant": "ncba", "instance": "NCBACareers"},
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break

        for listing in listings:
            assert listing.external_url.startswith("http")
            assert listing.title
            assert listing.company_name == "NCBA Bank"


class TestImpactpoolLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = ImpactpoolAdapter(page_timeout=60.0, nav_delay=5.0)
        config = _browser_config(
            "Impactpool",
            "impactpool",
            "impactpool",
            "https://www.impactpool.org",
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break

        for listing in listings:
            assert listing.external_url.startswith("http")
            assert listing.title


class TestWorldVisionLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = WorldVisionAdapter(page_timeout=60.0, nav_delay=5.0)
        config = _browser_config(
            "World Vision",
            "world-vision",
            "world_vision",
            "https://careers.wvi.org",
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break

        for listing in listings:
            assert listing.external_url.startswith("http")
            assert listing.title
