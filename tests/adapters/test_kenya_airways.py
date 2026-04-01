"""Tests for KenyaAirwaysAdapter."""

from __future__ import annotations

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.api.kenya_airways import (
    CAREERS_API,
    DEFAULT_LIMIT,
    KenyaAirwaysAdapter,
)
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://api-irec-prod.kenya-airways.com"
JOBS_URL = f"{CAREERS_API}/jobs"


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="Kenya Airways",
        slug="kenya-airways",
        adapter="kenya_airways",
        source_type=SourceType.API,
        base_url=BASE_URL,
    )


MOCK_JOBS_RESPONSE = {
    "jobs": [
        {
            "id": 1001,
            "title": "Captain - Boeing 787",
            "url": "https://careers.kenya-airways.com/jobs/1001",
            "location": "Nairobi, Kenya",
            "department": "Flight Operations",
        },
        {
            "id": 1002,
            "title": "Software Developer",
            "url": "https://careers.kenya-airways.com/jobs/1002",
            "location": "Nairobi, Kenya",
            "department": "IT",
        },
    ]
}

MOCK_PAGE_1 = {
    "jobs": [
        {
            "id": 2000 + i,
            "title": f"Position {i}",
            "url": f"https://careers.kenya-airways.com/jobs/{2000 + i}",
        }
        for i in range(DEFAULT_LIMIT)
    ]
}

MOCK_PAGE_2 = {
    "jobs": [
        {
            "id": 3000 + i,
            "title": f"Position Extra {i}",
            "url": f"https://careers.kenya-airways.com/jobs/{3000 + i}",
        }
        for i in range(3)
    ]
}

MOCK_DETAIL_RESPONSE = {
    "id": 1001,
    "title": "Captain - Boeing 787",
    "description": "<p>Full job description for Captain role.</p>",
    "location": "Nairobi, Kenya",
    "department": "Flight Operations",
}


class TestKenyaAirwaysRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("kenya_airways")(KenyaAirwaysAdapter)
        assert AdapterRegistry.get("kenya_airways") is KenyaAirwaysAdapter


class TestFetchListings:
    @respx.mock
    async def test_yields_listings(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json=MOCK_JOBS_RESPONSE),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json=MOCK_JOBS_RESPONSE),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.external_id == "1001"
        assert first.external_url == "https://careers.kenya-airways.com/jobs/1001"
        assert first.title == "Captain - Boeing 787"
        assert first.company_name == "Kenya Airways"
        assert first.raw_json is not None
        assert first.raw_json["id"] == 1001

    @respx.mock
    async def test_pagination(self) -> None:
        route = respx.get(JOBS_URL)
        route.side_effect = [
            httpx.Response(200, json=MOCK_PAGE_1),
            httpx.Response(200, json=MOCK_PAGE_2),
        ]
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == DEFAULT_LIMIT + 3
        assert route.call_count == 2

    @respx.mock
    async def test_empty_jobs(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json={"jobs": []}),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_missing_jobs_key(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json={}),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_constructs_url_when_missing(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"jobs": [{"id": 9999, "title": "Test Role"}]},
            ),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].external_url == "https://careers.kenya-airways.com/jobs/9999"

    @respx.mock
    async def test_max_pages_cap(self) -> None:
        """Adapter should stop after MAX_PAGES even if more pages exist."""
        from unittest.mock import patch

        full_page = {
            "jobs": [
                {
                    "id": i,
                    "title": f"Job {i}",
                    "url": f"https://careers.kenya-airways.com/jobs/{i}",
                }
                for i in range(DEFAULT_LIMIT)
            ]
        }
        route = respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json=full_page),
        )
        with patch("ijobs_scraper.adapters.api.kenya_airways.MAX_PAGES", 2):
            adapter = KenyaAirwaysAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == DEFAULT_LIMIT * 2
        assert route.call_count == 2


class TestFetchDetail:
    @respx.mock
    async def test_skips_if_description_present(self) -> None:
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listing = RawListing(
            external_id="1001",
            external_url="https://careers.kenya-airways.com/jobs/1001",
            raw_json={"id": 1001, "description": "Already has description"},
            company_name="Kenya Airways",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_json is not None
        assert result.raw_json["description"] == "Already has description"
        assert respx.calls.call_count == 0

    @respx.mock
    async def test_returns_as_is_if_no_external_id(self) -> None:
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listing = RawListing(
            external_url="https://careers.kenya-airways.com/jobs/1001",
            raw_json={"title": "Captain"},
            company_name="Kenya Airways",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result is listing
        assert respx.calls.call_count == 0

    @respx.mock
    async def test_fetches_when_no_description(self) -> None:
        detail_url = f"{CAREERS_API}/jobs/1001"
        respx.get(detail_url).mock(
            return_value=httpx.Response(200, json=MOCK_DETAIL_RESPONSE),
        )

        adapter = KenyaAirwaysAdapter(request_delay=0)
        listing = RawListing(
            external_id="1001",
            external_url="https://careers.kenya-airways.com/jobs/1001",
            raw_json={"id": 1001, "title": "Captain - Boeing 787"},
            company_name="Kenya Airways",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_json is not None
        assert "description" in result.raw_json


class TestCanHandleUrl:
    def test_kenya_airways_careers_url(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert adapter.can_handle_url("https://careers.kenya-airways.com/jobs/1001")

    def test_kenya_airways_api_url(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert adapter.can_handle_url("https://api-irec-prod.kenya-airways.com/careers/api/v2/jobs")

    def test_non_kenya_airways_url(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert not adapter.can_handle_url("https://careers.example.com/job/123")

    def test_partial_match(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert not adapter.can_handle_url("https://kenya-airwaysy.com/job/1")
