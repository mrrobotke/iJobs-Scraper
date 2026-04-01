"""Tests for CareerjetAdapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.api.careerjet import DEFAULT_PAGESIZE, CareerjetAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import SourceConfig, SourceType


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="Careerjet Kenya",
        slug="careerjet-kenya",
        adapter="careerjet",
        source_type=SourceType.API,
        base_url="https://www.careerjet.co.ke",
        config={"affid": "test123", "location": "Kenya"},
    )


MOCK_SEARCH_RESPONSE: dict[str, Any] = {
    "type": "JOBS",
    "hits": 2,
    "pages": 1,
    "jobs": [
        {
            "title": "Software Engineer",
            "company": "Tech Corp",
            "url": "https://www.careerjet.co.ke/job/123",
            "description": "Build great software.",
            "date": "2024-01-15",
            "locations": "Nairobi, Kenya",
            "salary": "KES 100,000 - 150,000",
            "site": "techcorp.com",
        },
        {
            "title": "Data Analyst",
            "company": "Data Inc",
            "url": "https://www.careerjet.co.ke/job/456",
            "description": "Analyze data and reports.",
            "date": "2024-01-14",
            "locations": "Mombasa, Kenya",
            "salary": "",
            "site": "datainc.com",
        },
    ],
}

MOCK_JOB: dict[str, Any] = {
    "title": "Software Engineer",
    "company": "Tech Corp",
    "url": "https://www.careerjet.co.ke/job/123",
    "description": "Build great software.",
    "date": "2024-01-15",
    "locations": "Nairobi, Kenya",
    "salary": "KES 100,000 - 150,000",
    "site": "techcorp.com",
}


def _mock_careerjet_module(
    search_results: list[dict[str, Any]] | dict[str, Any],
) -> MagicMock:
    """Create a mock careerjet_api module with configured search results."""
    mock_module = MagicMock()
    mock_client = MagicMock()
    if isinstance(search_results, list):
        mock_client.search.side_effect = search_results
    else:
        mock_client.search.return_value = search_results
    mock_module.CareerjetAPIClient.return_value = mock_client
    return mock_module


class TestCareerjetRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("careerjet")(CareerjetAdapter)
        assert AdapterRegistry.get("careerjet") is CareerjetAdapter


class TestCareerjetImportError:
    async def test_raises_when_sdk_missing(self) -> None:
        with patch.dict("sys.modules", {"careerjet_api": None}):
            adapter = CareerjetAdapter(request_delay=0)
            with pytest.raises(AdapterError) as exc_info:
                async for _ in adapter.fetch_listings(_make_config()):
                    pass
            assert not exc_info.value.retryable
            assert "careerjet-api is required" in str(exc_info.value)


class TestFetchListings:
    async def test_yields_listings(self) -> None:
        mock_mod = _mock_careerjet_module(MOCK_SEARCH_RESPONSE)
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    async def test_listing_fields(self) -> None:
        mock_mod = _mock_careerjet_module(MOCK_SEARCH_RESPONSE)
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.external_id is None
        assert first.external_url == "https://www.careerjet.co.ke/job/123"
        assert first.title == "Software Engineer"
        assert first.company_name == "Careerjet Kenya"
        assert first.raw_json is not None
        assert first.raw_json["company"] == "Tech Corp"

    async def test_pagination(self) -> None:
        page1: dict[str, Any] = {
            "jobs": [
                {"title": f"Job {i}", "url": f"https://careerjet.co.ke/job/{i}"} for i in range(2)
            ]
        }
        page2: dict[str, Any] = {
            "jobs": [{"title": "Last Job", "url": "https://careerjet.co.ke/job/99"}]
        }
        mock_mod = _mock_careerjet_module([page1, page2])
        with (
            patch.dict("sys.modules", {"careerjet_api": mock_mod}),
            patch(
                "ijobs_scraper.adapters.api.careerjet.DEFAULT_PAGESIZE",
                2,
            ),
        ):
            adapter = CareerjetAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 3
        client = mock_mod.CareerjetAPIClient.return_value
        assert client.search.call_count == 2

    async def test_empty_results(self) -> None:
        mock_mod = _mock_careerjet_module({"jobs": []})
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    async def test_skips_job_without_url(self) -> None:
        response: dict[str, Any] = {
            "jobs": [
                {"title": "No URL", "url": ""},
                {"title": "Has URL", "url": "https://careerjet.co.ke/job/1"},
            ]
        }
        mock_mod = _mock_careerjet_module(response)
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Has URL"

    async def test_skips_malformed_listing(self) -> None:
        """Adapter should skip bad listings and continue."""
        response: dict[str, Any] = {
            "jobs": [
                {
                    "title": "Good Job",
                    "url": "https://www.careerjet.co.ke/job/1",
                    "company": "Corp",
                    "description": "Desc",
                    "date": "2024-01-01",
                    "locations": "Nairobi",
                    "salary": "100K",
                    "site": "example.com",
                },
                None,  # type: ignore[list-item]  # Malformed entry
                {
                    "title": "Another Job",
                    "url": "https://www.careerjet.co.ke/job/2",
                    "company": "Corp2",
                    "description": "Desc2",
                    "date": "2024-01-02",
                    "locations": "Mombasa",
                    "salary": "",
                    "site": "example2.com",
                },
            ]
        }
        mock_mod = _mock_careerjet_module(response)
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    async def test_passes_search_params(self) -> None:
        mock_mod = _mock_careerjet_module({"jobs": []})
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        client = mock_mod.CareerjetAPIClient.return_value
        assert client.search.called
        params = client.search.call_args[0][0]
        assert params["affid"] == "test123"
        assert params["location"] == "Kenya"
        assert params["pagesize"] == DEFAULT_PAGESIZE

    async def test_user_ip_from_config(self) -> None:
        config = SourceConfig(
            name="Careerjet Kenya",
            slug="careerjet-kenya",
            adapter="careerjet",
            source_type=SourceType.API,
            base_url="https://www.careerjet.co.ke",
            config={"affid": "test123", "location": "Kenya", "user_ip": "192.168.1.1"},
        )
        mock_mod = _mock_careerjet_module({"jobs": []})
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            _ = [listing async for listing in adapter.fetch_listings(config)]

        client = mock_mod.CareerjetAPIClient.return_value
        params = client.search.call_args[0][0]
        assert params["user_ip"] == "192.168.1.1"

    async def test_user_ip_default(self) -> None:
        mock_mod = _mock_careerjet_module({"jobs": []})
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        client = mock_mod.CareerjetAPIClient.return_value
        params = client.search.call_args[0][0]
        assert params["user_ip"] == "0.0.0.0"

    async def test_sdk_initialized_with_locale(self) -> None:
        mock_mod = _mock_careerjet_module({"jobs": []})
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        mock_mod.CareerjetAPIClient.assert_called_once_with("en_KE")

    async def test_raises_on_sdk_error_response(self) -> None:
        """SDK error responses should raise AdapterError with retryable=True."""
        error_result: dict[str, Any] = {"type": "error", "error": "Invalid affiliate ID"}
        mock_mod = _mock_careerjet_module(error_result)
        with patch.dict("sys.modules", {"careerjet_api": mock_mod}):
            adapter = CareerjetAdapter(request_delay=0)
            with pytest.raises(AdapterError) as exc_info:
                async for _ in adapter.fetch_listings(_make_config()):
                    pass
            assert exc_info.value.retryable is True
            assert "Invalid affiliate ID" in str(exc_info.value)

    async def test_uses_to_thread_for_sdk_call(self) -> None:
        """SDK call must go through asyncio.to_thread to avoid blocking event loop."""
        import asyncio

        mock_mod = _mock_careerjet_module(MOCK_SEARCH_RESPONSE)
        with (
            patch.dict("sys.modules", {"careerjet_api": mock_mod}),
            patch("asyncio.to_thread", wraps=asyncio.to_thread) as mock_to_thread,
        ):
            adapter = CareerjetAdapter(request_delay=0)
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]
        assert mock_to_thread.called

    async def test_max_pages_cap(self) -> None:
        """Adapter should stop after MAX_PAGES even if SDK returns full pages."""
        full_page_jobs: list[dict[str, Any]] = [MOCK_JOB for _ in range(DEFAULT_PAGESIZE)]
        mock_mod = _mock_careerjet_module({"jobs": full_page_jobs})
        with (
            patch.dict("sys.modules", {"careerjet_api": mock_mod}),
            patch("ijobs_scraper.adapters.api.careerjet.MAX_PAGES", 3),
        ):
            adapter = CareerjetAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]
        assert len(listings) == DEFAULT_PAGESIZE * 2


class TestFetchDetail:
    async def test_returns_listing_unchanged(self) -> None:
        """Careerjet has no detail endpoint; listing passes through."""
        from ijobs_scraper.models import RawListing

        adapter = CareerjetAdapter(request_delay=0)
        listing = RawListing(
            external_url="https://www.careerjet.co.ke/job/123",
            title="Test Job",
            company_name="Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result is listing


class TestCanHandleUrl:
    def test_careerjet_ke(self) -> None:
        adapter = CareerjetAdapter()
        assert adapter.can_handle_url("https://www.careerjet.co.ke/job/123")

    def test_careerjet_com(self) -> None:
        adapter = CareerjetAdapter()
        assert adapter.can_handle_url("https://www.careerjet.com/job/123")

    def test_non_careerjet(self) -> None:
        adapter = CareerjetAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
