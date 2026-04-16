# API Reference

Everything consumers need is importable from the top-level `ijobs_scraper` package.

```python
from ijobs_scraper import (
    ScraperEngine, SourceConfig, RawListing, EnrichedJob,
    ScrapeResult, JobRequirements, SourceType,
    AIProvider, StorageBackend, JobCallback,
    AdapterRegistry, BaseAdapter, APIAdapter, HTMLAdapter, BrowserAdapter,
    ScraperError, AdapterError, EnrichmentError, DuplicateJobError, RateLimitError,
    get_due_sources,
)
```

---

## Core

### `ScraperEngine`

Main orchestrator. Coordinates adapters, enrichment, deduplication, and callbacks.

```python
class ScraperEngine:
    def __init__(
        self,
        ai_provider: AIProvider,
        storage: StorageBackend | None = None,
        on_job: JobCallback | None = None,
        dedup_enabled: bool = True,
        logger: Any = None,
    ) -> None: ...

    async def scrape_source(self, source: SourceConfig) -> ScrapeResult: ...
    async def parse_url(self, url: str, hint: str | None = None) -> EnrichedJob: ...
    async def scrape_all(self, sources: list[SourceConfig]) -> list[ScrapeResult]: ...
    def register_adapter(self, name: str, adapter_class: type[BaseAdapter]) -> None: ...
```

- **`scrape_source(source)`** — Scrape all listings from a single source. Runs the full pipeline: fetch, dedup, enrich, callback.
- **`parse_url(url, hint=None)`** — Parse a single job URL. Auto-detects the adapter or uses the provided hint.
- **`scrape_all(sources)`** — Scrape multiple sources sequentially.
- **`register_adapter(name, adapter_class)`** — Register a new adapter class at runtime.

### `AdapterRegistry`

Maps adapter names to their implementation classes.

```python
class AdapterRegistry:
    @classmethod
    def register(cls, name: str) -> Callable: ...
    @classmethod
    def get(cls, name: str) -> type[BaseAdapter]: ...
    @classmethod
    def detect_from_url(cls, url: str) -> type[BaseAdapter] | None: ...
    @classmethod
    def list_adapters(cls) -> dict[str, type[BaseAdapter]]: ...
```

- **`register(name)`** — Decorator that registers an adapter class under the given name.
- **`get(name)`** — Return the adapter class registered under `name`. Raises `AdapterError` if not found.
- **`detect_from_url(url)`** — Return the first adapter whose `can_handle_url()` matches the URL.
- **`list_adapters()`** — Return a copy of all registered adapters.

---

## Data Models

All models use Pydantic v2.

### `SourceConfig`

Configuration for a single job portal source.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Human-readable name (e.g., "Kenya Airways") |
| `slug` | `str` | URL-safe identifier (e.g., "kenya-airways") |
| `adapter` | `str` | Adapter name from registry (e.g., "greenhouse") |
| `source_type` | `SourceType` | One of: `api`, `html`, `browser`, `rss` |
| `base_url` | `str` | Base URL for the source |
| `cron_schedule` | `str \| None` | Cron expression (e.g., `"0 */6 * * *"`) |
| `is_active` | `bool` | Whether the source is enabled (default: `True`) |
| `config` | `dict[str, Any]` | Adapter-specific configuration |

### `RawListing`

Raw job listing data as fetched from a source, before enrichment.

| Field | Type | Description |
|-------|------|-------------|
| `external_id` | `str \| None` | Source-specific job ID |
| `external_url` | `str` | URL of the job listing |
| `title` | `str \| None` | Job title (if available pre-enrichment) |
| `raw_html` | `str \| None` | Raw HTML content |
| `raw_json` | `dict \| None` | Raw JSON response |
| `raw_text` | `str \| None` | Raw text content |
| `company_name` | `str \| None` | Company name |
| `fetched_at` | `datetime` | When the listing was fetched |

### `EnrichedJob`

Fully enriched job data after AI extraction and validation.

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | SEO-optimized job title |
| `description` | `str` | Cleaned job description |
| `company_name` | `str` | Company name |
| `company_website` | `str \| None` | Company website URL |
| `location` | `str \| None` | Normalized location ("City, Country") |
| `remote_type` | `Literal` | `"onsite"`, `"hybrid"`, or `"remote"` |
| `employment_type` | `Literal` | `"full_time"`, `"part_time"`, `"contract"`, or `"internship"` |
| `experience_level` | `str \| None` | Experience level |
| `salary_min` | `int \| None` | Minimum salary |
| `salary_max` | `int \| None` | Maximum salary |
| `currency` | `str` | Currency code (default: `"KES"`) |
| `skills` | `list[str]` | Extracted skills |
| `benefits` | `list[str]` | Extracted benefits |
| `category` | `str \| None` | Job category from predefined enum |
| `requirements` | `JobRequirements \| None` | Structured requirements |
| `number_of_openings` | `int \| None` | Number of open positions (defaults to `1` when the source does not specify) |
| `application_instructions` | `str \| None` | How to apply (email, portal link, deadline notes, etc.) |
| `external_url` | `str` | Original source URL |
| `posted_at` | `datetime \| None` | When the job was posted |
| `expires_at` | `datetime \| None` | When the job expires |
| `content_hash` | `str` | SHA-256 hash for deduplication |
| `source_slug` | `str` | Source identifier |

### `ScrapeResult`

Summary of a single source scrape run.

| Field | Type | Description |
|-------|------|-------------|
| `source_slug` | `str` | Source identifier |
| `status` | `Literal` | `"completed"`, `"partial"`, or `"failed"` |
| `started_at` | `datetime` | Run start time |
| `completed_at` | `datetime \| None` | Run end time |
| `jobs_found` | `int` | Total listings found |
| `jobs_created` | `int` | New jobs created |
| `jobs_duplicated` | `int` | Duplicates skipped |
| `jobs_failed` | `int` | Failed enrichments |
| `errors` | `list[str]` | Error messages |

### `JobRequirements`

Structured requirements extracted from a job listing.

| Field | Type | Description |
|-------|------|-------------|
| `education_level` | `str \| None` | Required education |
| `min_years_experience` | `int \| None` | Minimum years of experience |
| `certifications` | `list[str]` | Required certifications |
| `languages` | `list[str]` | Required languages |
| `key_responsibilities` | `list[str]` | Key duties and responsibilities for the role |
| `minimum_qualifications` | `list[str]` | Must-have qualifications (education, experience, required skills) |
| `preferred_qualifications` | `list[str]` | Nice-to-have qualifications that strengthen an application |

### `SourceType`

Enum classifying how a source is scraped: `API`, `HTML`, `BROWSER`, `RSS`.

---

## Protocols

Host application implements these interfaces. Uses structural subtyping (`Protocol`) — no inheritance required.

### `AIProvider`

```python
class AIProvider(Protocol):
    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]: ...
```

Send prompts and a JSON schema to an AI model, return parsed response.

### `StorageBackend`

```python
class StorageBackend(Protocol):
    async def get_known_urls(self, source_slug: str) -> set[str]: ...
    async def save_raw_listing(self, source_slug: str, listing: RawListing) -> None: ...
    async def mark_duplicate(self, source_slug: str, listing: RawListing, content_hash: str) -> None: ...
    async def check_content_hash(self, content_hash: str) -> bool: ...
```

Provides persistence for deduplication and raw listing storage.

### `JobCallback`

```python
class JobCallback(Protocol):
    async def __call__(self, job: EnrichedJob, source: SourceConfig, raw: RawListing) -> None: ...
```

Callback invoked for each newly enriched job.

---

## Adapter Base Classes

### `BaseAdapter`

Abstract base for all portal adapters.

- **`fetch_listings(config: SourceConfig) -> AsyncIterator[RawListing]`** — Yield raw job listings.
- **`fetch_detail(listing, config) -> RawListing`** — Optionally fetch full details (default: pass-through).
- **`can_handle_url(url: str) -> bool`** — Check if this adapter can parse the URL.

### `APIAdapter(BaseAdapter)`

Base for REST API sources. Provides `_get()` and `_post()` with rate limiting via httpx.

### `HTMLAdapter(BaseAdapter)`

Base for BeautifulSoup HTML scraping. Provides `_fetch_page()` with rate limiting and jitter.

### `BrowserAdapter(BaseAdapter)`

Base for Playwright browser automation. Provides `_launch_browser()` and `_navigate()`.

---

## Exceptions

| Exception | Parent | Description |
|-----------|--------|-------------|
| `ScraperError` | `Exception` | Base exception for all scraper errors |
| `AdapterError` | `ScraperError` | Adapter encountered an error (has `retryable` flag) |
| `RateLimitError` | `AdapterError` | HTTP 429 rate limit (has `retry_after` seconds) |
| `EnrichmentError` | `ScraperError` | AI enrichment pipeline failed |
| `DuplicateJobError` | `ScraperError` | Job already exists (has `content_hash`) |

---

## Scheduler

### `get_due_sources(sources, last_runs) -> list[SourceConfig]`

```python
def get_due_sources(
    sources: list[SourceConfig],
    last_runs: dict[str, datetime],
) -> list[SourceConfig]: ...
```

Evaluate cron schedules and return sources due for scraping. Does NOT enqueue work — that is the host application's responsibility.
