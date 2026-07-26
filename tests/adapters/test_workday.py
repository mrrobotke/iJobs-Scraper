"""Tests for the Workday CXS JSON adapter."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.browser.workday import WorkdayAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://absa.wd3.myworkdayjobs.com"
TENANT = "absa"
INSTANCE = "ABSAcareersite"
LISTINGS_URL = f"{BASE_URL}/wday/cxs/{TENANT}/{INSTANCE}/jobs"
EXTERNAL_PATH = "/job/Absa-Headquarters-KE/Sector-Lead_R-123"
DETAIL_URL = f"{BASE_URL}/wday/cxs/{TENANT}/{INSTANCE}{EXTERNAL_PATH}"


def _make_config(**overrides: Any) -> SourceConfig:
    config: dict[str, Any] = {
        "tenant": TENANT,
        "instance": INSTANCE,
        "applied_facets": {
            "locationCountry": ["9e684fd7be1e469d9ee955a4c3b754be"],
        },
    }
    config.update(overrides)
    return SourceConfig(
        name="Absa Bank",
        slug="absa",
        adapter="workday",
        source_type=SourceType.API,
        base_url=BASE_URL,
        config=config,
    )


def _response(*, total: int = 1, postings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if postings is None:
        postings = [
            {
                "title": "Sector Lead",
                "externalPath": EXTERNAL_PATH,
                "locationsText": "Absa Headquarters (KE)",
                "postedOn": "Posted 2 Days Ago",
                "remoteType": "Hybrid",
                "bulletFields": ["R-123", "2026-08-07"],
            }
        ]
    return {"total": total, "jobPostings": postings}


class TestWorkdayRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("workday")(WorkdayAdapter)
        assert AdapterRegistry.get("workday") is WorkdayAdapter


class TestFetchListings:
    @respx.mock
    async def test_uses_cxs_api_and_yields_listing(self) -> None:
        route = respx.post(LISTINGS_URL).mock(return_value=httpx.Response(200, json=_response()))
        adapter = WorkdayAdapter(request_delay=0)

        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        listing = listings[0]
        assert listing.external_id == "R-123"
        assert listing.title == "Sector Lead"
        assert listing.company_name == "Absa Bank"
        assert listing.external_url == f"{BASE_URL}/en-US/{INSTANCE}{EXTERNAL_PATH}"
        assert listing.raw_json is not None
        request_payload = route.calls[0].request.content
        assert b'"locationCountry":["9e684fd7be1e469d9ee955a4c3b754be"]' in request_payload

    @respx.mock
    async def test_paginates_by_offset_until_total(self) -> None:
        second_path = "/job/Nairobi-KE/Second_R-456"
        route = respx.post(LISTINGS_URL).mock(
            side_effect=[
                httpx.Response(200, json=_response(total=2)),
                httpx.Response(
                    200,
                    json=_response(
                        total=2,
                        postings=[
                            {
                                "title": "Second",
                                "externalPath": second_path,
                                "locationsText": "Nairobi",
                                "bulletFields": ["R-456"],
                            }
                        ],
                    ),
                ),
            ]
        )
        adapter = WorkdayAdapter(request_delay=0)

        listings = [listing async for listing in adapter.fetch_listings(_make_config(page_size=1))]

        assert [listing.external_id for listing in listings] == ["R-123", "R-456"]
        assert route.call_count == 2
        assert b'"offset":1' in route.calls[1].request.content

    @respx.mock
    async def test_skips_posting_without_external_path(self) -> None:
        respx.post(LISTINGS_URL).mock(
            return_value=httpx.Response(
                200,
                json=_response(postings=[{"title": "Malformed"}]),
            )
        )
        adapter = WorkdayAdapter(request_delay=0)

        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert listings == []

    async def test_requires_tenant_and_instance(self) -> None:
        adapter = WorkdayAdapter(request_delay=0)
        with pytest.raises(AdapterError, match="tenant"):
            _ = [listing async for listing in adapter.fetch_listings(_make_config(tenant=None))]


class TestFetchDetail:
    @respx.mock
    async def test_fetches_job_posting_info_from_cxs(self) -> None:
        respx.get(DETAIL_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jobPostingInfo": {
                        "title": "Sector Lead - Full",
                        "jobDescription": "<p>Lead the banking sector portfolio.</p>",
                        "location": "Absa Headquarters (KE)",
                    }
                },
            )
        )
        adapter = WorkdayAdapter(request_delay=0)
        listing = RawListing(
            external_id="R-123",
            external_url=f"{BASE_URL}/en-US/{INSTANCE}{EXTERNAL_PATH}",
            title="Sector Lead",
            raw_json={"externalPath": EXTERNAL_PATH},
            company_name="Absa Bank",
        )

        result = await adapter.fetch_detail(listing, _make_config())

        assert result.title == "Sector Lead - Full"
        assert result.raw_html == "<p>Lead the banking sector portfolio.</p>"
        assert result.raw_json is not None
        assert result.raw_json["location"] == "Absa Headquarters (KE)"

    async def test_returns_listing_when_external_path_is_missing(self) -> None:
        adapter = WorkdayAdapter(request_delay=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/en-US/{INSTANCE}/job/example",
            title="Example",
        )

        assert await adapter.fetch_detail(listing, _make_config()) is listing


class TestCanHandleUrl:
    def test_workday_url(self) -> None:
        assert WorkdayAdapter().can_handle_url(
            "https://absa.wd3.myworkdayjobs.com/en-US/ABSAcareersite/job/example"
        )

    def test_non_workday_url(self) -> None:
        assert not WorkdayAdapter().can_handle_url("https://example.com/job/123")
