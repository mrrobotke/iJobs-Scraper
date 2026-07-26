"""Tests for KenyaAirwaysAdapter."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.api.kenya_airways import (
    API_PATH,
    DEFAULT_PAGE_SIZE,
    KenyaAirwaysAdapter,
)
from ijobs_scraper.exceptions import RateLimitError
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://api-irec-prod.kenya-airways.com"
JOBS_URL = f"{BASE_URL}{API_PATH}/JobListing"


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="Kenya Airways",
        slug="kenya-airways",
        adapter="kenya_airways",
        source_type=SourceType.API,
        base_url=BASE_URL,
    )


def _paginated_response(
    jobs: list[dict[str, object]],
    *,
    page_number: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    has_next: bool = False,
    has_previous: bool = False,
    total_records: int | None = None,
    total_pages: int | None = None,
) -> dict[str, object]:
    """Build a paginated API response in the new iRec shape."""
    if total_records is None:
        total_records = len(jobs)
    if total_pages is None:
        total_pages = 1 if jobs else 0
    return {
        "data": jobs,
        "pageNumber": page_number,
        "pageSize": page_size,
        "totalPages": total_pages,
        "totalRecords": total_records,
        "hasPrevious": has_previous,
        "hasNext": has_next,
        "sortBy": None,
        "isDescending": False,
        "searchTerm": None,
    }


MOCK_JOBS = [
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

MOCK_JOBS_RESPONSE = _paginated_response(
    MOCK_JOBS,
    total_records=2,
    total_pages=1,
)

MOCK_PAGE_1 = _paginated_response(
    [
        {
            "id": 2000 + i,
            "title": f"Position {i}",
            "url": f"https://careers.kenya-airways.com/jobs/{2000 + i}",
        }
        for i in range(DEFAULT_PAGE_SIZE)
    ],
    page_number=1,
    has_next=True,
    total_records=DEFAULT_PAGE_SIZE + 3,
    total_pages=2,
)

MOCK_PAGE_2 = _paginated_response(
    [
        {
            "id": 3000 + i,
            "title": f"Position Extra {i}",
            "url": f"https://careers.kenya-airways.com/jobs/{3000 + i}",
        }
        for i in range(3)
    ],
    page_number=2,
    has_previous=True,
    total_records=DEFAULT_PAGE_SIZE + 3,
    total_pages=2,
)

MOCK_DETAIL_RESPONSE = {
    "id": 1001,
    "title": "Captain - Boeing 787",
    "description": "<p>Full job description for Captain role.</p>",
    "location": "Nairobi, Kenya",
    "department": "Flight Operations",
}

DETAIL_URL = f"{BASE_URL}{API_PATH}/1001"


class TestKenyaAirwaysRegistration:
    def test_registered(self) -> None:
        # Re-register after autouse _clean_registry fixture clears the registry
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

        assert len(listings) == DEFAULT_PAGE_SIZE + 3
        assert route.call_count == 2

    @respx.mock
    async def test_empty_data(self) -> None:
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json=_paginated_response([])),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_zero_total_records(self) -> None:
        """Should succeed with zero jobs — legitimate when KQ has no openings."""
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(
                200,
                json=_paginated_response([], total_records=0, total_pages=0),
            ),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_missing_data_key(self) -> None:
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
                json=_paginated_response([{"id": 9999, "title": "Test Role"}]),
            ),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].external_url == "https://careers.kenya-airways.com/jobs/9999"

    @respx.mock
    async def test_max_pages_cap(self) -> None:
        """Adapter should stop after MAX_PAGES even if hasNext is true."""

        full_page = _paginated_response(
            [
                {
                    "id": i,
                    "title": f"Job {i}",
                    "url": f"https://careers.kenya-airways.com/jobs/{i}",
                }
                for i in range(DEFAULT_PAGE_SIZE)
            ],
            has_next=True,
            total_records=DEFAULT_PAGE_SIZE * 10,
            total_pages=10,
        )
        route = respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json=full_page),
        )
        with patch("ijobs_scraper.adapters.api.kenya_airways.MAX_PAGES", 2):
            adapter = KenyaAirwaysAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == DEFAULT_PAGE_SIZE * 2
        assert route.call_count == 2

    @respx.mock
    async def test_stops_when_has_next_false(self) -> None:
        """Adapter should stop pagination when hasNext is false."""
        single_page = _paginated_response(
            [
                {
                    "id": i,
                    "title": f"Job {i}",
                    "url": f"https://careers.kenya-airways.com/jobs/{i}",
                }
                for i in range(DEFAULT_PAGE_SIZE)
            ],
            has_next=False,
            total_records=DEFAULT_PAGE_SIZE,
            total_pages=1,
        )
        route = respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json=single_page),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == DEFAULT_PAGE_SIZE
        assert route.call_count == 1

    @respx.mock
    async def test_unyieldable_listings_with_has_next(self) -> None:
        """MAX_PAGES caps runaway pagination when all listings lack URLs."""
        # Listings with no id and no url — they will all hit the `continue`
        unyieldable_page = _paginated_response(
            [
                {"title": "Ghost Job A"},
                {"title": "Ghost Job B"},
            ],
            has_next=True,
            total_records=100,
            total_pages=50,
        )
        route = respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json=unyieldable_page),
        )
        with patch("ijobs_scraper.adapters.api.kenya_airways.MAX_PAGES", 3):
            adapter = KenyaAirwaysAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0
        assert route.call_count == 3

    @respx.mock
    async def test_pagination_sends_correct_params(self) -> None:
        """Verify pageNumber and pageSize query params are sent correctly."""
        route = respx.get(JOBS_URL)
        route.side_effect = [
            httpx.Response(200, json=MOCK_PAGE_1),
            httpx.Response(200, json=MOCK_PAGE_2),
        ]
        adapter = KenyaAirwaysAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        first_url = respx.calls[0].request.url
        assert "pageNumber=1" in str(first_url)
        assert "pageSize=50" in str(first_url)

        second_url = respx.calls[1].request.url
        assert "pageNumber=2" in str(second_url)
        assert "pageSize=50" in str(second_url)

    @respx.mock
    async def test_rate_limit_during_pagination(self) -> None:
        """HTTP 429 mid-pagination raises RateLimitError."""
        route = respx.get(JOBS_URL)
        route.side_effect = [
            httpx.Response(200, json=MOCK_PAGE_1),
            httpx.Response(429, headers={"Retry-After": "60"}),
        ]
        adapter = KenyaAirwaysAdapter(request_delay=0, max_attempts=1)
        with pytest.raises(RateLimitError) as exc_info:
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]
        assert exc_info.value.retry_after == 60

    @respx.mock
    async def test_server_error_during_pagination(self) -> None:
        """HTTP 500 mid-pagination raises HTTPStatusError."""
        route = respx.get(JOBS_URL)
        route.side_effect = [
            httpx.Response(200, json=MOCK_PAGE_1),
            httpx.Response(500),
        ]
        adapter = KenyaAirwaysAdapter(request_delay=0, max_attempts=1)
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]
        assert exc_info.value.response.status_code == 500

    @respx.mock
    async def test_malformed_listing_skipped(self) -> None:
        """Malformed listings are skipped; valid ones still yielded."""
        page = _paginated_response(
            [
                # A non-dict entry triggers AttributeError on job.get()
                "not-a-dict",  # type: ignore[dict-item]
                {
                    "id": 5001,
                    "title": "Good Listing",
                    "url": "https://careers.kenya-airways.com/jobs/5001",
                },
            ],
        )
        respx.get(JOBS_URL).mock(
            return_value=httpx.Response(200, json=page),
        )
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].external_id == "5001"
        assert listings[0].title == "Good Listing"


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
        respx.get(DETAIL_URL).mock(
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

    async def test_rejects_path_traversal_id(self) -> None:
        """external_id with path traversal chars returns listing unchanged."""
        adapter = KenyaAirwaysAdapter(request_delay=0)
        listing = RawListing(
            external_id="../../admin",
            external_url="https://careers.kenya-airways.com/jobs/test",
            raw_json={"title": "Test"},
            company_name="Kenya Airways",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result is listing  # returned unchanged, no HTTP call made


class TestCanHandleUrl:
    def test_kenya_airways_careers_url(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert adapter.can_handle_url("https://careers.kenya-airways.com/jobs/1001")

    def test_kenya_airways_api_url(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert adapter.can_handle_url("https://api-irec-prod.kenya-airways.com/api/Jobs/JobListing")

    def test_non_kenya_airways_url(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert not adapter.can_handle_url("https://careers.example.com/job/123")

    def test_partial_match(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert not adapter.can_handle_url("https://kenya-airwaysy.com/job/1")

    def test_subdomain_spoof_rejected(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert not adapter.can_handle_url("https://kenya-airways.com.evil.com/job/1")

    def test_valid_subdomain_accepted(self) -> None:
        adapter = KenyaAirwaysAdapter()
        assert adapter.can_handle_url("https://careers.kenya-airways.com/jobs/123")
