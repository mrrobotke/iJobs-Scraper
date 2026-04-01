"""Tests for AdapterRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import BaseAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class DummyAdapter(BaseAdapter):
    """Minimal adapter for testing registry."""

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        yield RawListing(external_url="https://example.com/job/1")  # pragma: no cover

    def can_handle_url(self, url: str) -> bool:
        return "example.com" in url


class AnotherDummyAdapter(BaseAdapter):
    """Another adapter for testing."""

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        yield RawListing(external_url="https://other.com/job/1")  # pragma: no cover

    def can_handle_url(self, url: str) -> bool:
        return "other.com" in url


class TestAdapterRegistry:
    def test_register_and_get(self) -> None:
        AdapterRegistry.register("dummy")(DummyAdapter)
        assert AdapterRegistry.get("dummy") is DummyAdapter

    def test_register_decorator(self) -> None:
        @AdapterRegistry.register("decorated")
        class DecoratedAdapter(DummyAdapter):
            pass

        assert AdapterRegistry.get("decorated") is DecoratedAdapter

    def test_get_unknown_raises(self) -> None:
        with pytest.raises(AdapterError) as exc_info:
            AdapterRegistry.get("nonexistent")
        assert exc_info.value.retryable is False
        assert "nonexistent" in str(exc_info.value)

    def test_get_unknown_lists_available(self) -> None:
        AdapterRegistry.register("alpha")(DummyAdapter)
        AdapterRegistry.register("beta")(AnotherDummyAdapter)
        with pytest.raises(AdapterError, match="alpha"):
            AdapterRegistry.get("missing")

    def test_detect_from_url_found(self) -> None:
        AdapterRegistry.register("example")(DummyAdapter)
        result = AdapterRegistry.detect_from_url("https://example.com/job/42")
        assert result is DummyAdapter

    def test_detect_from_url_not_found(self) -> None:
        result = AdapterRegistry.detect_from_url("https://unknown.com/job/1")
        assert result is None

    def test_detect_from_url_picks_first_match(self) -> None:
        AdapterRegistry.register("example")(DummyAdapter)
        AdapterRegistry.register("other")(AnotherDummyAdapter)
        result = AdapterRegistry.detect_from_url("https://example.com/job/1")
        assert result is DummyAdapter

    def test_list_adapters(self) -> None:
        AdapterRegistry.register("one")(DummyAdapter)
        AdapterRegistry.register("two")(AnotherDummyAdapter)
        adapters = AdapterRegistry.list_adapters()
        assert "one" in adapters
        assert "two" in adapters
        assert adapters["one"] is DummyAdapter

    def test_list_adapters_returns_copy(self) -> None:
        AdapterRegistry.register("dummy")(DummyAdapter)
        adapters = AdapterRegistry.list_adapters()
        adapters["hacked"] = DummyAdapter  # type: ignore[assignment]
        assert "hacked" not in AdapterRegistry.list_adapters()

    def test_clear(self) -> None:
        AdapterRegistry.register("dummy")(DummyAdapter)
        assert len(AdapterRegistry.list_adapters()) == 1
        AdapterRegistry._clear()
        assert len(AdapterRegistry.list_adapters()) == 0

    def test_register_overwrites(self) -> None:
        AdapterRegistry.register("same")(DummyAdapter)
        AdapterRegistry.register("same")(AnotherDummyAdapter)
        assert AdapterRegistry.get("same") is AnotherDummyAdapter
