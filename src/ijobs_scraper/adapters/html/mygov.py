"""Kenya Government Advertising Agency job-adverts adapter.

The former MyGov site now redirects to the Government Advertising Agency
(GAA). The adapter name remains ``mygov`` for source compatibility.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import HTMLAdapter
from ijobs_scraper.models import RawListing, SourceConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

GAA_BASE_URL = "https://gaa.go.ke"
GAA_JOB_ADVERTS_PATH = "/index.php/node/445"
_GOVERNMENT_HOSTS = ("gaa.go.ke", "mygov.go.ke")


@AdapterRegistry.register("mygov")
class MyGovAdapter(HTMLAdapter):
    """Scrape current public-sector advert PDFs from the official GAA table."""

    @staticmethod
    def _listing_base(config: SourceConfig) -> str:
        host = (urlparse(config.base_url).hostname or "").lower()
        if host == "mygov.go.ke" or host.endswith(".mygov.go.ke"):
            return GAA_BASE_URL
        return config.base_url.rstrip("/")

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Yield each government advert row with its official PDF URL."""
        base = self._listing_base(config)
        url = f"{base}{GAA_JOB_ADVERTS_PATH}"
        soup = await self._fetch_page(url)
        table = soup.select_one("table#datatable")
        if table is None:
            return

        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            link = cells[1].find("a", href=True)
            if link is None:
                continue
            href = link.get("href")
            if not isinstance(href, str):
                continue
            external_url = urljoin(base + "/", href)
            if not self._validate_url(external_url, "gaa.go.ke"):
                continue

            title = cells[0].get_text(" ", strip=True)
            company_name = cells[2].get_text(" ", strip=True) or config.name
            submission_date = cells[3].get_text(" ", strip=True) if len(cells) > 3 else ""
            if not title:
                continue
            raw_text = "\n".join(
                part
                for part in (
                    title,
                    f"Recruiting agency: {company_name}",
                    f"Submission date: {submission_date}" if submission_date else "",
                )
                if part
            )

            yield RawListing(
                external_id=urlparse(external_url).path.rsplit("/", maxsplit=1)[-1],
                external_url=external_url,
                title=title,
                raw_text=raw_text,
                company_name=company_name,
            )

    async def _extract_pdf_text(self, url: str) -> str:
        """Download a bounded official PDF and extract its page text."""
        try:
            import pdfplumber
        except ImportError:
            logger.warning(
                "pdfplumber is unavailable; install ijobs-scraper[pdf] for MyGov details"
            )
            return ""

        body, _ = await self._fetch_bytes(url, detail=True)
        with pdfplumber.open(BytesIO(body)) as document:
            pages = (page.extract_text() or "" for page in document.pages)
            return "\n\n".join(text for text in pages if text.strip())

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Append extracted official PDF text to the advert row metadata."""
        if not self._validate_url(listing.external_url, "gaa.go.ke"):
            logger.warning(
                "Rejecting government advert URL outside GAA: %s",
                listing.external_url,
            )
            return listing
        if not urlparse(listing.external_url).path.lower().endswith(".pdf"):
            return listing

        pdf_text = await self._extract_pdf_text(listing.external_url)
        if not pdf_text:
            return listing
        combined = "\n\n".join(part for part in (listing.raw_text, pdf_text) if part)
        return listing.model_copy(update={"raw_text": combined})

    def can_handle_url(self, url: str) -> bool:
        """Return whether *url* belongs to the legacy MyGov or current GAA host."""
        return any(self._validate_url(url, host) is not None for host in _GOVERNMENT_HOSTS)
