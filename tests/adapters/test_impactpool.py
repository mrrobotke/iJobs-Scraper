"""Tests for the server-rendered Impactpool adapter."""

from __future__ import annotations

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.browser.impactpool import ImpactpoolAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://www.impactpool.org"
SEARCH_URL = f"{BASE_URL}/search"
LISTINGS_HTML = """
<main id="job_list">
  <div class="job">
    <a href="/jobs/1223430">
      <div class="ip-typography" type="cardTitle">Partnerships Manager</div>
      <div class="ip-typography" type="bodyEmphasis">Justdiggit Foundation</div>
      <div class="ip-typography" type="bodyEmphasis">Nairobi</div>
    </a>
  </div>
  <div class="job">
    <a href="/jobs/1228095">
      <div class="ip-typography" type="cardTitle">Project Assistant</div>
      <div class="ip-typography" type="bodyEmphasis">UN-Habitat</div>
    </a>
  </div>
  <turbo-frame id="search_results_more_button">
    <a href="/search?page=2&amp;per_page=40&amp;wl%5B%5D=115">Show more</a>
  </turbo-frame>
</main>
"""
LAST_PAGE_HTML = """
<main id="job_list">
  <div class="job">
    <a href="/jobs/1228000">
      <div class="ip-typography" type="cardTitle">Software Developer</div>
      <div class="ip-typography" type="bodyEmphasis">IRC</div>
    </a>
  </div>
</main>
"""


def _make_config(**config: object) -> SourceConfig:
    return SourceConfig(
        name="Impactpool",
        slug="impactpool",
        adapter="impactpool",
        source_type=SourceType.HTML,
        base_url=BASE_URL,
        config=dict(config),
    )


class TestImpactpoolRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("impactpool")(ImpactpoolAdapter)
        assert AdapterRegistry.get("impactpool") is ImpactpoolAdapter


class TestFetchListings:
    @respx.mock
    async def test_parses_server_rendered_job_cards(self) -> None:
        route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text=LAST_PAGE_HTML))
        adapter = ImpactpoolAdapter(request_delay=0, jitter=0)

        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].external_id == "1228000"
        assert listings[0].title == "Software Developer"
        assert listings[0].company_name == "IRC"
        assert listings[0].external_url == f"{BASE_URL}/jobs/1228000"
        assert "wl%5B%5D=115" in str(route.calls[0].request.url)

    @respx.mock
    async def test_follows_show_more_pagination(self) -> None:
        route = respx.get(SEARCH_URL).mock(
            side_effect=[
                httpx.Response(200, text=LISTINGS_HTML),
                httpx.Response(200, text=LAST_PAGE_HTML),
            ]
        )
        adapter = ImpactpoolAdapter(request_delay=0, jitter=0)

        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert [listing.external_id for listing in listings] == [
            "1223430",
            "1228095",
            "1228000",
        ]
        assert route.call_count == 2
        assert "page=2" in str(route.calls[1].request.url)

    @respx.mock
    async def test_empty_results_are_successful(self) -> None:
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, text='<main id="job_list"></main>')
        )
        adapter = ImpactpoolAdapter(request_delay=0, jitter=0)

        assert [listing async for listing in adapter.fetch_listings(_make_config())] == []


class TestFetchDetail:
    @respx.mock
    async def test_fetches_job_description(self) -> None:
        url = f"{BASE_URL}/jobs/1223430"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                text=(
                    '<div id="job-description"><h1>Partnerships Manager</h1>'
                    "<p>Build strategic partnerships.</p></div>"
                ),
            )
        )
        adapter = ImpactpoolAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_id="1223430",
            external_url=url,
            title="Partnerships Manager",
        )

        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "Build strategic partnerships" in result.raw_html

    @respx.mock
    async def test_rejects_non_impactpool_detail_url(self) -> None:
        adapter = ImpactpoolAdapter(request_delay=0, jitter=0)
        listing = RawListing(external_url="https://example.com/jobs/1")

        assert await adapter.fetch_detail(listing, _make_config()) is listing
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_impactpool_url(self) -> None:
        assert ImpactpoolAdapter().can_handle_url("https://www.impactpool.org/jobs/1223430")

    def test_non_impactpool_url(self) -> None:
        assert not ImpactpoolAdapter().can_handle_url("https://example.com/jobs/1")
