"""Smoke test: verify the package is importable and exports are correct."""

import ijobs_scraper


def test_package_imports() -> None:
    assert ijobs_scraper.__doc__ is not None


def test_all_exports() -> None:
    expected = {
        "AIProvider",
        "AdapterError",
        "AdapterRegistry",
        "APIAdapter",
        "BaseAdapter",
        "BrowserAdapter",
        "DuplicateJobError",
        "EnrichedJob",
        "EnrichmentError",
        "HTMLAdapter",
        "JobCallback",
        "JobRequirements",
        "RateLimitError",
        "RawListing",
        "ScrapeResult",
        "ScraperEngine",
        "ScraperError",
        "SourceConfig",
        "SourceType",
        "StorageBackend",
        "get_due_sources",
    }
    assert set(ijobs_scraper.__all__) == expected


def test_core_classes_importable() -> None:
    from ijobs_scraper import (
        AdapterRegistry,
        EnrichedJob,
        RawListing,
        ScraperEngine,
        SourceConfig,
    )

    assert ScraperEngine is not None
    assert AdapterRegistry is not None
    assert SourceConfig is not None
    assert RawListing is not None
    assert EnrichedJob is not None
