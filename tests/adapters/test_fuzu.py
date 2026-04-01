"""Tests for FuzuAdapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.html.fuzu import FuzuAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"
BASE_URL = "https://www.fuzu.com"
JOBS_URL = f"{BASE_URL}/kenya/jobs"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="Fuzu Kenya",
        slug="fuzu",
        adapter="fuzu",
        source_type=SourceType.HTML,
        base_url=BASE_URL,
    )


LISTINGS_HTML = _load_fixture("fuzu_listings.html")
LISTINGS_HTML_NO_NEXT = LISTINGS_HTML.replace(
    '<a href="/kenya/jobs?page=2" rel="next">Next</a>',
    "",
)
DETAIL_HTML = _load_fixture("fuzu_detail.html")

EMPTY_HTML = """
<html><body>
<div class="jobs-container">
    <div class="job-listings"></div>
</div>
</body></html>
"""

MALFORMED_HTML = """
<html><body>
<div class="jobs-container">
    <section class="job-list">
        <a href="" class="b2c-card" data-id="bad1">
            <h2>Empty Href Job</h2>
        </a>
        <a href="/kenya/jobs/valid-job-good1" class="b2c-card"
           company_slug="valid-corp" data-id="good1">
            <h2>Valid Job</h2>
        </a>
    </section>
</div>
</body></html>
"""


class TestFuzuRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("fuzu")(FuzuAdapter)
        assert AdapterRegistry.get("fuzu") is FuzuAdapter


class TestFetchListings:
    @respx.mock
    async def test_parses_jobs(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = FuzuAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = FuzuAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.title == "Sales Representative"
        assert first.external_url == f"{BASE_URL}/kenya/jobs/sales-representative-400001"
        assert first.company_name == "unilever-kenya"
        assert first.external_id == "400001"

    @respx.mock
    async def test_empty_page(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=EMPTY_HTML),
        )
        adapter = FuzuAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_skips_card_without_link(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=MALFORMED_HTML),
        )
        adapter = FuzuAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Valid Job"

    @respx.mock
    async def test_pagination(self) -> None:
        route = respx.get(JOBS_URL)
        route.side_effect = [
            httpx.Response(200, text=LISTINGS_HTML),
            httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        ]
        adapter = FuzuAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 4
        assert route.call_count == 2


class TestFetchDetail:
    @respx.mock
    async def test_parses_detail_page(self) -> None:
        detail_url = f"{BASE_URL}/kenya/jobs/sales-representative-400001"
        respx.get(detail_url).mock(
            return_value=httpx.Response(200, text=DETAIL_HTML),
        )
        adapter = FuzuAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_id="400001",
            external_url=detail_url,
            title="Sales Representative",
            company_name="Unilever Kenya",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "FMCG portfolio" in result.raw_html

    @respx.mock
    async def test_skips_if_raw_html_present(self) -> None:
        adapter = FuzuAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/kenya/jobs/test-999",
            raw_html="<div>Already loaded</div>",
            company_name="Test Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html == "<div>Already loaded</div>"
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_fuzu_url(self) -> None:
        adapter = FuzuAdapter()
        assert adapter.can_handle_url("https://www.fuzu.com/kenya/jobs/test-123")

    def test_non_fuzu_url(self) -> None:
        adapter = FuzuAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
