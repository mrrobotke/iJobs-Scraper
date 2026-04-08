"""Tests for CareerjetAdapter (v4 API)."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.api.careerjet import (
    CAREERJET_API_URL,
    DEFAULT_PAGESIZE,
    CareerjetAdapter,
)
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig, SourceType


def _make_config(**overrides: Any) -> SourceConfig:
    defaults: dict[str, Any] = {
        "name": "Careerjet Kenya",
        "slug": "careerjet-kenya",
        "adapter": "careerjet",
        "source_type": SourceType.API,
        "base_url": "https://www.careerjet.co.ke",
        "config": {"api_key": "test_api_key_123", "location": "Kenya", "user_ip": "1.2.3.4"},
    }
    defaults.update(overrides)
    return SourceConfig(**defaults)


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


class TestCareerjetRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("careerjet")(CareerjetAdapter)
        assert AdapterRegistry.get("careerjet") is CareerjetAdapter


class TestFetchListings:
    @respx.mock
    async def test_yields_listings(self) -> None:
        route = respx.get(CAREERJET_API_URL).mock(
            return_value=Response(200, json=MOCK_SEARCH_RESPONSE)
        )
        adapter = CareerjetAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2
        assert route.called

    @respx.mock
    async def test_listing_fields(self) -> None:
        respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json=MOCK_SEARCH_RESPONSE))
        adapter = CareerjetAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        first = listings[0]
        assert first.external_id is None
        assert first.external_url == "https://www.careerjet.co.ke/job/123"
        assert first.title == "Software Engineer"
        assert first.company_name == "Careerjet Kenya"
        assert first.raw_json is not None
        assert first.raw_json["company"] == "Tech Corp"

    @respx.mock
    async def test_pagination(self) -> None:
        page1: dict[str, Any] = {
            "jobs": [
                {"title": f"Job {i}", "url": f"https://careerjet.co.ke/job/{i}"}
                for i in range(DEFAULT_PAGESIZE)
            ]
        }
        page2: dict[str, Any] = {
            "jobs": [{"title": "Last Job", "url": "https://careerjet.co.ke/job/99"}]
        }
        route = respx.get(CAREERJET_API_URL).mock(
            side_effect=[Response(200, json=page1), Response(200, json=page2)]
        )
        adapter = CareerjetAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == DEFAULT_PAGESIZE + 1
        assert route.call_count == 2
        assert route.calls[0].request.url.params["page"] == "1"
        assert route.calls[1].request.url.params["page"] == "2"

    @respx.mock
    async def test_empty_results(self) -> None:
        respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json={"jobs": []}))
        adapter = CareerjetAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    @respx.mock
    async def test_skips_job_without_url(self) -> None:
        response: dict[str, Any] = {
            "jobs": [
                {"title": "No URL", "url": ""},
                {"title": "Has URL", "url": "https://careerjet.co.ke/job/1"},
            ]
        }
        respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json=response))
        adapter = CareerjetAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Has URL"

    @respx.mock
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
        respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json=response))
        adapter = CareerjetAdapter(request_delay=0)
        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2

    @respx.mock
    async def test_passes_search_params(self) -> None:
        route = respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json={"jobs": []}))
        adapter = CareerjetAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert route.called
        request = route.calls[0].request
        assert request.url.params["location"] == "Kenya"
        assert request.url.params["locale_code"] == "en_GB"
        assert request.url.params["user_agent"] == "ijobs-scraper/0.1.0"
        # api_key should NOT be in query params — it's in the Authorization header
        assert "api_key" not in request.url.params
        assert "affid" not in request.url.params

    @respx.mock
    async def test_authorization_header(self) -> None:
        """Verify Basic Auth header is sent with the API key."""
        route = respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json={"jobs": []}))
        adapter = CareerjetAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        request = route.calls[0].request
        expected = base64.b64encode(b"test_api_key_123:").decode()
        assert request.headers["authorization"] == f"Basic {expected}"

    @respx.mock
    async def test_referer_header(self) -> None:
        """Verify Referer header is sent with the base_url."""
        route = respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json={"jobs": []}))
        adapter = CareerjetAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        request = route.calls[0].request
        assert request.headers["referer"] == "https://www.careerjet.co.ke"

    @respx.mock
    async def test_user_ip_from_config(self) -> None:
        config = _make_config(
            config={
                "api_key": "test_api_key_123",
                "location": "Kenya",
                "user_ip": "192.168.1.1",
            },
        )
        route = respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json={"jobs": []}))
        adapter = CareerjetAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(config)]

        request = route.calls[0].request
        assert request.url.params["user_ip"] == "192.168.1.1"

    async def test_raises_on_missing_user_ip(self) -> None:
        """Missing user_ip in config should raise AdapterError."""
        config = _make_config(config={"api_key": "test_api_key_123", "location": "Kenya"})
        adapter = CareerjetAdapter(request_delay=0)
        with pytest.raises(AdapterError) as exc_info:
            async for _ in adapter.fetch_listings(config):
                pass
        assert exc_info.value.retryable is False
        assert "user_ip" in str(exc_info.value)

    @respx.mock
    async def test_locale_from_config(self) -> None:
        config = _make_config(
            config={
                "api_key": "test_api_key_123",
                "location": "Kenya",
                "locale": "fr_FR",
                "user_ip": "1.2.3.4",
            },
        )
        route = respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json={"jobs": []}))
        adapter = CareerjetAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(config)]

        request = route.calls[0].request
        assert request.url.params["locale_code"] == "fr_FR"

    @respx.mock
    async def test_raises_on_api_error_response(self) -> None:
        """API error responses should raise AdapterError with retryable=True."""
        error_result: dict[str, Any] = {"type": "ERROR", "error": "Invalid API key"}
        respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json=error_result))
        adapter = CareerjetAdapter(request_delay=0)
        with pytest.raises(AdapterError) as exc_info:
            async for _ in adapter.fetch_listings(_make_config()):
                pass
        assert exc_info.value.retryable is True
        assert "Invalid API key" in str(exc_info.value)

    @respx.mock
    async def test_max_pages_cap(self) -> None:
        """Adapter should stop after MAX_PAGES even if API returns full pages."""
        full_page_jobs: list[dict[str, Any]] = [MOCK_JOB for _ in range(DEFAULT_PAGESIZE)]
        respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json={"jobs": full_page_jobs}))
        with patch("ijobs_scraper.adapters.api.careerjet.MAX_PAGES", 3):
            adapter = CareerjetAdapter(request_delay=0)
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]
        assert len(listings) == DEFAULT_PAGESIZE * 3

    @respx.mock
    async def test_raises_on_missing_api_key(self) -> None:
        config = _make_config(config={"location": "Kenya"})  # no api_key
        adapter = CareerjetAdapter(request_delay=0)
        with pytest.raises(AdapterError) as exc_info:
            async for _ in adapter.fetch_listings(config):
                pass
        assert exc_info.value.retryable is False
        assert "api_key" in str(exc_info.value)

    @respx.mock
    async def test_raises_rate_limit_error_on_429(self) -> None:
        from ijobs_scraper.exceptions import RateLimitError

        respx.get(CAREERJET_API_URL).mock(return_value=Response(429, headers={"Retry-After": "60"}))
        adapter = CareerjetAdapter(request_delay=0)
        with pytest.raises(RateLimitError):
            async for _ in adapter.fetch_listings(_make_config()):
                pass

    @respx.mock
    async def test_raises_on_http_500(self) -> None:
        import httpx as httpx_mod

        respx.get(CAREERJET_API_URL).mock(return_value=Response(500))
        adapter = CareerjetAdapter(request_delay=0)
        with pytest.raises(httpx_mod.HTTPStatusError):
            async for _ in adapter.fetch_listings(_make_config()):
                pass

    @respx.mock
    async def test_keywords_from_config(self) -> None:
        config = _make_config(
            config={
                "api_key": "test_api_key_123",
                "keywords": "python developer",
                "user_ip": "1.2.3.4",
            }
        )
        route = respx.get(CAREERJET_API_URL).mock(return_value=Response(200, json={"jobs": []}))
        adapter = CareerjetAdapter(request_delay=0)
        _ = [listing async for listing in adapter.fetch_listings(config)]
        assert route.calls[0].request.url.params["keywords"] == "python developer"


class TestFetchDetail:
    async def test_returns_listing_unchanged(self) -> None:
        """Careerjet has no detail endpoint; listing passes through."""
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


def _load_env_key(key: str) -> str | None:
    """Load a key from env var, falling back to .env.local/.env files."""
    value = os.environ.get(key)
    if value:
        return value
    for env_file in (".env.local", ".env"):
        path = Path(__file__).resolve().parents[2] / env_file
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == key:
                    return v.strip()
    return None


class TestLiveCareerjetIntegration:
    @pytest.mark.live
    async def test_fetches_real_listings(self) -> None:
        """Smoke test against the real Careerjet v4 API."""
        api_key = _load_env_key("CAREERJET_API_KEY")
        if not api_key:
            pytest.skip("CAREERJET_API_KEY not set (env var or .env.local)")

        config = SourceConfig(
            name="Careerjet Kenya",
            slug="careerjet-kenya",
            adapter="careerjet",
            source_type=SourceType.API,
            base_url="https://www.careerjet.co.ke",
            config={"api_key": api_key, "location": "Kenya", "user_ip": "127.0.0.1"},
        )
        adapter = CareerjetAdapter()
        listings = [listing async for listing in adapter.fetch_listings(config)]
        assert len(listings) >= 1
        for listing in listings:
            assert listing.external_url
            assert listing.title
