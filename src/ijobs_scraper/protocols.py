"""Protocol interfaces for host application integration.

The host application implements these protocols to provide AI extraction,
persistence, and job handling capabilities. Uses structural subtyping —
no inheritance required.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ijobs_scraper.models import EnrichedJob, RawListing, SourceConfig


@runtime_checkable
class AIProvider(Protocol):
    """Provides AI-powered structured data extraction."""

    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Send prompts + JSON schema, return parsed response."""
        ...


@runtime_checkable
class StorageBackend(Protocol):
    """Provides persistence for deduplication and raw listing storage."""

    async def get_known_urls(self, source_slug: str) -> set[str]:
        """Return external_urls already scraped for this source."""
        ...

    async def save_raw_listing(self, source_slug: str, listing: RawListing) -> None:
        """Persist raw scraped data before enrichment."""
        ...

    async def mark_duplicate(
        self, source_slug: str, listing: RawListing, content_hash: str
    ) -> None:
        """Record that this listing is a duplicate (identified by content hash)."""
        ...

    async def check_content_hash(self, content_hash: str) -> bool:
        """Return True if this content hash already exists (cross-source dedup)."""
        ...


@runtime_checkable
class FailureTrackingStorageBackend(Protocol):
    """Optional storage extension for durable failed-listing checkpoints."""

    async def mark_failed(self, source_slug: str, listing: RawListing) -> None:
        """Persist a failed URL so a continuation can advance past it."""
        ...


@runtime_checkable
class JobCallback(Protocol):
    """Callback invoked for each newly enriched job."""

    async def __call__(
        self,
        job: EnrichedJob,
        source: SourceConfig,
        raw: RawListing,
    ) -> None:
        """Handle a newly enriched job."""
        ...
