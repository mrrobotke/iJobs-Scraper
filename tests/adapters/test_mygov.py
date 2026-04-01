"""Tests for MyGovAdapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.html.mygov import MyGovAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"
BASE_URL = "https://www.mygov.go.ke"
ADVERTS_URL = f"{BASE_URL}/job-adverts"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="MyGov Kenya",
        slug="mygov",
        adapter="mygov",
        source_type=SourceType.HTML,
        base_url=BASE_URL,
    )


LISTINGS_HTML = _load_fixture("mygov_listings.html")
LISTINGS_HTML_NO_NEXT = LISTINGS_HTML.replace(
    '<a href="/job-adverts?page=2" class="next">Next</a>',
    "",
)
DETAIL_HTML = _load_fixture("mygov_detail.html")

EMPTY_HTML = """
<html><body>
<div class="content-area">
    <table class="job-adverts-table">
        <thead><tr><th>Title</th><th>Organization</th><th>Deadline</th></tr></thead>
        <tbody></tbody>
    </table>
</div>
</body></html>
"""

MALFORMED_HTML = """
<html><body>
<div class="content-area">
    <table class="job-adverts-table">
        <thead><tr><th>Title</th><th>Organization</th></tr></thead>
        <tbody>
            <tr><td></td></tr>
            <tr>
                <td><a href="/job-adverts/valid-job-999">Valid Job</a></td>
                <td>Test Ministry</td>
            </tr>
        </tbody>
    </table>
</div>
</body></html>
"""


class TestMyGovRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("mygov")(MyGovAdapter)
        assert AdapterRegistry.get("mygov") is MyGovAdapter


class TestFetchListings:
    @respx.mock
    async def test_parses_jobs(self) -> None:
        respx.get(ADVERTS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 3

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(ADVERTS_URL).mock(
            return_value=httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        )
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.title == "Chief Economist"
        assert first.external_url == f"{BASE_URL}/job-adverts/chief-economist-300001"
        assert first.company_name == "National Treasury"

    @respx.mock
    async def test_empty_table(self) -> None:
        respx.get(ADVERTS_URL).mock(
            return_value=httpx.Response(200, text=EMPTY_HTML),
        )
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_skips_row_without_link(self) -> None:
        respx.get(ADVERTS_URL).mock(
            return_value=httpx.Response(200, text=MALFORMED_HTML),
        )
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Valid Job"

    @respx.mock
    async def test_pagination(self) -> None:
        route = respx.get(ADVERTS_URL)
        route.side_effect = [
            httpx.Response(200, text=LISTINGS_HTML),
            httpx.Response(200, text=LISTINGS_HTML_NO_NEXT),
        ]
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 6
        assert route.call_count == 2

    @respx.mock
    async def test_no_table_on_page(self) -> None:
        respx.get(ADVERTS_URL).mock(
            return_value=httpx.Response(200, text="<html><body>No content</body></html>"),
        )
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0


class TestFetchDetail:
    @respx.mock
    async def test_parses_detail_page(self) -> None:
        detail_url = f"{BASE_URL}/job-adverts/chief-economist-300001"
        respx.get(detail_url).mock(
            return_value=httpx.Response(200, text=DETAIL_HTML),
        )
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=detail_url,
            title="Chief Economist",
            company_name="National Treasury",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "macroeconomic policy" in result.raw_html

    @respx.mock
    async def test_skips_if_raw_html_present(self) -> None:
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/job-adverts/test-999",
            raw_html="<div>Already loaded</div>",
            company_name="Test Ministry",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html == "<div>Already loaded</div>"
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_mygov_url(self) -> None:
        adapter = MyGovAdapter()
        assert adapter.can_handle_url("https://www.mygov.go.ke/job-adverts/test-123")

    def test_non_mygov_url(self) -> None:
        adapter = MyGovAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
