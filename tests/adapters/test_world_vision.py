"""Tests for WorldVisionAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.browser.world_vision import WorldVisionAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://careers.wvi.org"


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="World Vision",
        slug="world-vision",
        adapter="world_vision",
        source_type=SourceType.BROWSER,
        base_url=BASE_URL,
    )


def _make_mock_card(
    title: str = "Field Coordinator",
    href: str = "/jobs/field-coordinator-12345",
    location: str | None = "Nairobi, Kenya",
) -> AsyncMock:
    """Create a mock Playwright element handle for a job card."""
    card = AsyncMock()
    card.get_attribute = AsyncMock(return_value=href)

    # Title element
    title_el = AsyncMock()
    title_el.text_content = AsyncMock(return_value=title)

    # Location element
    if location:
        loc_el = AsyncMock()
        loc_el.text_content = AsyncMock(return_value=location)
        card.query_selector = AsyncMock(side_effect=[title_el, loc_el])
    else:
        card.query_selector = AsyncMock(side_effect=[title_el, None])

    return card


def _make_mock_page(
    cards: list[AsyncMock] | None = None,
    has_next: bool = False,
) -> AsyncMock:
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()

    if cards is None:
        cards = [_make_mock_card()]

    page.query_selector_all = AsyncMock(return_value=cards)

    if has_next:
        next_link = AsyncMock()
        next_link.click = AsyncMock()
        page.query_selector = AsyncMock(return_value=next_link)
    else:
        page.query_selector = AsyncMock(return_value=None)

    return page


class TestWorldVisionRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("world_vision")(WorldVisionAdapter)
        assert AdapterRegistry.get("world_vision") is WorldVisionAdapter


class TestFetchListings:
    async def test_parses_single_page(self) -> None:
        cards = [
            _make_mock_card("Field Coordinator", "/jobs/fc-001", "Nairobi, Kenya"),
            _make_mock_card("Finance Officer", "/jobs/fo-002", "Mombasa, Kenya"),
        ]
        mock_page = _make_mock_page(cards=cards)

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2
        assert listings[0].title == "Field Coordinator"
        assert listings[1].title == "Finance Officer"
        assert listings[0].company_name == "World Vision"

    async def test_external_urls_are_absolute(self) -> None:
        card = _make_mock_card("Test Job", "/jobs/test-123")
        mock_page = _make_mock_page(cards=[card])

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].external_url.startswith("https://careers.wvi.org")

    async def test_skips_card_with_no_href(self) -> None:
        card = _make_mock_card("No Link Job")
        card.get_attribute = AsyncMock(return_value=None)
        mock_page = _make_mock_page(cards=[card])

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    async def test_skips_card_with_empty_title(self) -> None:
        card = AsyncMock()
        card.get_attribute = AsyncMock(return_value="/jobs/empty-001")
        title_el = AsyncMock()
        title_el.text_content = AsyncMock(return_value="   ")
        card.query_selector = AsyncMock(side_effect=[title_el, None])

        mock_page = _make_mock_page(cards=[card])

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    async def test_empty_page_returns_nothing(self) -> None:
        mock_page = _make_mock_page(cards=[])
        mock_page.wait_for_selector = AsyncMock(side_effect=TimeoutError("no cards"))

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    async def test_raw_html_includes_location(self) -> None:
        card = _make_mock_card("WASH Officer", "/jobs/wash-001", "Turkana, Kenya")
        mock_page = _make_mock_page(cards=[card])

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert listings[0].raw_html is not None
        assert "Turkana" in listings[0].raw_html

    async def test_browser_cleanup_on_error(self) -> None:
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=RuntimeError("connection failed"))

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        close_mock = AsyncMock()
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", close_mock),
            pytest.raises(RuntimeError, match="connection failed"),
        ):
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        close_mock.assert_awaited_once()

    async def test_pagination_with_turbo(self) -> None:
        """Test Turbo-enhanced pagination via next link."""
        cards_page1 = [_make_mock_card("Job A", "/jobs/a-1")]
        cards_page2 = [_make_mock_card("Job B", "/jobs/b-2")]

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        call_count = 0

        async def query_selector_all_side_effect(selector: str) -> list[AsyncMock]:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return cards_page1
            return cards_page2

        mock_page.query_selector_all = AsyncMock(side_effect=query_selector_all_side_effect)

        next_link = AsyncMock()
        next_link.click = AsyncMock()
        mock_page.query_selector = AsyncMock(side_effect=[next_link, None])

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2
        assert listings[0].title == "Job A"
        assert listings[1].title == "Job B"


class TestFetchDetail:
    async def test_fetches_detail_page(self) -> None:
        detail_el = AsyncMock()
        detail_el.inner_html = AsyncMock(
            return_value="<p>Support community development programs</p>"
        )
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=detail_el)

        adapter = WorldVisionAdapter(page_timeout=5.0, nav_delay=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/jobs/fc-001",
            title="Field Coordinator",
            company_name="World Vision",
        )
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "community development" in result.raw_html

    async def test_skips_if_already_has_detail(self) -> None:
        adapter = WorldVisionAdapter()
        listing = RawListing(
            external_url=f"{BASE_URL}/jobs/test-001",
            title="Test Job",
            company_name="World Vision",
            raw_html="<div>" + "x" * 300 + "</div>",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result.raw_html == listing.raw_html

    async def test_rejects_external_host(self) -> None:
        adapter = WorldVisionAdapter()
        listing = RawListing(
            external_url="https://evil.com/steal",
            title="Bad Job",
            company_name="Evil Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result.raw_html is None


class TestCanHandleUrl:
    def test_world_vision_url(self) -> None:
        adapter = WorldVisionAdapter()
        assert adapter.can_handle_url("https://careers.wvi.org/jobs/fc-12345")

    def test_non_world_vision_url(self) -> None:
        adapter = WorldVisionAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
