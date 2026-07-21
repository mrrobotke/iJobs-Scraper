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
    '<a href="/jobs?page=2" class="pagination__next">Next &raquo;</a>\n',
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
    <a href="/job/">No</a>
    <a href="/job/valid-job-999">Valid Job at Valid Corp</a>
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
        assert first.title == "Accountant at KPMG East Africa"
        assert first.external_url == f"{BASE_URL}/job/accountant-at-kpmg-200001"
        assert first.company_name == "MyJobMag Kenya"  # No company element in HTML

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
        assert listings[0].title == "Valid Job at Valid Corp"

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
    async def test_resolves_apply_now_redirect_without_following_external_target(self) -> None:
        detail_url = f"{BASE_URL}/job/procurement-coordinator-200002"
        apply_now_url = f"{BASE_URL}/apply-now/1283419"
        employer_url = "https://seventwentyholdings.co.ke/jobs/procurement-coordinator"
        detail_html = """
        <html><body><div class="job-detail">
          <h2>Method of Application</h2>
          <div class="mag-b">
            Interested and qualified? Go to
            <a href="/apply-now/1283419">SevenTwenty Holdings</a> to apply.
          </div>
        </div></body></html>
        """
        respx.get(detail_url).mock(return_value=httpx.Response(200, text=detail_html))
        redirect_route = respx.get(apply_now_url).mock(
            return_value=httpx.Response(302, headers={"Location": employer_url})
        )
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listing = RawListing(external_url=detail_url, title="Procurement Coordinator")

        result = await adapter.fetch_detail(listing, _make_config())

        assert result.application_url == employer_url
        assert redirect_route.call_count == 1

    @respx.mock
    async def test_allows_bounded_same_source_canonical_redirect(self) -> None:
        detail_url = "https://myjobmag.co.ke/job/procurement-coordinator-200004"
        apply_now_url = "https://myjobmag.co.ke/apply-now/1283421"
        canonical_apply_now_url = "https://www.myjobmag.co.ke/apply-now/1283421"
        employer_url = "https://seventwentyholdings.co.ke/jobs/procurement-coordinator"
        detail_html = """
        <html><body><div class="job-detail">
          <h2>Method of Application</h2>
          <a href="/apply-now/1283421">Apply</a>
        </div></body></html>
        """
        respx.get(detail_url).mock(return_value=httpx.Response(200, text=detail_html))
        first_redirect = respx.get(apply_now_url).mock(
            return_value=httpx.Response(301, headers={"Location": canonical_apply_now_url})
        )
        second_redirect = respx.get(canonical_apply_now_url).mock(
            return_value=httpx.Response(302, headers={"Location": employer_url})
        )
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listing = RawListing(external_url=detail_url, title="Procurement Coordinator")

        result = await adapter.fetch_detail(listing, _make_config())

        assert result.application_url == employer_url
        assert first_redirect.call_count == 1
        assert second_redirect.call_count == 1

    @respx.mock
    async def test_rejects_apply_now_redirect_back_to_myjobmag(self) -> None:
        detail_url = f"{BASE_URL}/job/procurement-coordinator-200003"
        apply_now_url = f"{BASE_URL}/apply-now/1283420"
        detail_html = """
        <html><body><div class="job-detail">
          <h2>Method of Application</h2>
          <a href="/apply-now/1283420">Apply</a>
        </div></body></html>
        """
        respx.get(detail_url).mock(return_value=httpx.Response(200, text=detail_html))
        respx.get(apply_now_url).mock(
            return_value=httpx.Response(
                302,
                headers={"Location": f"{BASE_URL}/job/another-role"},
            )
        )
        adapter = MyJobMagAdapter(request_delay=0, jitter=0)
        listing = RawListing(external_url=detail_url, title="Procurement Coordinator")

        result = await adapter.fetch_detail(listing, _make_config())

        assert result.application_url is None

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
