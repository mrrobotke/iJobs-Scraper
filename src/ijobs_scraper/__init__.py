"""ijobs-scraper: Job scraping & AI enrichment engine for African job markets."""

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.base import APIAdapter, BaseAdapter, BrowserAdapter, HTMLAdapter
from ijobs_scraper.engine import ScraperEngine
from ijobs_scraper.exceptions import (
    AdapterError,
    DuplicateJobError,
    EnrichmentError,
    RateLimitError,
    ScraperError,
)
from ijobs_scraper.models import (
    EnrichedJob,
    JobRequirements,
    RawListing,
    ScrapeResult,
    SourceConfig,
    SourceType,
)
from ijobs_scraper.protocols import AIProvider, JobCallback, StorageBackend
from ijobs_scraper.scheduler import get_due_sources

__all__ = [
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
]
