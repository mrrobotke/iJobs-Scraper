"""Tests for SmartRecruitersAdapter."""

from __future__ import annotations

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.api.smartrecruiters import (
    DEFAULT_LIMIT,
    SmartRecruitersAdapter,
)
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

COMPANY_SLUG = "TestCompany1"
BASE_URL = "https://api.smartrecruiters.com"
POSTINGS_URL = f"{BASE_URL}/v1/companies/{COMPANY_SLUG}/postings"


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="Test Company",
        slug="test-company",
        adapter="smartrecruiters",
        source_type=SourceType.API,
        base_url=BASE_URL,
        config={"company_slug": COMPANY_SLUG},
    )


MOCK_POSTINGS_RESPONSE = {
    "content": [
        {
            "id": "abc-123",
            "name": "Software Engineer",
            "refNumber": "REF001",
            "company": {"name": "Test Company"},
            "location": {"city": "Nairobi", "country": "Kenya"},
            "releasedDate": "2026-03-15T10:00:00Z",
        },
        {
            "id": "def-456",
            "name": "Data Analyst",
            "refNumber": "REF002",
            "company": {"name": "Test Company"},
            "location": {"city": "Mombasa", "country": "Kenya"},
            "releasedDate": "2026-03-16T10:00:00Z",
        },
    ],
    "totalFound": 2,
    "offset": 0,
    "limit": DEFAULT_LIMIT,
}

MOCK_PAGE_1 = {
    "content": [
        {
            "id": f"id-{i}",
            "name": f"Job {i}",
            "company": {"name": "Test Company"},
            "location": {"city": "Nairobi", "country": "Kenya"},
        }
        for i in range(DEFAULT_LIMIT)
    ],
    "totalFound": DEFAULT_LIMIT + 5,
    "offset": 0,
    "limit": DEFAULT_LIMIT,
}

MOCK_PAGE_2 = {
    "content": [
        {
            "id": f"id-{DEFAULT_LIMIT + i}",
            "name": f"Job {DEFAULT_LIMIT + i}",
            "company": {"name": "Test Company"},
            "location": {"city": "Nairobi", "country": "Kenya"},
        }
        for i in range(5)
    ],
    "totalFound": DEFAULT_LIMIT + 5,
    "offset": DEFAULT_LIMIT,
    "limit": DEFAULT_LIMIT,
}

MOCK_DETAIL_RESPONSE = {
    "id": "abc-123",
    "name": "Software Engineer",
    "company": {"name": "Test Company"},
    "location": {"city": "Nairobi", "country": "Kenya"},
    "jobAd": {
        "sections": {
            "jobDescription": {
                "text": "<p>Build great software at Test Company.</p>",
            },
        },
    },
}


class TestSmartRecruitersRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("smartrecruiters")(SmartRecruitersAdapter)
        assert AdapterRegistry.get("smartrecruiters") is SmartRecruitersAdapter


class TestFetchListings:
    @respx.mock
    async def test_yields_listings(self) -> None:
        respx.get(POSTINGS_URL).mock(
            return_value=httpx.Response(200, json=MOCK_POSTINGS_RESPONSE),
        )
        adapter = SmartRecruitersAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(POSTINGS_URL).mock(
            return_value=httpx.Response(200, json=MOCK_POSTINGS_RESPONSE),
        )
        adapter = SmartRecruitersAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.external_id == "abc-123"
        assert first.external_url == (f"https://jobs.smartrecruiters.com/{COMPANY_SLUG}/abc-123")
        assert first.title == "Software Engineer"
        assert first.company_name == "Test Company"
        assert first.raw_json is not None
        assert first.raw_json["id"] == "abc-123"

    @respx.mock
    async def test_pagination(self) -> None:
        route = respx.get(POSTINGS_URL)
        route.side_effect = [
            httpx.Response(200, json=MOCK_PAGE_1),
            httpx.Response(200, json=MOCK_PAGE_2),
        ]
        adapter = SmartRecruitersAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == DEFAULT_LIMIT + 5
        assert route.call_count == 2

    @respx.mock
    async def test_empty_content(self) -> None:
        respx.get(POSTINGS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"content": [], "totalFound": 0, "offset": 0, "limit": 100},
            ),
        )
        adapter = SmartRecruitersAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_missing_content_key(self) -> None:
        respx.get(POSTINGS_URL).mock(
            return_value=httpx.Response(200, json={"totalFound": 0}),
        )
        adapter = SmartRecruitersAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0


class TestFetchDetail:
    @respx.mock
    async def test_skips_if_jobad_present(self) -> None:
        adapter = SmartRecruitersAdapter(request_delay=0)
        listing = RawListing(
            external_id="abc-123",
            external_url=f"https://jobs.smartrecruiters.com/{COMPANY_SLUG}/abc-123",
            raw_json={"id": "abc-123", "jobAd": {"sections": {}}},
            company_name="Test Company",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_json is not None
        assert "jobAd" in result.raw_json
        assert respx.calls.call_count == 0

    @respx.mock
    async def test_fetches_when_no_jobad(self) -> None:
        detail_url = f"{POSTINGS_URL}/abc-123"
        respx.get(detail_url).mock(
            return_value=httpx.Response(200, json=MOCK_DETAIL_RESPONSE),
        )

        adapter = SmartRecruitersAdapter(request_delay=0)
        listing = RawListing(
            external_id="abc-123",
            external_url=f"https://jobs.smartrecruiters.com/{COMPANY_SLUG}/abc-123",
            raw_json={"id": "abc-123", "name": "Software Engineer"},
            company_name="Test Company",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_json is not None
        assert "jobAd" in result.raw_json

    @respx.mock
    async def test_returns_as_is_if_no_external_id(self) -> None:
        adapter = SmartRecruitersAdapter(request_delay=0)
        listing = RawListing(
            external_url=f"https://jobs.smartrecruiters.com/{COMPANY_SLUG}/abc-123",
            raw_json={"name": "Engineer"},
            company_name="Test Company",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result is listing
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_smartrecruiters_jobs_url(self) -> None:
        adapter = SmartRecruitersAdapter()
        assert adapter.can_handle_url("https://jobs.smartrecruiters.com/AmrefHealthAfrica4/1234")

    def test_smartrecruiters_api_url(self) -> None:
        adapter = SmartRecruitersAdapter()
        assert adapter.can_handle_url(
            "https://api.smartrecruiters.com/v1/companies/AmrefHealthAfrica4"
        )

    def test_non_smartrecruiters_url(self) -> None:
        adapter = SmartRecruitersAdapter()
        assert not adapter.can_handle_url("https://careers.example.com/job/123")

    def test_partial_match(self) -> None:
        adapter = SmartRecruitersAdapter()
        assert not adapter.can_handle_url("https://notsmartrecruitery.com/job/1")
