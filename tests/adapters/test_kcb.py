"""Tests for KCBAdapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.html.kcb import KCBAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"
BASE_URL = "https://ke.kcbgroup.com"
CAREERS_URL = f"{BASE_URL}/careers"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="KCB Bank",
        slug="kcb",
        adapter="kcb",
        source_type=SourceType.HTML,
        base_url=BASE_URL,
    )


LISTINGS_HTML = _load_fixture("kcb_listings.html")
LISTINGS_HTML_NO_NEXT = LISTINGS_HTML.replace(
    '<a href="/about/careers?page=2" class="next-page">Next</a>',
    "",
)
DETAIL_HTML = _load_fixture("kcb_detail.html")

EMPTY_HTML = """
<html><body>
<div class="careers-section">
    <div class="career-listings"></div>
</div>
</body></html>
"""

MALFORMED_HTML = """
<html><body>
<div class="careers-section">
    <div class="career-listings">
        <div class="career-card">
            <h3 class="career-card__title"></h3>
        </div>
        <div class="career-card">
            <h3 class="career-card__title">
                <a href="/about/careers/valid-job-999">Valid Job</a>
            </h3>
        </div>
    </div>
</div>
</body></html>
"""


class TestKCBRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("kcb")(KCBAdapter)
        assert AdapterRegistry.get("kcb") is KCBAdapter


class TestFetchListings:
    @respx.mock
    async def test_parses_jobs(self) -> None:
        respx.get(CAREERS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = KCBAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(CAREERS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = KCBAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.title == "Relationship Manager"
        assert first.external_url == f"{BASE_URL}/about/careers/relationship-manager-500001"
        assert first.company_name == "KCB Bank"

    @respx.mock
    async def test_empty_page(self) -> None:
        respx.get(CAREERS_URL).mock(
            return_value=httpx.Response(200, text=EMPTY_HTML),
        )
        adapter = KCBAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_skips_card_without_title_link(self) -> None:
        respx.get(CAREERS_URL).mock(
            return_value=httpx.Response(200, text=MALFORMED_HTML),
        )
        adapter = KCBAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Valid Job"

    @respx.mock
    async def test_pagination(self) -> None:
        route = respx.get(CAREERS_URL)
        route.side_effect = [
            httpx.Response(200, text=LISTINGS_HTML),
            httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        ]
        adapter = KCBAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 4
        assert route.call_count == 2


class TestFetchDetail:
    @respx.mock
    async def test_parses_detail_page(self) -> None:
        detail_url = f"{BASE_URL}/about/careers/relationship-manager-500001"
        respx.get(detail_url).mock(
            return_value=httpx.Response(200, text=DETAIL_HTML),
        )
        adapter = KCBAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=detail_url,
            title="Relationship Manager",
            company_name="KCB Bank",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "corporate banking clients" in result.raw_html

    @respx.mock
    async def test_skips_if_raw_html_present(self) -> None:
        adapter = KCBAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/about/careers/test-999",
            raw_html="<div>Already loaded</div>",
            company_name="KCB Bank",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html == "<div>Already loaded</div>"
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_kcb_url(self) -> None:
        adapter = KCBAdapter()
        assert adapter.can_handle_url("https://ke.kcbgroup.com/about/careers/test-123")

    def test_non_kcb_url(self) -> None:
        adapter = KCBAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
