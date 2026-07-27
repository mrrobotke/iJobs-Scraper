"""Tests for ScraperEngine orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper.engine import ScraperEngine
from ijobs_scraper.exceptions import AdapterError
from ijobs_scraper.models import EnrichedJob, RawListing, SourceConfig, SourceType

from .conftest import StubAIProvider, StubStorageBackend

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _make_source(
    adapter: str = "test_adapter",
    *,
    config: dict[str, object] | None = None,
) -> SourceConfig:
    return SourceConfig(
        name="Test Source",
        slug="test-source",
        adapter=adapter,
        source_type=SourceType.API,
        base_url="https://example.com",
        config=config or {},
    )


class MockAdapter(APIAdapter):
    """Test adapter that yields pre-defined listings."""

    def __init__(self, listings: list[RawListing] | None = None) -> None:
        super().__init__()
        self._listings = listings or [
            RawListing(
                external_id="1",
                external_url="https://example.com/job/1",
                title="Job 1",
                raw_json={"title": "Job 1", "description": "First job"},
                company_name="Test Corp",
            ),
            RawListing(
                external_id="2",
                external_url="https://example.com/job/2",
                title="Job 2",
                raw_json={"title": "Job 2", "description": "Second job"},
                company_name="Test Corp",
            ),
        ]

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        for listing in self._listings:
            yield listing

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Return the listing with raw_json content for enrichment."""
        if listing.raw_json:
            return listing
        return listing.model_copy(
            update={"raw_json": {"title": listing.title or "Test Job", "description": "Details"}}
        )

    def can_handle_url(self, url: str) -> bool:
        return "example.com" in url


class FailingAdapter(APIAdapter):
    """Adapter where one listing raises an error."""

    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        yield RawListing(
            external_id="1",
            external_url="https://example.com/job/1",
            title="Good Job",
            raw_json={"title": "Good Job"},
            company_name="Corp",
        )
        yield RawListing(
            external_id="2",
            external_url="https://example.com/job/2",
            # No raw content AND no title → will fail enrichment
            company_name="Corp",
        )
        yield RawListing(
            external_id="3",
            external_url="https://example.com/job/3",
            title="Another Good Job",
            raw_json={"title": "Another Good Job"},
            company_name="Corp",
        )

    def can_handle_url(self, url: str) -> bool:
        return False


class TestScrapeSource:
    async def test_scrapes_all_listings(self) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        ai = StubAIProvider()
        engine = ScraperEngine(ai_provider=ai)

        result = await engine.scrape_source(_make_source())

        assert result.jobs_found == 2
        assert result.jobs_created == 2
        assert result.status == "completed"
        assert len(ai.calls) == 2

    async def test_layer1_dedup_skips_known_urls(self) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        ai = StubAIProvider()
        storage = StubStorageBackend()
        storage.known_urls["test-source"] = {"https://example.com/job/1"}

        engine = ScraperEngine(ai_provider=ai, storage=storage)
        result = await engine.scrape_source(_make_source())

        assert result.jobs_found == 2
        assert result.jobs_duplicated == 1
        assert result.jobs_created == 1

    async def test_batch_continuation_counts_only_new_listings(self) -> None:
        listings = [
            RawListing(
                external_id=str(index),
                external_url=f"https://example.com/job/{index}",
                title=f"Job {index}",
                raw_json={"title": f"Job {index}", "description": "Details"},
                company_name="Test Corp",
            )
            for index in range(1, 6)
        ]

        class BatchMockAdapter(MockAdapter):
            def __init__(self) -> None:
                super().__init__(listings)

        AdapterRegistry.register("test_adapter")(BatchMockAdapter)
        ai = StubAIProvider()
        storage = StubStorageBackend()
        storage.known_urls["test-source"] = {
            "https://example.com/job/1",
            "https://example.com/job/2",
        }

        engine = ScraperEngine(ai_provider=ai, storage=storage)
        first_result = await engine.scrape_source(
            _make_source(config={"max_new_listings_per_batch": 2})
        )

        assert first_result.jobs_found == 4
        assert first_result.jobs_duplicated == 2
        assert first_result.jobs_created == 2
        assert first_result.continuation_required is True
        assert len(ai.calls) == 2

        second_result = await engine.scrape_source(
            _make_source(config={"max_new_listings_per_batch": 2})
        )

        assert second_result.jobs_found == 5
        assert second_result.jobs_duplicated == 4
        assert second_result.jobs_created == 1
        assert second_result.continuation_required is False
        assert len(ai.calls) == 3

    async def test_failed_listing_is_checkpointed_before_continuation(self) -> None:
        AdapterRegistry.register("test_adapter")(FailingAdapter)
        ai = StubAIProvider()
        storage = StubStorageBackend()
        engine = ScraperEngine(ai_provider=ai, storage=storage)

        first_result = await engine.scrape_source(
            _make_source(config={"max_new_listings_per_batch": 2})
        )
        second_result = await engine.scrape_source(
            _make_source(config={"max_new_listings_per_batch": 2})
        )

        assert first_result.jobs_created == 1
        assert first_result.jobs_failed == 1
        assert first_result.continuation_required is True
        assert len(storage.failed_listings) == 1
        assert storage.failed_listings[0][1].external_url == "https://example.com/job/2"
        assert second_result.jobs_duplicated == 2
        assert second_result.jobs_created == 1
        assert second_result.continuation_required is False

    @pytest.mark.parametrize("limit", [0, -1, "not-a-number"])
    async def test_rejects_invalid_batch_limit(self, limit: object) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        engine = ScraperEngine(ai_provider=StubAIProvider())

        with pytest.raises(
            ValueError,
            match="max_new_listings_per_batch must be a positive integer",
        ):
            await engine.scrape_source(_make_source(config={"max_new_listings_per_batch": limit}))

    async def test_layer2_dedup_via_storage(self) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        ai = StubAIProvider()
        storage = StubStorageBackend()

        # Pre-populate with the content hash that the stub AI will produce
        from ijobs_scraper.dedup import compute_content_hash

        existing_hash = compute_content_hash("Software Engineer", "Test Corp", "Nairobi, Kenya")
        storage.content_hashes.add(existing_hash)

        engine = ScraperEngine(ai_provider=ai, storage=storage)
        result = await engine.scrape_source(_make_source())

        assert result.jobs_found == 2
        # Both listings produce the same content hash (stub AI returns same data)
        assert result.jobs_duplicated == 2
        assert result.jobs_created == 0

    async def test_per_job_error_isolation(self) -> None:
        AdapterRegistry.register("test_adapter")(FailingAdapter)
        ai = StubAIProvider()
        engine = ScraperEngine(ai_provider=ai)

        result = await engine.scrape_source(_make_source())

        assert result.jobs_found == 3
        assert result.jobs_failed == 1  # The listing with no content
        assert result.jobs_created == 2  # The two good listings
        assert result.status == "partial"
        assert len(result.errors) == 1

    async def test_saves_raw_listing(self) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        ai = StubAIProvider()
        storage = StubStorageBackend()

        engine = ScraperEngine(ai_provider=ai, storage=storage)
        await engine.scrape_source(_make_source())

        assert len(storage.saved_listings) == 2
        assert storage.saved_listings[0][0] == "test-source"

    async def test_calls_job_callback(self) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        ai = StubAIProvider()
        callback_jobs: list[EnrichedJob] = []

        async def on_job(job: EnrichedJob, source: SourceConfig, raw: RawListing) -> None:
            callback_jobs.append(job)

        engine = ScraperEngine(ai_provider=ai, on_job=on_job)
        await engine.scrape_source(_make_source())

        assert len(callback_jobs) == 2
        assert callback_jobs[0].title == "Software Engineer"

    async def test_dedup_disabled(self) -> None:
        listings = [
            RawListing(
                external_url="https://example.com/job/1",
                raw_json={"title": "Job"},
                company_name="Corp",
            ),
        ]
        AdapterRegistry.register("test_adapter")(lambda: MockAdapter(listings))

        # Register the actual adapter class, not a lambda
        class SingleMockAdapter(MockAdapter):
            def __init__(self) -> None:
                super().__init__(listings)

        AdapterRegistry.register("test_adapter")(SingleMockAdapter)

        ai = StubAIProvider()
        storage = StubStorageBackend()
        storage.known_urls["test-source"] = {"https://example.com/job/1"}

        engine = ScraperEngine(ai_provider=ai, storage=storage, dedup_enabled=False)
        result = await engine.scrape_source(_make_source())

        assert result.jobs_duplicated == 0
        assert result.jobs_created == 1


class TestParseUrl:
    async def test_with_hint(self) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        ai = StubAIProvider()
        engine = ScraperEngine(ai_provider=ai)

        job = await engine.parse_url("https://example.com/job/1", hint="test_adapter")
        assert job.title == "Software Engineer"
        assert job.external_url is None

    async def test_auto_detect(self) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        ai = StubAIProvider()
        engine = ScraperEngine(ai_provider=ai)

        job = await engine.parse_url("https://example.com/job/1")
        assert job.title == "Software Engineer"

    async def test_no_adapter_raises(self) -> None:
        ai = StubAIProvider()
        engine = ScraperEngine(ai_provider=ai)

        with pytest.raises(AdapterError, match="No adapter found"):
            await engine.parse_url("https://unknown-portal.com/job/1")


class TestScrapeAll:
    async def test_scrapes_multiple_sources(self) -> None:
        AdapterRegistry.register("test_adapter")(MockAdapter)
        ai = StubAIProvider()
        engine = ScraperEngine(ai_provider=ai)

        sources = [
            _make_source(),
            SourceConfig(
                name="Other Source",
                slug="other-source",
                adapter="test_adapter",
                source_type=SourceType.API,
                base_url="https://other.com",
            ),
        ]
        results = await engine.scrape_all(sources)

        assert len(results) == 2
        assert all(r.status in ("completed", "partial") for r in results)


class TestRegisterAdapter:
    def test_register_adapter(self) -> None:
        ai = StubAIProvider()
        engine = ScraperEngine(ai_provider=ai)
        engine.register_adapter("manual_adapter", MockAdapter)

        assert AdapterRegistry.get("manual_adapter") is MockAdapter
