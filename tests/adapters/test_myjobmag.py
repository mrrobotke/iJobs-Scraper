"""Tests for MyJobMagAdapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.html.myjobmag import MyJobMagAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"
BASE_URL = "https://www.myjobmag.co.ke"
JOBS_URL = f"{BASE_URL}/jobs"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="MyJobMag Kenya",
        slug="myjobmag",
        adapter="myjobmag",
        source_type=SourceType.HTML,
        base_url=BASE_URL,
    )


LISTINGS_HTML = _load_fixture("myjobmag_listings.html")
LISTINGS_HTML_NO_NEXT = LISTINGS_HTML.replace(
    '<a href="/jobs?page=2" class="pagination__next">Next &raquo;</a>',
    "",
)
DETAIL_HTML = _load_fixture("myjobmag_detail.html")

EMPTY_HTML = """
<html><body>
<div class="job-list">
    <ul class="job-list__items"></ul>
</div>
</body></html>
"""

MALFORMED_HTML = """
<html><body>
<div class="job-list">
    <ul class="job-list__items">
        <li class="job-list__item">
            <div class="job-info">
                <h2 class="job-info__title"></h2>
            </div>
        </li>
        <li class="job-list__item">
            <div class="job-info">
                <h2 class="job-info__title">
                    <a href="/job/valid-job-999">Valid Job</a>
                </h2>
                <div class="job-info__company">Valid Corp</div>
            </div>
        </li>
    </ul>
</div>
</body></html>
"""


class TestMyJobMagRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("myjobmag")(MyJobMagAdapter)
        assert AdapterRegistry.get("myjobmag") is MyJobMagAdapter


class TestFetchListings:
    @respx.mock
    async def test_parses_jobs(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.title == "Accountant"
        assert first.external_url == f"{BASE_URL}/job/accountant-at-kpmg-200001"
        assert first.company_name == "KPMG East Africa"

    @respx.mock
    async def test_empty_page(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=EMPTY_HTML),
        )
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_skips_entry_without_title_link(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, text=MALFORMED_HTML),
        )
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
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
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 4
        assert route.call_count == 2


class TestFetchDetail:
    @respx.mock
    async def test_parses_detail_page(self) -> None:
        detail_url = f"{BASE_URL}/job/accountant-at-kpmg-200001"
        respx.get(detail_url).mock(
            return_value=httpx.Response(200, text=DETAIL_HTML),
        )
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=detail_url,
            title="Accountant",
            company_name="KPMG East Africa",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "CPA-K certification" in result.raw_html

    @respx.mock
    async def test_skips_if_raw_html_present(self) -> None:
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/job/test-999",
            raw_html="<div>Already loaded</div>",
            company_name="Test Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html == "<div>Already loaded</div>"
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_myjobmag_url(self) -> None:
        adapter = MyJobMagAdapter()
        assert adapter.can_handle_url("https://www.myjobmag.co.ke/job/test-123")

    def test_non_myjobmag_url(self) -> None:
        adapter = MyJobMagAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
