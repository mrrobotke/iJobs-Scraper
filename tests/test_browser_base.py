"""Tests for BrowserAdapter base class behavior.

Tests the default fetch_detail, can_handle_url, _launch_browser, and
_close_browser methods provided by the BrowserAdapter base class.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from ijobs_scraper.adapters.base import BrowserAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _ConcreteBrowserAdapter(BrowserAdapter):
    """Concrete adapter for testing base class methods."""

    _host_suffix = "example.com"
    _detail_selector = ".job-detail"
    _detail_min_length = 100

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        yield RawListing(external_url="https://example.com/job/1")  # pragma: no cover


class _NoHostAdapter(BrowserAdapter):
    """Adapter with no host suffix configured."""

    _detail_selector = ".job-detail"

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        yield RawListing(external_url="https://example.com/job/1")  # pragma: no cover


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="Test Portal",
        slug="test-portal",
        adapter="test",
        source_type=SourceType.BROWSER,
        base_url="https://example.com",
    )


class TestLaunchBrowser:
    async def test_playwright_import_error_raises_adapter_error(self) -> None:
        """_launch_browser raises AdapterError when playwright is not installed."""
        adapter = _ConcreteBrowserAdapter()

        with patch.dict(sys.modules, {"playwright": None, "playwright.async_api": None}):
            with pytest.raises(AdapterError, match="playwright is required"):
                await adapter._launch_browser()


class TestCloseBrowser:
    async def test_closes_all_resources_in_order(self) -> None:
        """_close_browser closes context, browser, and pw in order."""
        adapter = _ConcreteBrowserAdapter()
        call_order: list[str] = []

        async def track_context() -> None:
            call_order.append("context")

        async def track_browser() -> None:
            call_order.append("browser")

        async def track_pw() -> None:
            call_order.append("pw")

        adapter._context = AsyncMock()
        adapter._context.close = track_context
        adapter._browser = AsyncMock()
        adapter._browser.close = track_browser
        adapter._pw = AsyncMock()
        adapter._pw.stop = track_pw

        await adapter._close_browser()

        assert call_order == ["context", "browser", "pw"]
        assert adapter._context is None
        assert adapter._browser is None
        assert adapter._pw is None

    async def test_context_error_propagates(self) -> None:
        """Error in context.close propagates (not silently swallowed)."""
        adapter = _ConcreteBrowserAdapter()
        adapter._context = AsyncMock()
        adapter._context.close = AsyncMock(
            side_effect=RuntimeError("context close failed"),
        )
        adapter._browser = AsyncMock()
        adapter._pw = AsyncMock()

        with pytest.raises(RuntimeError, match="context close failed"):
            await adapter._close_browser()

    async def test_handles_all_none(self) -> None:
        """_close_browser handles the case where no resources were created."""
        adapter = _ConcreteBrowserAdapter()
        adapter._pw = None
        adapter._browser = None
        adapter._context = None
        # Should complete without error
        await adapter._close_browser()


class TestFetchDetailBaseClass:
    """Tests for BrowserAdapter.fetch_detail (inherits default from BaseAdapter)."""

    async def test_returns_listing_unchanged(self) -> None:
        """Base fetch_detail returns the listing as-is (no override in BrowserAdapter)."""
        adapter = _ConcreteBrowserAdapter()
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result is listing

    async def test_returns_listing_with_html(self) -> None:
        """Base fetch_detail preserves existing raw_html."""
        adapter = _ConcreteBrowserAdapter()
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
            raw_html="<div>existing content</div>",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result is listing
        assert result.raw_html == "<div>existing content</div>"


class TestValidateUrl:
    """Tests for _validate_url SSRF protection (static method on BaseAdapter)."""

    def test_valid_http_url(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        result = adapter._validate_url("https://www.example.com/job/1", "example.com")
        assert result == "https://www.example.com/job/1"

    def test_rejects_non_http_scheme(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        assert adapter._validate_url("ftp://example.com/job/1", "example.com") is None

    def test_rejects_mismatched_host(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        assert adapter._validate_url("https://evil.com/job/1", "example.com") is None

    def test_subdomain_matches(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        result = adapter._validate_url("https://careers.example.com/job/1", "example.com")
        assert result == "https://careers.example.com/job/1"

    def test_rejects_host_suffix_spoof(self) -> None:
        """example.com.evil.com should NOT match example.com."""
        adapter = _ConcreteBrowserAdapter()
        assert adapter._validate_url(
            "https://example.com.evil.com/job/1", "example.com"
        ) is None



class TestCanHandleUrl:
    """Tests for BrowserAdapter.can_handle_url base class implementation."""

    def test_matching_host(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        assert adapter.can_handle_url("https://www.example.com/job/1")

    def test_exact_host(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        assert adapter.can_handle_url("https://example.com/job/1")

    def test_non_matching_host(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        assert not adapter.can_handle_url("https://evil.com/job/1")

    def test_empty_host_suffix_returns_false(self) -> None:
        """Adapter with empty _host_suffix always returns False."""
        adapter = _NoHostAdapter()
        assert not adapter.can_handle_url("https://example.com/job/1")


class TestRequireConfig:
    """Tests for _require_config on BaseAdapter (accessible from BrowserAdapter)."""

    def test_returns_value(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        config = _make_config()
        config.config["my_key"] = "my_value"
        assert adapter._require_config(config, "my_key") == "my_value"

    def test_missing_key_raises(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        config = _make_config()
        with pytest.raises(AdapterError, match="my_key"):
            adapter._require_config(config, "my_key")

    def test_non_string_value_raises(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        config = _make_config()
        config.config["my_key"] = 42
        with pytest.raises(AdapterError, match="must be a string"):
            adapter._require_config(config, "my_key")
