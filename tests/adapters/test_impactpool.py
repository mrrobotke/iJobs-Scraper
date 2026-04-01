"""Tests for ImpactpoolAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.browser.impactpool import ImpactpoolAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://www.impactpool.org"


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="Impactpool",
        slug="impactpool",
        adapter="impactpool",
        source_type=SourceType.BROWSER,
        base_url=BASE_URL,
    )


def _make_mock_card(
    title: str = "Programme Manager",
    href: str = "/jobs/programme-manager-12345",
    org: str | None = "UNDP",
) -> AsyncMock:
    """Create a mock Playwright element handle for a job card."""
    card = AsyncMock()
    card.get_attribute = AsyncMock(return_value=href)

    # Title element
    title_el = AsyncMock()
    title_el.text_content = AsyncMock(return_value=title)
    card.query_selector = AsyncMock(return_value=title_el)

    # Organization element (second query_selector call)
    if org:
        org_el = AsyncMock()
        org_el.text_content = AsyncMock(return_value=org)
        # First call returns title_el, subsequent calls for org
        card.query_selector = AsyncMock(side_effect=[title_el, org_el])
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


class TestImpactpoolRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("impactpool")(ImpactpoolAdapter)
        assert AdapterRegistry.get("impactpool") is ImpactpoolAdapter


class TestFetchListings:
    async def test_parses_single_page(self) -> None:
        cards = [
            _make_mock_card("Programme Manager", "/jobs/pm-001", "UNDP"),
            _make_mock_card("M&E Officer", "/jobs/me-002", "UNICEF"),
        ]
        mock_page = _make_mock_page(cards=cards)

        adapter = ImpactpoolAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2
        assert listings[0].title == "Programme Manager"
        assert listings[0].company_name == "UNDP"
        assert listings[1].title == "M&E Officer"
        assert listings[1].company_name == "UNICEF"

    async def test_external_urls_are_absolute(self) -> None:
        card = _make_mock_card("Test Job", "/jobs/test-123")
        mock_page = _make_mock_page(cards=[card])

        adapter = ImpactpoolAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].external_url.startswith("https://www.impactpool.org")

    async def test_skips_card_without_jobs_href(self) -> None:
        card = _make_mock_card("About Us", "/about")
        mock_page = _make_mock_page(cards=[card])

        adapter = ImpactpoolAdapter(page_timeout=5.0, nav_delay=0)
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

        adapter = ImpactpoolAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    async def test_empty_page_returns_nothing(self) -> None:
        mock_page = _make_mock_page(cards=[])
        mock_page.wait_for_selector = AsyncMock(side_effect=TimeoutError("no cards"))

        adapter = ImpactpoolAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    async def test_fallback_company_name(self) -> None:
        """Falls back to config.name when no org element is found."""
        card = _make_mock_card("Data Analyst", "/jobs/da-001", org=None)
        mock_page = _make_mock_page(cards=[card])

        adapter = ImpactpoolAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].company_name == "Impactpool"

    async def test_browser_cleanup_on_error(self) -> None:
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=RuntimeError("connection failed"))

        adapter = ImpactpoolAdapter(page_timeout=5.0, nav_delay=0)
        close_mock = AsyncMock()
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", close_mock),
            pytest.raises(RuntimeError, match="connection failed"),
        ):
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        close_mock.assert_awaited_once()


class TestFetchDetail:
    async def test_fetches_detail_page(self) -> None:
        detail_el = AsyncMock()
        detail_el.inner_html = AsyncMock(return_value="<p>Lead monitoring and evaluation</p>")
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=detail_el)

        adapter = ImpactpoolAdapter(page_timeout=5.0, nav_delay=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/jobs/me-officer-001",
            title="M&E Officer",
            company_name="UNDP",
        )
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "monitoring and evaluation" in result.raw_html

    async def test_skips_if_already_has_detail(self) -> None:
        adapter = ImpactpoolAdapter()
        listing = RawListing(
            external_url=f"{BASE_URL}/jobs/test-001",
            title="Test Job",
            company_name="Test Org",
            raw_html="<div>Already loaded</div>",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result.raw_html == "<div>Already loaded</div>"

    async def test_rejects_external_host(self) -> None:
        adapter = ImpactpoolAdapter()
        listing = RawListing(
            external_url="https://evil.com/steal",
            title="Bad Job",
            company_name="Evil Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result.raw_html is None


class TestCanHandleUrl:
    def test_impactpool_url(self) -> None:
        adapter = ImpactpoolAdapter()
        assert adapter.can_handle_url("https://www.impactpool.org/jobs/pm-12345")

    def test_non_impactpool_url(self) -> None:
        adapter = ImpactpoolAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
