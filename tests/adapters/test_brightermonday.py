"""Tests for BrighterMondayAdapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.html.brightermonday import BrighterMondayAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"
BASE_URL = "https://www.brightermonday.co.ke"
JOBS_URL = f"{BASE_URL}/jobs"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="BrighterMonday",
        slug="brightermonday",
        adapter="brightermonday",
        source_type=SourceType.HTML,
        base_url=BASE_URL,
    )


LISTINGS_HTML = _load_fixture("brightermonday_listings.html")
LISTINGS_HTML_NO_NEXT = LISTINGS_HTML.replace(
    '<a href="/jobs?page=2" class="pagination__next" rel="next">Next</a>',
    "",
)
DETAIL_HTML = _load_fixture("brightermonday_detail.html")

EMPTY_HTML = """
<html><body>
<div class="search-results">
    <div class="search-results__list"></div>
</div>
</body></html>
"""

MALFORMED_HTML = """
<html><body>
<div class="search-results">
    <div class="search-results__list">
        <div class="job-card" data-job-id="bad1">
            <div class="job-card__content">
                <h3 class="job-card__title"></h3>
            </div>
        </div>
        <div class="job-card" data-job-id="good1">
            <div class="job-card__content">
                <h3 class="job-card__title">
                    <a href="/listings/valid-job-good1">Valid Job</a>
                </h3>
                <p class="job-card__company">Test Corp</p>
            </div>
        </div>
    </div>
</div>
</body></html>
"""


class TestBrighterMondayRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("brightermonday")(BrighterMondayAdapter)
        assert AdapterRegistry.get("brightermonday") is BrighterMondayAdapter


class TestFetchListings:
    @respx.mock
    async def test_parses_jobs(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = BrighterMondayAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 3

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = BrighterMondayAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.title == "Software Engineer"
        assert first.external_url == f"{BASE_URL}/listings/software-engineer-100001"
        assert first.company_name == "Safaricom PLC"
        assert first.external_id == "100001"

    @respx.mock
    async def test_empty_page(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=EMPTY_HTML),
        )
        adapter = BrighterMondayAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_skips_card_without_title_link(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=MALFORMED_HTML),
        )
        adapter = BrighterMondayAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Valid Job"

    @respx.mock
    async def test_pagination(self) -> None:
        route = respx.get(JOBS_URL)
        route.side_effect = [
            httpx.Response(200, text=LISTINGS_HTML),  # CSRF extraction
            httpx.Response(200, text=LISTINGS_HTML),  # page 1
            httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),  # page 2 (final)
        ]
        adapter = BrighterMondayAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        # 3 calls: first for CSRF, then page 1, then page 2
        assert len(listings) == 6
        assert route.call_count == 3

    @respx.mock
    async def test_csrf_token_extracted(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = BrighterMondayAdapter(request_delay=0, jitter=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        client = await adapter._ensure_client()
        assert client.headers.get("X-CSRF-TOKEN") == "abc123csrftoken"


class TestFetchDetail:
    @respx.mock
    async def test_parses_detail_page(self) -> None:
        detail_url = f"{BASE_URL}/listings/software-engineer-100001"
        respx.get(detail_url).mock(
            return_value=httpx.Response(200, text=DETAIL_HTML),
        )
        adapter = BrighterMondayAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_id="100001",
            external_url=detail_url,
            title="Software Engineer",
            company_name="Safaricom PLC",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "Software Engineer" in result.raw_html
        assert "scalable microservices" in result.raw_html

    @respx.mock
    async def test_skips_if_raw_html_present(self) -> None:
        adapter = BrighterMondayAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/listings/test-100001",
            raw_html="<div>Already loaded</div>",
            company_name="Test Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html == "<div>Already loaded</div>"
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_brightermonday_url(self) -> None:
        adapter = BrighterMondayAdapter()
        assert adapter.can_handle_url("https://www.brightermonday.co.ke/listings/job-123")

    def test_non_brightermonday_url(self) -> None:
        adapter = BrighterMondayAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
