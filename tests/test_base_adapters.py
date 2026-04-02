"""Tests for BaseAdapter, HTMLAdapter, and BrowserAdapter base class features."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from ijobs_scraper.adapters.base import BaseAdapter, BrowserAdapter, HTMLAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _ConcreteHTMLAdapter(HTMLAdapter):
    """Minimal concrete adapter for testing base class methods."""

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        yield RawListing(external_url="https://example.com/job/1")  # pragma: no cover


class _ConcreteBrowserAdapter(BrowserAdapter):
    """Minimal concrete adapter for testing base class methods."""

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        yield RawListing(external_url="https://example.com/job/1")  # pragma: no cover


class TestValidateUrl:
    """Tests for BaseAdapter._validate_url SSRF protection."""

    def test_valid_https(self) -> None:
        result = BaseAdapter._validate_url("https://www.example.com/jobs", "example.com")
        assert result == "https://www.example.com/jobs"

    def test_valid_http(self) -> None:
        result = BaseAdapter._validate_url("http://www.example.com/jobs", "example.com")
        assert result == "http://www.example.com/jobs"

    def test_exact_host_match(self) -> None:
        result = BaseAdapter._validate_url("https://example.com/jobs", "example.com")
        assert result == "https://example.com/jobs"

    def test_subdomain_match(self) -> None:
        result = BaseAdapter._validate_url("https://www.example.com/jobs", "example.com")
        assert result == "https://www.example.com/jobs"

    def test_rejects_ftp_scheme(self) -> None:
        assert BaseAdapter._validate_url("ftp://example.com/file", "example.com") is None

    def test_rejects_javascript_scheme(self) -> None:
        assert BaseAdapter._validate_url("javascript:alert(1)", "example.com") is None

    def test_rejects_data_scheme(self) -> None:
        assert BaseAdapter._validate_url("data:text/html,<h1>hi</h1>", "example.com") is None

    def test_rejects_wrong_host(self) -> None:
        assert BaseAdapter._validate_url("https://evil.com/steal", "example.com") is None

    def test_rejects_host_suffix_spoof(self) -> None:
        """Attacker registers example.com.evil.com — must be rejected."""
        assert (
            BaseAdapter._validate_url("https://example.com.evil.com/steal", "example.com") is None
        )

    def test_rejects_host_prefix_spoof(self) -> None:
        """Attacker uses evil-example.com — must be rejected."""
        assert BaseAdapter._validate_url("https://evil-example.com/jobs", "example.com") is None

    def test_rejects_empty_url(self) -> None:
        assert BaseAdapter._validate_url("", "example.com") is None

    def test_handles_url_with_port(self) -> None:
        result = BaseAdapter._validate_url("https://example.com:8080/jobs", "example.com")
        assert result == "https://example.com:8080/jobs"

    def test_rejects_no_scheme(self) -> None:
        assert BaseAdapter._validate_url("//example.com/jobs", "example.com") is None

    def test_real_portal_brightermonday(self) -> None:
        result = BaseAdapter._validate_url(
            "https://www.brightermonday.co.ke/listings/job-123",
            "brightermonday.co.ke",
        )
        assert result is not None

    def test_real_portal_spoof_rejected(self) -> None:
        assert (
            BaseAdapter._validate_url(
                "https://brightermonday.co.ke.evil.com/steal",
                "brightermonday.co.ke",
            )
            is None
        )


class TestMaxResponseSize:
    """Tests for HTMLAdapter._fetch_page response size limit."""

    @respx.mock
    async def test_rejects_oversized_content_length_header(self) -> None:
        url = "https://example.com/huge"
        size = HTMLAdapter.MAX_RESPONSE_SIZE + 1
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                content=b"small body",
                headers={"content-length": str(size)},
            ),
        )
        adapter = _ConcreteHTMLAdapter(request_delay=0, jitter=0)

        with pytest.raises(AdapterError, match="Response too large"):
            await adapter._fetch_page(url)

    @respx.mock
    async def test_rejects_oversized_body(self) -> None:
        url = "https://example.com/huge"
        oversized = b"x" * (HTMLAdapter.MAX_RESPONSE_SIZE + 1)
        respx.get(url).mock(
            return_value=httpx.Response(200, content=oversized),
        )
        adapter = _ConcreteHTMLAdapter(request_delay=0, jitter=0)

        with pytest.raises(AdapterError, match="Response too large"):
            await adapter._fetch_page(url)

    @respx.mock
    async def test_accepts_normal_response(self) -> None:
        url = "https://example.com/normal"
        respx.get(url).mock(
            return_value=httpx.Response(200, text="<html><body>OK</body></html>"),
        )
        adapter = _ConcreteHTMLAdapter(request_delay=0, jitter=0)
        soup = await adapter._fetch_page(url)
        assert soup is not None


class TestRequireConfig:
    """Tests for BaseAdapter._require_config (available to all adapter types)."""

    def _config_with(self, **kwargs: object) -> SourceConfig:
        return SourceConfig(
            name="Test",
            slug="test",
            adapter="test",
            source_type="browser",
            base_url="https://example.com",
            config=dict(kwargs),
        )

    def test_returns_string_value(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        config = self._config_with(my_key="my_value")
        assert adapter._require_config(config, "my_key") == "my_value"

    def test_html_adapter_also_has_require_config(self) -> None:
        adapter = _ConcreteHTMLAdapter(request_delay=0, jitter=0)
        config = self._config_with(token="abc")
        assert adapter._require_config(config, "token") == "abc"

    def test_missing_key_raises_adapter_error(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        config = self._config_with()
        with pytest.raises(AdapterError, match="Missing required config key 'board_token'"):
            adapter._require_config(config, "board_token")

    def test_non_string_value_raises_adapter_error(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        config = self._config_with(count=42)
        with pytest.raises(AdapterError, match="must be a string"):
            adapter._require_config(config, "count")

    def test_not_retryable(self) -> None:
        adapter = _ConcreteBrowserAdapter()
        config = self._config_with()
        with pytest.raises(AdapterError) as exc_info:
            adapter._require_config(config, "key")
        assert exc_info.value.retryable is False
