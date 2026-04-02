"""Tests for BrowserAdapter base class behavior.

Tests the default fetch_detail, can_handle_url, _launch_browser, and
_close_browser methods provided by the BrowserAdapter base class.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

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

        with (
            patch.dict(sys.modules, {"playwright": None, "playwright.async_api": None}),
            pytest.raises(AdapterError, match="playwright is required"),
        ):
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

    async def test_per_step_error_handling(self) -> None:
        """Each cleanup step handles errors independently."""
        adapter = _ConcreteBrowserAdapter()
        adapter._context = AsyncMock()
        adapter._context.close = AsyncMock(
            side_effect=RuntimeError("context close failed"),
        )
        adapter._browser = AsyncMock()
        adapter._browser.close = AsyncMock()
        adapter._pw = AsyncMock()
        adapter._pw.stop = AsyncMock()

        browser_mock = adapter._browser
        pw_mock = adapter._pw

        # Should NOT raise despite context.close failing
        await adapter._close_browser()

        # Browser and playwright should still have been closed
        browser_mock.close.assert_awaited_once()
        pw_mock.stop.assert_awaited_once()
        assert adapter._context is None
        assert adapter._browser is None
        assert adapter._pw is None

    async def test_timeout_handling(self) -> None:
        """Cleanup handles stuck resources via timeout."""
        adapter = _ConcreteBrowserAdapter()
        adapter._context = AsyncMock()
        adapter._browser = AsyncMock()
        adapter._pw = None

        with patch("ijobs_scraper.adapters.base.asyncio.wait_for") as mock_wf:
            mock_wf.side_effect = TimeoutError()
            await adapter._close_browser()

        assert adapter._context is None
        assert adapter._browser is None

    async def test_handles_all_none(self) -> None:
        """_close_browser handles the case where no resources were created."""
        adapter = _ConcreteBrowserAdapter()
        adapter._pw = None
        adapter._browser = None
        adapter._context = None
        # Should complete without error
        await adapter._close_browser()


class _NoSelectorAdapter(BrowserAdapter):
    """Adapter with no detail selector configured."""

    _host_suffix = "example.com"

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        yield RawListing(external_url="https://example.com/job/1")  # pragma: no cover


class TestFetchDetailSkipConditions:
    """Tests for the three skip paths in base class fetch_detail."""

    async def test_skip_no_selector_configured(self) -> None:
        """Returns listing as-is when _detail_selector is empty."""
        adapter = _NoSelectorAdapter()
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result is listing

    async def test_skip_no_host_suffix_configured(self) -> None:
        """Returns listing as-is when _host_suffix is empty."""
        adapter = _NoHostAdapter()
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result is listing

    async def test_skip_already_has_sufficient_html(self) -> None:
        """Returns listing as-is when raw_html exceeds _detail_min_length."""
        adapter = _ConcreteBrowserAdapter()  # min_length = 100
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
            raw_html="<div>" + "x" * 200 + "</div>",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result.raw_html == listing.raw_html

    async def test_skip_invalid_host(self) -> None:
        """Returns listing as-is when URL doesn't match expected host."""
        adapter = _ConcreteBrowserAdapter()  # _host_suffix = "example.com"
        listing = RawListing(
            external_url="https://evil.com/steal",
            title="Bad Job",
            company_name="Evil Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result.raw_html is None

    async def test_proceeds_when_html_below_threshold(self) -> None:
        """Does not skip when raw_html exists but is below the minimum length."""
        adapter = _ConcreteBrowserAdapter()  # min_length = 100
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
            raw_html="<h1>Short</h1>",
        )
        # Patch playwright import to simulate ImportError fallback
        with patch.dict(sys.modules, {"playwright": None, "playwright.async_api": None}):
            result = await adapter.fetch_detail(listing, _make_config())
        # ImportError path returns listing unchanged
        assert result.raw_html == "<h1>Short</h1>"


class TestFetchDetailPlaywrightPath:
    """Test the full fetch_detail path with mocked Playwright."""

    async def test_fetches_and_returns_html(self) -> None:
        """Full happy path: launches browser, fetches detail, returns HTML."""
        detail_el = AsyncMock()
        detail_el.inner_html = AsyncMock(return_value="<p>Job details here</p>")

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.set_default_timeout = MagicMock()
        mock_page.query_selector = AsyncMock(return_value=detail_el)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_pw = AsyncMock()
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.stop = AsyncMock()

        mock_async_pw_func = MagicMock()
        mock_async_pw_instance = AsyncMock()
        mock_async_pw_instance.start = AsyncMock(return_value=mock_pw)
        mock_async_pw_func.return_value = mock_async_pw_instance

        adapter = _ConcreteBrowserAdapter(page_timeout=5.0, nav_delay=0)
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
        )

        playwright_mock = MagicMock()
        playwright_mock.async_playwright = mock_async_pw_func

        with patch.dict(
            "sys.modules",
            {
                "playwright": MagicMock(),
                "playwright.async_api": playwright_mock,
            },
        ):
            result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "Job details here" in result.raw_html

    async def test_returns_original_on_playwright_error(self) -> None:
        """Returns original listing when Playwright raises an error."""
        mock_async_pw_func = MagicMock()
        mock_async_pw_instance = AsyncMock()
        mock_async_pw_instance.start = AsyncMock(
            side_effect=RuntimeError("browser crash"),
        )
        mock_async_pw_func.return_value = mock_async_pw_instance

        adapter = _ConcreteBrowserAdapter(page_timeout=5.0, nav_delay=0)
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
        )

        playwright_mock = MagicMock()
        playwright_mock.async_playwright = mock_async_pw_func

        with patch.dict(
            "sys.modules",
            {
                "playwright": MagicMock(),
                "playwright.async_api": playwright_mock,
            },
        ):
            result = await adapter.fetch_detail(listing, _make_config())

        assert result.external_url == listing.external_url

    async def test_detail_element_not_found_returns_original(self) -> None:
        """Returns original listing when detail selector finds nothing."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.set_default_timeout = MagicMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_pw = AsyncMock()
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.stop = AsyncMock()

        mock_async_pw_func = MagicMock()
        mock_async_pw_instance = AsyncMock()
        mock_async_pw_instance.start = AsyncMock(return_value=mock_pw)
        mock_async_pw_func.return_value = mock_async_pw_instance

        adapter = _ConcreteBrowserAdapter(page_timeout=5.0, nav_delay=0)
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
        )

        playwright_mock = MagicMock()
        playwright_mock.async_playwright = mock_async_pw_func

        with patch.dict(
            "sys.modules",
            {
                "playwright": MagicMock(),
                "playwright.async_api": playwright_mock,
            },
        ):
            result = await adapter.fetch_detail(listing, _make_config())

        assert result.external_url == listing.external_url

    async def test_playwright_import_error_returns_original(self) -> None:
        """Returns original listing when playwright is not installed."""
        adapter = _ConcreteBrowserAdapter(page_timeout=5.0, nav_delay=0)
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Test Job",
            company_name="Test Corp",
        )

        with patch.dict(sys.modules, {"playwright": None, "playwright.async_api": None}):
            result = await adapter.fetch_detail(listing, _make_config())

        assert result.external_url == listing.external_url


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
        assert adapter._validate_url("https://example.com.evil.com/job/1", "example.com") is None


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
