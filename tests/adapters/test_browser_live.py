"""Live integration tests for adapters with historically browser-backed imports.

These tests hit real websites and are NOT run in CI.
Run manually with: pytest tests/adapters/test_browser_live.py -v -m live
"""

from __future__ import annotations

from typing import Any

import pytest

from ijobs_scraper.adapters.browser.impactpool import ImpactpoolAdapter
from ijobs_scraper.adapters.browser.workday import WorkdayAdapter
from ijobs_scraper.adapters.browser.world_vision import WorldVisionAdapter
from ijobs_scraper.models import SourceConfig, SourceType

pytestmark = pytest.mark.live


def _config(
    name: str,
    slug: str,
    adapter: str,
    base_url: str,
    source_type: SourceType,
    config: dict[str, Any] | None = None,
) -> SourceConfig:
    return SourceConfig(
        name=name,
        slug=slug,
        adapter=adapter,
        source_type=source_type,
        base_url=base_url,
        config=config or {},
    )


class TestWorkdayAbsaLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = WorkdayAdapter(request_delay=0)
        config = _config(
            "Absa Bank",
            "absa",
            "workday",
            "https://absa.wd3.myworkdayjobs.com",
            SourceType.API,
            {
                "tenant": "absa",
                "instance": "ABSAcareersite",
                "applied_facets": {"locationCountry": ["9e684fd7be1e469d9ee955a4c3b754be"]},
            },
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break
        await adapter.close()

        assert len(listings) >= 1
        for listing in listings:
            assert listing.external_url.startswith("http")
            assert listing.title
            assert listing.company_name == "Absa Bank"


class TestImpactpoolLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = ImpactpoolAdapter(request_delay=0, jitter=0)
        config = _config(
            "Impactpool",
            "impactpool",
            "impactpool",
            "https://www.impactpool.org",
            SourceType.HTML,
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break
        await adapter.close()

        assert len(listings) >= 1
        for listing in listings:
            assert listing.external_url.startswith("http")
            assert listing.title


class TestWorldVisionLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = WorldVisionAdapter(page_timeout=60.0, nav_delay=5.0)
        config = _config(
            "World Vision",
            "world-vision",
            "world_vision",
            "https://careers.wvi.org",
            SourceType.BROWSER,
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break

        for listing in listings:
            assert listing.external_url.startswith("http")
            assert listing.title
