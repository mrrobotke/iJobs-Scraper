"""Tests for ReliefWebAdapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.api.reliefweb import (
    ReliefWebAdapter,
)
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

API_BASE = "https://api.reliefweb.int"
JOBS_URL = f"{API_BASE}/v1/jobs"


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="ReliefWeb Kenya",
        slug="reliefweb-kenya",
        adapter="reliefweb",
        source_type=SourceType.API,
        base_url=API_BASE,
        config={"appname": "ijobs-scraper-test"},
    )


MOCK_JOBS_RESPONSE: dict[str, Any] = {
    "totalCount": 2,
    "count": 2,
    "data": [
        {
            "id": "1001",
            "fields": {
                "title": "Programme Officer",
                "body-html": "<p>UN agency seeks officer.</p>",
                "url": "https://reliefweb.int/job/1001",
                "source": [{"name": "UNICEF"}],
                "date": {
                    "created": "2024-01-10T00:00:00+00:00",
                    "closing": "2024-02-10T00:00:00+00:00",
                },
                "country": [{"name": "Kenya"}],
                "theme": [{"name": "Health"}],
                "type": [{"name": "Job"}],
            },
        },
        {
            "id": "1002",
            "fields": {
                "title": "Logistics Coordinator",
                "body-html": "<p>Coordinate logistics operations.</p>",
                "url": "https://reliefweb.int/job/1002",
                "source": [{"name": "WFP"}],
                "date": {
                    "created": "2024-01-12T00:00:00+00:00",
                    "closing": "2024-02-12T00:00:00+00:00",
                },
                "country": [{"name": "Kenya"}],
                "theme": [{"name": "Logistics and Telecommunications"}],
                "type": [{"name": "Job"}],
            },
        },
    ],
}

MOCK_SINGLE_JOB: dict[str, Any] = {
    "data": [
        {
            "id": "1001",
            "fields": {
                "title": "Programme Officer — Full Details",
                "body-html": "<p>Full job description here.</p>",
                "url": "https://reliefweb.int/job/1001",
                "source": [{"name": "UNICEF"}],
                "date": {
                    "created": "2024-01-10T00:00:00+00:00",
                    "closing": "2024-02-10T00:00:00+00:00",
                },
                "country": [{"name": "Kenya"}],
                "theme": [{"name": "Health"}],
                "type": [{"name": "Job"}],
            },
        }
    ]
}


class TestReliefWebRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("reliefweb")(ReliefWebAdapter)
        assert AdapterRegistry.get("reliefweb") is ReliefWebAdapter


class TestFetchListings:
    @respx.mock
    async def test_yields_listings(self) -> None:
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json=MOCK_JOBS_RESPONSE))
        adapter = ReliefWebAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json=MOCK_JOBS_RESPONSE))
        adapter = ReliefWebAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.external_id == "1001"
        assert first.external_url == "https://reliefweb.int/job/1001"
        assert first.title == "Programme Officer"
        assert first.raw_html == "<p>UN agency seeks officer.</p>"
        assert first.company_name == "UNICEF"
        assert first.raw_json is not None

    @respx.mock
    async def test_passes_appname(self) -> None:
        route = respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json={"data": [], "totalCount": 0})
        )
        adapter = ReliefWebAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert route.called
        request = route.calls[0].request
        assert "appname=ijobs-scraper-test" in str(request.url)

    @respx.mock
    async def test_passes_kenya_filter(self) -> None:
        route = respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json={"data": [], "totalCount": 0})
        )
        adapter = ReliefWebAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        request = route.calls[0].request
        url_str = str(request.url)
        assert "filter" in url_str
        assert "country" in url_str

    @respx.mock
    async def test_requests_fields(self) -> None:
        route = respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json={"data": [], "totalCount": 0})
        )
        adapter = ReliefWebAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        request = route.calls[0].request
        url_str = str(request.url)
        assert "fields" in url_str
        assert "title" in url_str

    @respx.mock
    async def test_pagination(self) -> None:
        page1: dict[str, Any] = {
            "totalCount": 3,
            "data": [
                {
                    "id": str(i),
                    "fields": {
                        "title": f"Job {i}",
                        "url": f"https://reliefweb.int/job/{i}",
                        "source": [{"name": "OCHA"}],
                    },
                }
                for i in range(2)
            ],
        }
        page2: dict[str, Any] = {
            "totalCount": 3,
            "data": [
                {
                    "id": "99",
                    "fields": {
                        "title": "Last Job",
                        "url": "https://reliefweb.int/job/99",
                        "source": [{"name": "OCHA"}],
                    },
                }
            ],
        }
        pages = iter([page1, page2])
        respx.get(JOBS_URL).mock(side_effect=lambda req: httpx.Response(200, json=next(pages)))

        with patch("ijobs_scraper.adapters.api.reliefweb.DEFAULT_LIMIT", 2):
            adapter = ReliefWebAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 3

    @respx.mock
    async def test_empty_data(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json={"data": [], "totalCount": 0})
        )
        adapter = ReliefWebAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_missing_data_key(self) -> None:
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json={}))
        adapter = ReliefWebAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_falls_back_to_config_name(self) -> None:
        """When source list is empty, use config.name as company."""
        response: dict[str, Any] = {
            "totalCount": 1,
            "data": [
                {
                    "id": "500",
                    "fields": {
                        "title": "Test Job",
                        "url": "https://reliefweb.int/job/500",
                        "source": [],
                    },
                }
            ],
        }
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json=response))
        adapter = ReliefWebAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].company_name == "ReliefWeb Kenya"

    @respx.mock
    async def test_constructs_url_from_id(self) -> None:
        """When fields.url is missing, construct from item id."""
        response: dict[str, Any] = {
            "totalCount": 1,
            "data": [
                {
                    "id": "777",
                    "fields": {
                        "title": "Test Job",
                        "source": [{"name": "OCHA"}],
                    },
                }
            ],
        }
        respx.get(JOBS_URL).mock(return_value=httpx.Response(200, json=response))
        adapter = ReliefWebAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].external_url == "https://reliefweb.int/job/777"


class TestFetchDetail:
    @respx.mock
    async def test_skips_if_raw_html_present(self) -> None:
        adapter = ReliefWebAdapter(request_delay=0)
        listing = RawListing(
            external_id="1001",
            external_url="https://reliefweb.int/job/1001",
            raw_html="<p>Already has content</p>",
            company_name="UNICEF",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html == "<p>Already has content</p>"
        assert respx.calls.call_count == 0

    @respx.mock
    async def test_fetches_when_no_html(self) -> None:
        detail_url = f"{API_BASE}/v1/jobs/1001"
        respx.get(detail_url).mock(return_value=httpx.Response(200, json=MOCK_SINGLE_JOB))

        adapter = ReliefWebAdapter(request_delay=0)
        listing = RawListing(
            external_id="1001",
            external_url="https://reliefweb.int/job/1001",
            company_name="UNICEF",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html == "<p>Full job description here.</p>"
        assert result.title == "Programme Officer — Full Details"

    @respx.mock
    async def test_returns_as_is_if_no_external_id(self) -> None:
        adapter = ReliefWebAdapter(request_delay=0)
        listing = RawListing(
            external_url="https://reliefweb.int/job/1001",
            company_name="UNICEF",
        )
        result = await adapter.fetch_detail(listing, _make_config())

        assert result is listing
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_reliefweb_url(self) -> None:
        adapter = ReliefWebAdapter()
        assert adapter.can_handle_url("https://reliefweb.int/job/1001")

    def test_api_reliefweb_url(self) -> None:
        adapter = ReliefWebAdapter()
        assert adapter.can_handle_url("https://api.reliefweb.int/v1/jobs")

    def test_non_reliefweb_url(self) -> None:
        adapter = ReliefWebAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
