"""ScraperEngine — main orchestrator for job scraping and enrichment.

Coordinates adapters, enrichment pipeline, deduplication, and callbacks.
Provides both batch (scrape_source, scrape_all) and single-URL (parse_url) modes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import BaseAdapter
from ijobs_scraper.dedup import is_known_url
from ijobs_scraper.enrichment import enrich
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import EnrichedJob, RawListing, ScrapeResult, SourceConfig, SourceType
from ijobs_scraper.protocols import AIProvider, JobCallback, StorageBackend

_default_logger = logging.getLogger("ijobs_scraper")


class ScraperEngine:
    """Main entry point for the ijobs-scraper package.

    Orchestrates the full pipeline: adapter → fetch → dedup → enrich → callback.
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        storage: StorageBackend | None = None,
        on_job: JobCallback | None = None,
        dedup_enabled: bool = True,
        logger: Any = None,
    ) -> None:
        self._ai_provider = ai_provider
        self._storage = storage
        self._on_job = on_job
        self._dedup_enabled = dedup_enabled
        self._log: logging.Logger = logger or _default_logger

    async def scrape_source(self, source: SourceConfig) -> ScrapeResult:
        """Scrape all listings from a single source.

        Follows the full pipeline: fetch listings → Layer 1 dedup →
        fetch detail → enrich → Layer 2 dedup → save → callback.
        Per-job error isolation ensures one failure never stops the batch.

        Args:
            source: Configuration for the source to scrape.

        Returns:
            Summary of the scrape run with counts and errors.
        """
        result = ScrapeResult(
            source_slug=source.slug,
            status="completed",
            started_at=datetime.now(UTC),
        )

        adapter_cls = AdapterRegistry.get(source.adapter)
        adapter = adapter_cls()

        # Layer 1 dedup: load known URLs for this source
        known_urls: set[str] = set()
        if self._dedup_enabled and self._storage:
            known_urls = await self._storage.get_known_urls(source.slug)

        self._log.info(
            "scrape_source_started",
            extra={"source_slug": source.slug, "adapter": source.adapter},
        )

        async for listing in adapter.fetch_listings(source):
            result.jobs_found += 1

            # Layer 1: source URL uniqueness
            if self._dedup_enabled and is_known_url(listing.external_url, known_urls):
                result.jobs_duplicated += 1
                continue

            try:
                # Fetch full details if needed
                listing = await adapter.fetch_detail(listing, source)

                # Enrich via AI
                enriched = await enrich(listing, source, self._ai_provider)

                # Layer 2: cross-source content hash dedup
                if (
                    self._dedup_enabled
                    and self._storage
                    and await self._storage.check_content_hash(enriched.content_hash)
                ):
                    result.jobs_duplicated += 1
                    await self._storage.mark_duplicate(source.slug, listing, enriched.content_hash)
                    continue

                # Persist raw listing
                if self._storage:
                    await self._storage.save_raw_listing(source.slug, listing)

                # Emit enriched job via callback
                if self._on_job:
                    await self._on_job(enriched, source, listing)

                result.jobs_created += 1

            except Exception as exc:
                result.jobs_failed += 1
                result.errors.append(f"{listing.external_url}: {exc}")
                self._log.warning(
                    "listing_failed",
                    extra={"source_slug": source.slug, "external_url": listing.external_url},
                    exc_info=exc,
                )

        result.status = "completed" if not result.errors else "partial"
        result.completed_at = datetime.now(UTC)

        self._log.info(
            "scrape_source_completed",
            extra={
                "source_slug": source.slug,
                "jobs_found": result.jobs_found,
                "jobs_created": result.jobs_created,
            },
        )
        return result

    async def parse_url(self, url: str, hint: str | None = None) -> EnrichedJob:
        """Parse a single job URL and return enriched data.

        Auto-detects the adapter from the URL domain, or uses the provided
        hint to select the adapter explicitly.

        Args:
            url: The job listing URL to parse.
            hint: Optional adapter name to use instead of auto-detection.

        Returns:
            Enriched job data extracted from the URL.

        Raises:
            AdapterError: If no adapter can handle the URL.
        """
        adapter_cls = AdapterRegistry.get(hint) if hint else AdapterRegistry.detect_from_url(url)

        if adapter_cls is None:
            raise AdapterError("auto", f"No adapter found for URL: {url}", retryable=False)

        adapter = adapter_cls()
        source = SourceConfig(
            name="manual",
            slug="manual",
            adapter=hint or "auto",
            source_type=SourceType.HTML,
            base_url=url,
        )

        listing = RawListing(external_url=url)
        listing = await adapter.fetch_detail(listing, source)
        return await enrich(listing, source, self._ai_provider)

    async def scrape_all(self, sources: list[SourceConfig]) -> list[ScrapeResult]:
        """Scrape multiple sources sequentially.

        Args:
            sources: List of source configurations to scrape.

        Returns:
            List of scrape results, one per source.
        """
        results: list[ScrapeResult] = []
        for source in sources:
            result = await self.scrape_source(source)
            results.append(result)
        return results

    def register_adapter(self, name: str, adapter_class: type[BaseAdapter]) -> None:
        """Register a new adapter class in the global registry.

        Args:
            name: Name to register the adapter under.
            adapter_class: The adapter class to register.
        """
        AdapterRegistry._adapters[name] = adapter_class
