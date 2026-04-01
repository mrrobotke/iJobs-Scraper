"""Tests for GreenhouseAdapter."""

from __future__ import annotations

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.api.greenhouse import BOARDS_API, GreenhouseAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BOARD_TOKEN = "testcompany"
JOBS_URL = f"{BOARDS_API}/{BOARD_TOKEN}/jobs"


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="Test Company",
        slug="test-company",
        adapter="greenhouse",
        source_type=SourceType.API,
        base_url="https://boards-api.greenhouse.io",
        config={"board_token": BOARD_TOKEN},
    )


MOCK_JOBS_RESPONSE = {
    "jobs": [
        {
            "id": 101,
            "title": "Software Engineer",
            "absolute_url": "https://boards.greenhouse.io/testcompany/jobs/101",
            "content": "<p>Build great software.</p>",
            "location": {"name": "Nairobi, Kenya"},
            "departments": [{"name": "Engineering"}],
        },
        {
            "id": 102,
            "title": "Product Manager",
            "absolute_url": "https://boards.greenhouse.io/testcompany/jobs/102",
            "content": "<p>Lead product strategy.</p>",
            "location": {"name": "Remote"},
            "departments": [{"name": "Product"}],
        },
    ]
}

MOCK_SINGLE_JOB = {
    "id": 101,
    "title": "Software Engineer",
    "absolute_url": "https://boards.greenhouse.io/testcompany/jobs/101",
    "content": "<p>Build great software. Full details here.</p>",
    "location": {"name": "Nairobi, Kenya"},
}


class TestGreenhouseRegistration:
    def test_registered(self) -> None:
        # Import triggers registration; re-register for clean test
        AdapterRegistry.register("greenhouse")(GreenhouseAdapter)
        assert AdapterRegistry.get("greenhouse") is GreenhouseAdapter


class TestFetchListings:
    @respx.mock
    async def test_yields_listings(self) -> None:
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json=MOCK_JOBS_RESPONSE))
        adapter = GreenhouseAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json=MOCK_JOBS_RESPONSE))
        adapter = GreenhouseAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.external_id == "101"
        assert first.external_url == "https://boards.greenhouse.io/testcompany/jobs/101"
        assert first.title == "Software Engineer"
        assert first.company_name == "Test Company"
        assert first.raw_json is not None
        assert first.raw_json["id"] == 101

    @respx.mock
    async def test_passes_content_param(self) -> None:
        route = respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json={"jobs": []}))
        adapter = GreenhouseAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert route.called
        request = route.calls[0].request
        assert "content=true" in str(request.url)

    @respx.mock
    async def test_empty_jobs(self) -> None:
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json={"jobs": []}))
        adapter = GreenhouseAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_missing_jobs_key(self) -> None:
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json={}))
        adapter = GreenhouseAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0


class TestFetchDetail:
    @respx.mock
    async def test_skips_if_content_present(self) -> None:
        adapter = GreenhouseAdapter(request_delay=0)
        listing = RawListing(
            external_id="101",
            external_url="https://boards.greenhouse.io/testcompany/jobs/101",
            raw_json={"id": 101, "content": "<p>Already has content</p>"},
            company_name="Test Company",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_json is not None
        assert result.raw_json["content"] == "<p>Already has content</p>"
        assert respx.calls.call_count == 0

    @respx.mock
    async def test_fetches_when_no_content(self) -> None:
        detail_url = f"{BOARDS_API}/{BOARD_TOKEN}/jobs/101"
        respx.get(detail_url).mock(return_value=httpx.Response(200, json=MOCK_SINGLE_JOB))

        adapter = GreenhouseAdapter(request_delay=0)
        listing = RawListing(
            external_id="101",
            external_url="https://boards.greenhouse.io/testcompany/jobs/101",
            raw_json={"id": 101, "title": "Software Engineer"},
            company_name="Test Company",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_json is not None
        assert "Full details" in result.raw_json["content"]

    @respx.mock
    async def test_returns_as_is_if_no_external_id(self) -> None:
        adapter = GreenhouseAdapter(request_delay=0)
        listing = RawListing(
            external_url="https://boards.greenhouse.io/testcompany/jobs/101",
            raw_json={"title": "Engineer"},
            company_name="Test Company",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result is listing  # unchanged
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_greenhouse_board_url(self) -> None:
        adapter = GreenhouseAdapter()
        assert adapter.can_handle_url("https://boards.greenhouse.io/oneacrefund/jobs/123")

    def test_greenhouse_api_url(self) -> None:
        adapter = GreenhouseAdapter()
        assert adapter.can_handle_url("https://boards-api.greenhouse.io/v1/boards/oneacrefund")

    def test_non_greenhouse_url(self) -> None:
        adapter = GreenhouseAdapter()
        assert not adapter.can_handle_url("https://careers.example.com/job/123")

    def test_partial_match(self) -> None:
        adapter = GreenhouseAdapter()
        assert not adapter.can_handle_url("https://notgreenhousey.com/job/1")
