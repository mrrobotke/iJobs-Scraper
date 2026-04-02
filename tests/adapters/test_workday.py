"""Tests for WorkdayAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.browser.workday import WorkdayAdapter
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://absa.wd3.myworkdayjobs.com"
CAREERS_URL = f"{BASE_URL}/en-US/AbsaCareers/jobs"


def _make_config(
    name: str = "Absa Bank",
    slug: str = "absa",
    tenant: str = "absa",
    instance: str = "AbsaCareers",
    base_url: str = BASE_URL,
) -> SourceConfig:
    return SourceConfig(
        name=name,
        slug=slug,
        adapter="workday",
        source_type=SourceType.BROWSER,
        base_url=base_url,
        config={"tenant": tenant, "instance": instance},
    )


def _make_ncba_config() -> SourceConfig:
    return _make_config(
        name="NCBA Bank",
        slug="ncba",
        tenant="ncba",
        instance="NCBACareers",
        base_url="https://ncba.wd3.myworkdayjobs.com",
    )


def _make_mock_card(
    title: str = "Software Engineer",
    href: str = "/en-US/AbsaCareers/job/Nairobi/Software-Engineer_12345",
    location: str | None = "Nairobi, Kenya",
) -> AsyncMock:
    """Create a mock Playwright element handle for a job card."""
    card = AsyncMock()
    card.text_content = AsyncMock(return_value=title)
    card.get_attribute = AsyncMock(return_value=href)

    # Parent element for location lookup
    parent = AsyncMock()
    if location:
        loc_el = AsyncMock()
        loc_el.text_content = AsyncMock(return_value=location)
        parent.query_selector = AsyncMock(return_value=loc_el)
    else:
        parent.query_selector = AsyncMock(return_value=None)
    card.evaluate_handle = AsyncMock(return_value=parent)

    return card


def _make_mock_page(
    cards: list[AsyncMock] | None = None,
    has_next: bool = False,
) -> AsyncMock:
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.set_default_timeout = MagicMock()

    if cards is None:
        cards = [_make_mock_card()]

    page.query_selector_all = AsyncMock(return_value=cards)

    if has_next:
        next_btn = AsyncMock()
        next_btn.get_attribute = AsyncMock(return_value=None)  # not disabled
        next_btn.click = AsyncMock()
        page.query_selector = AsyncMock(return_value=next_btn)
    else:
        page.query_selector = AsyncMock(return_value=None)

    return page


class TestWorkdayRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("workday")(WorkdayAdapter)
        assert AdapterRegistry.get("workday") is WorkdayAdapter


class TestBuildCareersUrl:
    def test_builds_url(self) -> None:
        adapter = WorkdayAdapter()
        config = _make_config()
        url = adapter._build_careers_url(config)
        assert url == CAREERS_URL

    def test_missing_instance_raises(self) -> None:
        adapter = WorkdayAdapter()
        config = _make_config()
        # Remove the key entirely so _require_config raises
        del config.config["instance"]
        with pytest.raises(AdapterError, match="instance"):
            adapter._build_careers_url(config)


class TestFetchListings:
    async def test_parses_single_page(self) -> None:
        cards = [
            _make_mock_card("Software Engineer", "/en-US/AbsaCareers/job/SE_001"),
            _make_mock_card("Data Analyst", "/en-US/AbsaCareers/job/DA_002"),
        ]
        mock_page = _make_mock_page(cards=cards, has_next=False)

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2
        assert listings[0].title == "Software Engineer"
        assert listings[1].title == "Data Analyst"
        assert listings[0].company_name == "Absa Bank"

    async def test_external_urls_are_absolute(self) -> None:
        card = _make_mock_card("Test Job", "/en-US/AbsaCareers/job/Test_123")
        mock_page = _make_mock_page(cards=[card])

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].external_url.startswith("https://absa.wd3.myworkdayjobs.com")

    async def test_ncba_config_works(self) -> None:
        """Workday adapter is reusable -- NCBA uses same adapter, different config."""
        card = _make_mock_card(
            "Risk Analyst",
            "/en-US/NCBACareers/job/Risk-Analyst_100",
        )
        mock_page = _make_mock_page(cards=[card])

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        config = _make_ncba_config()
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(config)]

        assert len(listings) == 1
        assert listings[0].company_name == "NCBA Bank"
        assert listings[0].title == "Risk Analyst"

    async def test_skips_card_with_no_title(self) -> None:
        bad_card = AsyncMock()
        bad_card.text_content = AsyncMock(return_value=None)
        bad_card.get_attribute = AsyncMock(return_value="/en-US/AbsaCareers/job/X_1")
        bad_card.evaluate_handle = AsyncMock(return_value=AsyncMock())

        good_card = _make_mock_card("Valid Job", "/en-US/AbsaCareers/job/V_2")
        mock_page = _make_mock_page(cards=[bad_card, good_card])

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Valid Job"

    async def test_skips_card_with_no_href(self) -> None:
        card = _make_mock_card("No Link Job")
        card.get_attribute = AsyncMock(return_value=None)
        mock_page = _make_mock_page(cards=[card])

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    async def test_empty_page_returns_nothing(self) -> None:
        mock_page = _make_mock_page(cards=[])
        # Simulate no cards found on wait_for_selector
        mock_page.wait_for_selector = AsyncMock(side_effect=TimeoutError("no cards"))

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 0

    async def test_pagination(self) -> None:
        """Test that adapter follows next button through pages."""
        cards_page1 = [_make_mock_card("Job A", "/en-US/AbsaCareers/job/A_1")]
        cards_page2 = [_make_mock_card("Job B", "/en-US/AbsaCareers/job/B_2")]

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.set_default_timeout = MagicMock()

        call_count = 0

        async def query_selector_all_side_effect(selector: str) -> list[AsyncMock]:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return cards_page1
            return cards_page2

        mock_page.query_selector_all = AsyncMock(side_effect=query_selector_all_side_effect)

        # First call returns next button, second call returns None (end)
        next_btn = AsyncMock()
        next_btn.get_attribute = AsyncMock(return_value=None)
        next_btn.click = AsyncMock()
        mock_page.query_selector = AsyncMock(side_effect=[next_btn, None])

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 2
        assert listings[0].title == "Job A"
        assert listings[1].title == "Job B"

    async def test_raw_html_includes_location(self) -> None:
        card = _make_mock_card(
            "DevOps Engineer",
            "/en-US/AbsaCareers/job/DevOps_1",
            location="Johannesburg, South Africa",
        )
        mock_page = _make_mock_page(cards=[card])

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert listings[0].raw_html is not None
        assert "Johannesburg" in listings[0].raw_html

    async def test_browser_cleanup_on_error(self) -> None:
        """Browser resources are cleaned up even if an error occurs."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=RuntimeError("connection failed"))
        mock_page.set_default_timeout = MagicMock()

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        close_mock = AsyncMock()
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", close_mock),
            pytest.raises(RuntimeError, match="connection failed"),
        ):
            _ = [listing async for listing in adapter.fetch_listings(_make_config())]

        close_mock.assert_awaited_once()

    async def test_per_card_exception_isolation(self) -> None:
        """One card raising an exception should not stop remaining cards."""
        bad_card = AsyncMock()
        bad_card.text_content = AsyncMock(side_effect=RuntimeError("DOM error"))
        bad_card.get_attribute = AsyncMock(return_value="/en-US/AbsaCareers/job/Bad_1")
        bad_card.evaluate_handle = AsyncMock(return_value=AsyncMock())

        good_card = _make_mock_card("Good Job", "/en-US/AbsaCareers/job/Good_2")
        mock_page = _make_mock_page(cards=[bad_card, good_card])

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        with (
            patch.object(adapter, "_launch_browser", return_value=mock_page),
            patch.object(adapter, "_close_browser", new_callable=AsyncMock),
        ):
            listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Good Job"


class TestFetchDetail:
    """Tests for base class fetch_detail via WorkdayAdapter class attributes."""

    async def test_skips_if_already_has_detail(self) -> None:
        adapter = WorkdayAdapter()
        listing = RawListing(
            external_url=f"{BASE_URL}/en-US/AbsaCareers/job/SE_001",
            title="Software Engineer",
            company_name="Absa Bank",
            raw_html="<div>" + "x" * 300 + "</div>",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result.raw_html == listing.raw_html

    async def test_rejects_external_host(self) -> None:
        adapter = WorkdayAdapter()
        listing = RawListing(
            external_url="https://evil.com/steal",
            title="Bad Job",
            company_name="Evil Corp",
        )
        result = await adapter.fetch_detail(listing, _make_config())
        assert result.raw_html is None

    async def test_fetches_detail_via_playwright(self) -> None:
        """Base class fetch_detail launches a standalone Playwright session."""
        detail_el = AsyncMock()
        detail_el.inner_html = AsyncMock(return_value="<p>Build scalable systems</p>")

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

        adapter = WorkdayAdapter(page_timeout=5.0, nav_delay=0)
        listing = RawListing(
            external_url=f"{BASE_URL}/en-US/AbsaCareers/job/SE_001",
            title="Software Engineer",
            company_name="Absa Bank",
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
        assert "scalable systems" in result.raw_html


class TestCanHandleUrl:
    """Tests for base class can_handle_url via WorkdayAdapter._host_suffix."""

    def test_workday_url(self) -> None:
        adapter = WorkdayAdapter()
        assert adapter.can_handle_url(
            "https://absa.wd3.myworkdayjobs.com/en-US/AbsaCareers/job/SE_001"
        )

    def test_ncba_workday_url(self) -> None:
        adapter = WorkdayAdapter()
        assert adapter.can_handle_url(
            "https://ncba.wd3.myworkdayjobs.com/en-US/NCBACareers/job/RA_001"
        )

    def test_non_workday_url(self) -> None:
        adapter = WorkdayAdapter()
        assert not adapter.can_handle_url("https://www.example.com/job/123")
