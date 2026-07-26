"""Tests for the current NCBA Group careers adapter."""

from __future__ import annotations

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.html.ncba import NCBAAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://ncbagroup.com"
CAREERS_URL = f"{BASE_URL}/careers/"
LISTINGS_HTML = """
<main>
  <article class="vacancy-card">
    <h2><a href="/careers/senior-risk-manager/">Senior Risk Manager</a></h2>
    <span class="location">Nairobi, Kenya</span>
  </article>
  <article class="vacancy-card"><h2>Malformed</h2></article>
</main>
"""


def _make_config() -> SourceConfig:
    return SourceConfig(
        name="NCBA Bank",
        slug="ncba-bank",
        adapter="ncba",
        source_type=SourceType.HTML,
        base_url=BASE_URL,
    )


class TestNCBARegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("ncba")(NCBAAdapter)
        assert AdapterRegistry.get("ncba") is NCBAAdapter


class TestFetchListings:
    @respx.mock
    async def test_parses_current_vacancy_cards(self) -> None:
        respx.get(CAREERS_URL).mock(return_value=httpx.Response(200, text=LISTINGS_HTML))
        adapter = NCBAAdapter(request_delay=0, jitter=0)

        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        assert listings[0].title == "Senior Risk Manager"
        assert listings[0].external_url == f"{BASE_URL}/careers/senior-risk-manager/"
        assert listings[0].company_name == "NCBA Bank"

    @respx.mock
    async def test_brand_page_without_openings_is_successful(self) -> None:
        respx.get(CAREERS_URL).mock(
            return_value=httpx.Response(
                200,
                text="<main><h1>Careers</h1><p>Join our talent community.</p></main>",
            )
        )
        adapter = NCBAAdapter(request_delay=0, jitter=0)

        assert [listing async for listing in adapter.fetch_listings(_make_config())] == []


class TestFetchDetail:
    @respx.mock
    async def test_fetches_vacancy_detail(self) -> None:
        url = f"{BASE_URL}/careers/senior-risk-manager/"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                text='<main class="job-detail"><p>Lead enterprise risk management.</p></main>',
            )
        )
        adapter = NCBAAdapter(request_delay=0, jitter=0)
        listing = RawListing(external_url=url, title="Senior Risk Manager")

        result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_html is not None
        assert "enterprise risk management" in result.raw_html


class TestCanHandleUrl:
    def test_ncba_url(self) -> None:
        assert NCBAAdapter().can_handle_url("https://ncbagroup.com/careers/senior-risk-manager/")

    def test_non_ncba_url(self) -> None:
        assert not NCBAAdapter().can_handle_url("https://example.com/jobs/1")
