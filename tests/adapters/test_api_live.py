"""Live integration tests for API adapters.

These tests hit real APIs and are NOT run in CI.
Run manually with: pytest tests/adapters/test_api_live.py -v -m live

Requires environment variables in .env.local:
    RELIEFWEB_APPNAME — registered appname for ReliefWeb API
"""

from __future__ import annotations

import os

import pytest

from ijobs_scraper.adapters.api.reliefweb import ReliefWebAdapter
from ijobs_scraper.models import SourceConfig, SourceType

pytestmark = pytest.mark.live


def _config(
    name: str,
    slug: str,
    adapter: str,
    base_url: str,
    config: dict[str, object] | None = None,
) -> SourceConfig:
    return SourceConfig(
        name=name,
        slug=slug,
        adapter=adapter,
        source_type=SourceType.API,
        base_url=base_url,
        config=config or {},
    )


class TestReliefWebLive:
    async def test_fetch_listings_returns_jobs(self) -> None:
        appname = os.environ.get("RELIEFWEB_APPNAME", "")
        if not appname:
            pytest.skip("RELIEFWEB_APPNAME not set")

        adapter = ReliefWebAdapter()
        config = _config(
            "ReliefWeb Kenya",
            "reliefweb-kenya",
            "reliefweb",
            "https://api.reliefweb.int",
            config={"appname": appname},
        )
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 3:
                break
        await adapter.close()

        assert len(listings) >= 1, "ReliefWeb should have at least 1 Kenya job"
        for listing in listings:
            assert listing.external_url.startswith("http")
            assert listing.title
            assert listing.company_name

    async def test_fetch_detail_enriches_listing(self) -> None:
        appname = os.environ.get("RELIEFWEB_APPNAME", "")
        if not appname:
            pytest.skip("RELIEFWEB_APPNAME not set")

        adapter = ReliefWebAdapter()
        config = _config(
            "ReliefWeb Kenya",
            "reliefweb-kenya",
            "reliefweb",
            "https://api.reliefweb.int",
            config={"appname": appname},
        )
        # Grab first listing, then fetch its detail
        first = None
        async for listing in adapter.fetch_listings(config):
            first = listing
            break

        if first is None:
            await adapter.close()
            pytest.skip("No listings available from ReliefWeb")

        listing_without_html = first.model_copy(update={"raw_html": None})
        detail = await adapter.fetch_detail(listing_without_html, config)
        await adapter.close()

        assert detail.external_url == first.external_url
        assert detail.raw_html
        assert detail.title
