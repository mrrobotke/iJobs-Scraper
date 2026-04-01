"""Live integration tests for HTML adapters.

These tests hit real websites and are NOT run in CI.
Run manually with: pytest tests/adapters/test_html_live.py -v -m live
"""

from __future__ import annotations

import httpx
import pytest

from ijobs_scraper.adapters.html.brightermonday import BrighterMondayAdapter
from ijobs_scraper.adapters.html.fuzu import FuzuAdapter
from ijobs_scraper.adapters.html.kcb import KCBAdapter
from ijobs_scraper.adapters.html.mygov import MyGovAdapter
from ijobs_scraper.adapters.html.myjobmag import MyJobMagAdapter
from ijobs_scraper.models import SourceConfig, SourceType

pytestmark = pytest.mark.live


def _config(name: str, slug: str, adapter: str, base_url: str) -> SourceConfig:
    return SourceConfig(
        name=name,
        slug=slug,
        adapter=adapter,
        source_type=SourceType.HTML,
        base_url=base_url,
    )


class TestBrighterMondayLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = BrighterMondayAdapter()
        config = _config(
            "BrighterMonday",
            "brightermonday",
            "brightermonday",
            "https://www.brightermonday.co.ke",
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
            assert listing.company_name


class TestMyJobMagLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = MyJobMagAdapter()
        config = _config(
            "MyJobMag Kenya",
            "myjobmag",
            "myjobmag",
            "https://www.myjobmag.co.ke",
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


class TestMyGovLive:
    async def test_fetch_listings_no_crash(self) -> None:
        """MyGov /job-adverts may 404 — adapter must not crash."""
        adapter = MyGovAdapter()
        config = _config(
            "MyGov Kenya",
            "mygov",
            "mygov",
            "https://www.mygov.go.ke",
        )
        listings = []
        try:
            async for listing in adapter.fetch_listings(config):
                listings.append(listing)
                if len(listings) >= 3:
                    break
        except httpx.HTTPStatusError:
            pass  # Portal may have removed /job-adverts (404)
        await adapter.close()

        # Just verify no crash — MyGov may have removed /job-adverts
        for listing in listings:
            assert listing.external_url.startswith("http")


class TestFuzuLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = FuzuAdapter()
        config = _config(
            "Fuzu Kenya",
            "fuzu",
            "fuzu",
            "https://www.fuzu.com",
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


class TestKCBLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        adapter = KCBAdapter()
        config = _config(
            "KCB Bank",
            "kcb",
            "kcb",
            "https://ke.kcbgroup.com",
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break
        await adapter.close()

        # KCB may have 0 openings at any time — just verify no crash
        for listing in listings:
            assert listing.external_url.startswith("http")
