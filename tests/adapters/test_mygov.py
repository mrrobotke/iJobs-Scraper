"""Tests for the MyGov/GAA job adverts adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import respx

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.html.mygov import MyGovAdapter
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

BASE_URL = "https://gaa.go.ke"
LISTINGS_URL = f"{BASE_URL}/index.php/node/445"
PDF_PATH = "/sites/default/files/2026-07/public-service-vacancies.pdf"
PDF_URL = f"{BASE_URL}{PDF_PATH}"
LISTINGS_HTML = f"""
<table id="datatable">
  <tbody>
    <tr>
      <td class="views-field-title">Vacant Positions In The Public Service</td>
      <td class="views-field-field-advert-attachment">
        <a href="{PDF_PATH}" type="application/pdf">Vacancies.pdf</a>
      </td>
      <td class="views-field-field-recruiting-agency">Public Service Commission</td>
      <td class="views-field-field-submission-date">10th August, 2026</td>
    </tr>
    <tr>
      <td class="views-field-title">Malformed advert</td>
      <td></td>
      <td>Unknown Agency</td>
      <td>Refer to institution</td>
    </tr>
  </tbody>
</table>
"""


def _make_config(base_url: str = BASE_URL) -> SourceConfig:
    return SourceConfig(
        name="MyGov Kenya",
        slug="mygov",
        adapter="mygov",
        source_type=SourceType.HTML,
        base_url=base_url,
    )


class TestMyGovRegistration:
    def test_registered(self) -> None:
        AdapterRegistry.register("mygov")(MyGovAdapter)
        assert AdapterRegistry.get("mygov") is MyGovAdapter


class TestFetchListings:
    @respx.mock
    async def test_parses_gaa_job_advert_table(self) -> None:
        respx.get(LISTINGS_URL).mock(return_value=httpx.Response(200, text=LISTINGS_HTML))
        adapter = MyGovAdapter(request_delay=0, jitter=0)

        listings = [listing async for listing in adapter.fetch_listings(_make_config())]

        assert len(listings) == 1
        listing = listings[0]
        assert listing.title == "Vacant Positions In The Public Service"
        assert listing.external_url == PDF_URL
        assert listing.company_name == "Public Service Commission"
        assert listing.raw_text is not None
        assert "10th August, 2026" in listing.raw_text

    @respx.mock
    async def test_redirects_legacy_mygov_config_to_gaa(self) -> None:
        route = respx.get(LISTINGS_URL).mock(
            return_value=httpx.Response(200, text='<table id="datatable"><tbody></tbody></table>')
        )
        adapter = MyGovAdapter(request_delay=0, jitter=0)

        listings = [
            listing
            async for listing in adapter.fetch_listings(_make_config("https://www.mygov.go.ke"))
        ]

        assert listings == []
        assert route.called

    @respx.mock
    async def test_missing_table_is_successful_empty_result(self) -> None:
        respx.get(LISTINGS_URL).mock(
            return_value=httpx.Response(200, text="<html><body>No adverts</body></html>")
        )
        adapter = MyGovAdapter(request_delay=0, jitter=0)

        assert [listing async for listing in adapter.fetch_listings(_make_config())] == []


class TestFetchDetail:
    async def test_extracts_text_from_pdf(self) -> None:
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listing = RawListing(
            external_url=PDF_URL,
            title="Vacant Positions",
            raw_text="Public Service Commission",
        )

        with patch.object(
            adapter,
            "_extract_pdf_text",
            new=AsyncMock(return_value="Director ICT\nApplications close 10 August"),
        ):
            result = await adapter.fetch_detail(listing, _make_config())

        assert result.raw_text is not None
        assert "Director ICT" in result.raw_text
        assert "Public Service Commission" in result.raw_text

    @respx.mock
    async def test_rejects_non_gaa_detail_url(self) -> None:
        adapter = MyGovAdapter(request_delay=0, jitter=0)
        listing = RawListing(external_url="https://example.com/vacancies.pdf")

        assert await adapter.fetch_detail(listing, _make_config()) is listing
        assert respx.calls.call_count == 0


class TestCanHandleUrl:
    def test_legacy_mygov_url(self) -> None:
        assert MyGovAdapter().can_handle_url("https://www.mygov.go.ke/job-adverts")

    def test_gaa_url(self) -> None:
        assert MyGovAdapter().can_handle_url(PDF_URL)

    def test_non_government_url(self) -> None:
        assert not MyGovAdapter().can_handle_url("https://example.com/jobs")
