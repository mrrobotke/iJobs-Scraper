# ijobs-scraper — Architecture & Requirements

> **Package name:** `ijobs-scraper`
> **Install:** `pip install ijobs-scraper`
> **Version:** 0.1.0 (planned)
> **Python:** >=3.12
> **License:** MIT
> **Date:** April 1, 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Package Structure](#2-package-structure)
3. [Diagrams](#3-diagrams)
4. [Public API & Core Interfaces](#4-public-api--core-interfaces)
5. [Data Models](#5-data-models)
6. [Adapter System](#6-adapter-system)
7. [OpenAI Enrichment Pipeline](#7-openai-enrichment-pipeline)
8. [Deduplication Strategy](#8-deduplication-strategy)
9. [Engine Orchestration](#9-engine-orchestration)
10. [iJobs Backend Integration](#10-ijobs-backend-integration)
11. [Cron Scheduling](#11-cron-scheduling)
12. [Admin API Endpoints](#12-admin-api-endpoints-ijobs-side)
13. [Error Handling & Resilience](#13-error-handling--resilience)
14. [Implementation Phases](#14-implementation-phases)
15. [Dependencies](#15-dependencies)
16. [Monitoring & Observability](#16-monitoring--observability)

---

## 1. Executive Summary

`ijobs-scraper` is a standalone, framework-agnostic Python package published to PyPI. It provides a complete job scraping, AI enrichment, and deduplication engine that any Python application can integrate via a clean public API.

The package operates in two modes:

- **Auto Scraper** — Scheduled background scraping of Kenyan vacancy portals. Runs on configurable cron schedules, fetches job listings through pluggable adapters, enriches them via OpenAI structured outputs, deduplicates, and emits structured job data through a callback.
- **Manual Scraper** — On-demand URL parsing. A user provides a job URL, the engine auto-detects the source, fetches content, runs it through the same OpenAI enrichment pipeline, and returns structured job data ready for form pre-fill.

### Design Principles

- **Zero framework coupling** — no FastAPI, SQLAlchemy, or ORM imports inside the package
- **Protocol-based interfaces** — host app provides storage, AI provider, and callbacks via Python `Protocol`
- **Pluggable adapter system** — each portal source is a self-contained adapter class
- **PyPI-publishable** — standalone `pyproject.toml` with hatchling build backend
- **Async-first** — all I/O operations use `async`/`await` (httpx, playwright)
- **Type-safe** — full Pydantic v2 models, mypy strict compatible

---

## 2. Package Structure

### 2.1 Repository Layout

```
ijobs-scraper/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── ijobs_scraper/
│       ├── __init__.py           # Public API exports
│       ├── engine.py             # ScraperEngine orchestrator
│       ├── models.py             # Pydantic data models
│       ├── protocols.py          # Protocol interfaces (AIProvider, StorageBackend, etc.)
│       ├── enrichment.py         # OpenAI structured output pipeline
│       ├── dedup.py              # Deduplication logic
│       ├── scheduler.py          # Cron schedule management (croniter)
│       ├── exceptions.py         # Custom exception hierarchy
│       ├── _registry.py          # Adapter registry (internal)
│       └── adapters/
│           ├── __init__.py
│           ├── base.py           # BaseAdapter, APIAdapter, HTMLAdapter, BrowserAdapter
│           ├── api/
│           │   ├── kenya_airways.py
│           │   ├── greenhouse.py         # Reusable for any Greenhouse employer
│           │   ├── smartrecruiters.py     # Reusable for any SR employer
│           │   ├── careerjet.py
│           │   └── reliefweb.py
│           ├── html/
│           │   ├── brightermonday.py
│           │   ├── myjobmag.py
│           │   ├── mygov.py
│           │   ├── fuzu.py
│           │   └── kcb.py
│           └── browser/
│               ├── workday.py            # Reusable for Absa, NCBA
│               ├── impactpool.py
│               └── world_vision.py
├── tests/
│   ├── conftest.py
│   ├── test_engine.py
│   ├── test_enrichment.py
│   ├── test_dedup.py
│   └── adapters/
│       ├── test_greenhouse.py
│       ├── test_kenya_airways.py
│       └── ...
└── examples/
    ├── fastapi_integration.py
    ├── standalone_scrape.py
    └── ijobs_integration.py
```

### 2.2 pyproject.toml

```toml
[project]
name = "ijobs-scraper"
version = "0.1.0"
description = "Job scraping & AI enrichment engine for African job markets"
requires-python = ">=3.12"
license = "MIT"
authors = [{name = "iWorldAfric"}]
readme = "README.md"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "croniter>=2.0",
]

[project.optional-dependencies]
browser = ["playwright>=1.40"]
careerjet = ["careerjet-api>=3.0"]
pdf = ["pdfplumber>=0.10"]
all = ["ijobs-scraper[browser,careerjet,pdf]"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ijobs_scraper"]
```

Core dependencies are minimal: httpx, pydantic, bs4, lxml, croniter. Heavy deps like playwright are optional extras installed with `pip install ijobs-scraper[browser]`.

---

## 3. Diagrams

All diagrams are PlantUML files in `docs/architecture/diagrams/scraper/`.

| Diagram | File | Description |
|---------|------|-------------|
| Package Structure | [`package-structure.puml`](diagrams/scraper/package-structure.puml) | Class diagram showing all modules, protocols, and adapter hierarchy |
| Data Flow | [`data-flow.puml`](diagrams/scraper/data-flow.puml) | Activity diagram of the auto scraper pipeline (fetch → dedup → enrich → callback) |
| Integration | [`integration.puml`](diagrams/scraper/integration.puml) | Component diagram showing how ijobs-scraper connects to external sources, OpenAI, and the iJobs backend |
| Manual Scraper Sequence | [`manual-scraper-sequence.puml`](diagrams/scraper/manual-scraper-sequence.puml) | Sequence diagram of the manual URL parsing flow (user → frontend → API → engine → OpenAI → response) |
| Database Schema | [`db-schema.puml`](diagrams/scraper/db-schema.puml) | ER diagram of ingestion tables (iJobs side) and their relationship to the jobs table |

To render locally: `plantuml docs/architecture/diagrams/scraper/*.puml`

---

## 4. Public API & Core Interfaces

Everything consumers need is importable from the top-level package:

```python
from ijobs_scraper import (
    # Core engine
    ScraperEngine,

    # Data models
    RawListing, EnrichedJob, ScrapeResult, SourceConfig,

    # Protocols (host app implements these)
    AIProvider, StorageBackend, JobCallback,

    # Adapter system
    AdapterRegistry, BaseAdapter,

    # Exceptions
    ScraperError, AdapterError, EnrichmentError, DuplicateJobError,

    # Scheduler
    get_due_sources,
)
```

### 4.1 ScraperEngine

The primary entry point. Coordinates adapters, enrichment, dedup, and output.

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

### 4.2 Protocol Interfaces

These are the interfaces the host application implements. They use Python `Protocol` for structural subtyping — no inheritance required.

#### AIProvider

```python
class AIProvider(Protocol):
    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Send prompts + JSON schema, return parsed response.

        Implementation should use OpenAI's response_format with
        json_schema for guaranteed type-safe extraction.
        """
        ...
```

#### StorageBackend

```python
class StorageBackend(Protocol):
    async def get_known_urls(self, source_slug: str) -> set[str]:
        """Return external_urls already scraped for this source."""
        ...

    async def save_raw_listing(self, source_slug: str, listing: RawListing) -> None:
        """Persist raw scraped data before enrichment."""
        ...

    async def mark_duplicate(self, source_slug: str, listing: RawListing, existing_url: str) -> None:
        """Record that this listing is a duplicate."""
        ...

    async def check_content_hash(self, content_hash: str) -> bool:
        """Return True if this content hash already exists (cross-source dedup)."""
        ...
```

#### JobCallback

```python
class JobCallback(Protocol):
    async def __call__(
        self,
        job: EnrichedJob,
        source: SourceConfig,
        raw: RawListing,
    ) -> None:
        """Handle a newly enriched job.

        Host app implements this to persist to DB,
        trigger notifications, update search indexes, etc.
        """
        ...
```

---

## 5. Data Models

All models use Pydantic v2 for validation and serialization.

### 5.1 SourceConfig

```python
class SourceType(str, Enum):
    API = "api"
    HTML = "html"
    BROWSER = "browser"
    RSS = "rss"

class SourceConfig(BaseModel):
    name: str                          # "Kenya Airways"
    slug: str                          # "kenya-airways"
    adapter: str                       # "kenya_airways" or "greenhouse"
    source_type: SourceType
    base_url: str
    cron_schedule: str | None = None   # "0 */6 * * *"
    is_active: bool = True
    config: dict[str, Any] = {}        # Adapter-specific config
    # Examples:
    #   Greenhouse: {"board_token": "oneacrefund"}
    #   SmartRecruiters: {"company_slug": "AmrefHealthAfrica4"}
    #   Workday: {"tenant": "absa", "instance": "AbsaCareers"}
```

### 5.2 RawListing

```python
class RawListing(BaseModel):
    external_id: str | None = None
    external_url: str
    title: str | None = None
    raw_html: str | None = None
    raw_json: dict[str, Any] | None = None
    raw_text: str | None = None
    company_name: str | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### 5.3 EnrichedJob

Output of the OpenAI structured extraction pipeline:

```python
class EnrichedJob(BaseModel):
    title: str
    description: str
    company_name: str
    company_website: str | None = None
    location: str | None = None
    remote_type: Literal["onsite", "hybrid", "remote"] = "onsite"
    employment_type: Literal["full_time", "part_time", "contract", "internship"] = "full_time"
    experience_level: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str = "KES"
    skills: list[str] = []
    benefits: list[str] = []
    category: str | None = None
    requirements: JobRequirements | None = None
    number_of_openings: int | None = None  # Post-validated to default to 1 when absent
    application_instructions: str | None = None
    external_url: str
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    content_hash: str
    source_slug: str

class JobRequirements(BaseModel):
    education_level: str | None = None
    min_years_experience: int | None = None
    certifications: list[str] = []
    languages: list[str] = []
    key_responsibilities: list[str] = []
    minimum_qualifications: list[str] = []
    preferred_qualifications: list[str] = []
```

### 5.4 ScrapeResult

```python
class ScrapeResult(BaseModel):
    source_slug: str
    status: Literal["completed", "partial", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    jobs_found: int = 0
    jobs_created: int = 0
    jobs_duplicated: int = 0
    jobs_failed: int = 0
    errors: list[str] = []
```

---

## 6. Adapter System

Each portal source is encapsulated in an adapter class. Adapters are responsible **only** for fetching raw listings. They know nothing about enrichment, dedup, or storage.

> See: [`package-structure.puml`](diagrams/scraper/package-structure.puml)

### 6.1 Base Adapter

```python
class BaseAdapter(ABC):
    @abstractmethod
    async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]:
        """Yield raw job listings from the source."""
        ...

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Optionally fetch full job details. Default: return as-is."""
        return listing

    def can_handle_url(self, url: str) -> bool:
        """Return True if this adapter can parse the given URL (for manual scraper)."""
        return False
```

### 6.2 Specialized Base Classes

```python
class APIAdapter(BaseAdapter):
    """Base for REST API sources. Provides httpx client management."""
    async def _get(self, url, params=None, headers=None) -> dict: ...
    async def _post(self, url, json=None, headers=None) -> dict: ...

class HTMLAdapter(BaseAdapter):
    """Base for BeautifulSoup HTML scraping."""
    async def _fetch_page(self, url) -> BeautifulSoup: ...

class BrowserAdapter(BaseAdapter):
    """Base for Playwright browser automation."""
    async def _launch_browser(self) -> Page: ...
```

### 6.3 Adapter Registry

```python
class AdapterRegistry:
    _adapters: dict[str, type[BaseAdapter]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(adapter_cls):
            cls._adapters[name] = adapter_cls
            return adapter_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> type[BaseAdapter]: ...

    @classmethod
    def detect_from_url(cls, url: str) -> type[BaseAdapter] | None:
        """Auto-detect adapter from URL domain."""
        ...
```

### 6.4 Example: Greenhouse Adapter

```python
@AdapterRegistry.register("greenhouse")
class GreenhouseAdapter(APIAdapter):
    """Reusable for any Greenhouse-powered career board."""
    BOARDS_API = "https://boards-api.greenhouse.io/v1/boards"

    async def fetch_listings(self, config):
        token = config.config["board_token"]
        data = await self._get(f"{self.BOARDS_API}/{token}/jobs", params={"content": "true"})
        for job in data.get("jobs", []):
            yield RawListing(
                external_id=str(job["id"]),
                external_url=job["absolute_url"],
                title=job.get("title"),
                raw_json=job,
                company_name=config.name,
            )

    def can_handle_url(self, url):
        return "greenhouse.io" in url
```

### 6.5 Adapter Catalog

| Adapter | Class | Type | Reusable | Sources |
|---------|-------|------|----------|---------|
| `kenya_airways` | KenyaAirwaysAdapter | API | No | Kenya Airways iRec API |
| `greenhouse` | GreenhouseAdapter | API | **Yes** | One Acre Fund + any Greenhouse employer |
| `smartrecruiters` | SmartRecruitersAdapter | API | **Yes** | Amref + any SR employer |
| `careerjet` | CareerjetAdapter | API | **Yes** | 60+ indexed sites via Careerjet API |
| `reliefweb` | ReliefWebAdapter | API | No | ReliefWeb UN jobs (Kenya filter) |
| `brightermonday` | BrighterMondayAdapter | HTML | No | BrighterMonday Kenya (Laravel, CSRF) |
| `myjobmag` | MyJobMagAdapter | HTML | No | MyJobMag Kenya (PHP) |
| `mygov` | MyGovAdapter | HTML | No | MyGov Kenya /job-adverts |
| `fuzu` | FuzuAdapter | HTML | No | Fuzu Kenya (Rails, server-rendered) |
| `kcb` | KCBAdapter | HTML | No | KCB Bank careers (PHP) |
| `workday` | WorkdayAdapter | Browser | **Yes** | Absa, NCBA + any Workday employer |
| `impactpool` | ImpactpoolAdapter | Browser | No | Impactpool Kenya jobs |
| `world_vision` | WorldVisionAdapter | Browser | No | World Vision careers |

---

## 7. OpenAI Enrichment Pipeline

The enrichment pipeline takes raw scraped content and uses OpenAI structured outputs to extract validated, SEO-optimized job data.

> See: [`manual-scraper-sequence.puml`](diagrams/scraper/manual-scraper-sequence.puml) for the full flow.

### 7.1 Pipeline Steps

1. Raw listing received (HTML, JSON, or plain text)
2. Content cleaned and truncated (max 15,000 chars to fit context window)
3. System prompt + user prompt constructed with raw content
4. Sent to `AIProvider.structured_extract()` with JSON schema enforcement
5. Response parsed into `EnrichedJob` Pydantic model
6. Content hash computed (SHA-256 of normalized title + company + location)
7. Validation against field constraints (max lengths, enum values)

### 7.2 JSON Schema for Structured Extraction

Passed to OpenAI's `response_format` with `strict: true`:

```python
EXTRACTION_SCHEMA = {
    "name": "job_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "required": ["title", "description", "company_name", "location",
                     "remote_type", "employment_type", "category", "skills"],
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "company_name": {"type": "string"},
            "company_website": {"type": ["string", "null"]},
            "location": {"type": ["string", "null"]},
            "remote_type": {"type": "string", "enum": ["onsite", "hybrid", "remote"]},
            "employment_type": {"type": "string",
                "enum": ["full_time", "part_time", "contract", "internship"]},
            "experience_level": {"type": ["string", "null"]},
            "salary_min": {"type": ["integer", "null"]},
            "salary_max": {"type": ["integer", "null"]},
            "currency": {"type": "string"},
            "skills": {"type": "array", "items": {"type": "string"}},
            "benefits": {"type": "array", "items": {"type": "string"}},
            "category": {"type": "string", "enum": [
                "technology-engineering", "it-support-helpdesk",
                "finance-accounting", "banking-insurance",
                "sales-business-development", "marketing-communications",
                "healthcare-medical", "education-training",
                "legal-compliance", "human-resources",
                "administration-secretarial", "supply-chain-logistics",
                "engineering-construction", "ngo-un-development",
                "internships-attachments"
            ]},
            "requirements": {
                "type": ["object", "null"],
                "properties": {
                    "education_level": {"type": ["string", "null"]},
                    "min_years_experience": {"type": ["integer", "null"]},
                    "certifications": {"type": "array", "items": {"type": "string"}},
                    "languages": {"type": "array", "items": {"type": "string"}}
                }
            },
            "posted_at": {"type": ["string", "null"]},
            "expires_at": {"type": ["string", "null"]}
        },
        "additionalProperties": False
    }
}
```

### 7.3 System Prompt

```
You are a job listing data extractor and SEO optimizer for the African job market.

Given raw job listing content (HTML, JSON, or text), extract all fields into the
required JSON schema. Follow these rules:

1. TITLE: Create a clear, SEO-friendly title. Remove company name from title.
   Keep under 200 characters.
2. DESCRIPTION: Clean up HTML, remove navigation/footer cruft, format with
   proper paragraphs. Optimize for search visibility.
3. LOCATION: Normalize to "City, Country" format. Default country is Kenya.
4. SALARY: Extract min/max as integers. Convert monthly to annual if specified.
   Default currency is KES unless explicitly stated otherwise.
5. SKILLS: Extract specific technical and soft skills mentioned.
6. CATEGORY: Map to the closest matching category from the enum list.
7. EMPLOYMENT TYPE: Infer from context if not explicit.
8. If a field cannot be determined, use null.
```

### 7.4 Host App AIProvider Implementation (iJobs Example)

```python
class IJobsAIProvider:
    """Bridges ijobs_scraper.AIProvider to iJobs OpenAIProvider."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini"):
        self.api_key = api_key
        self.model = model

    async def structured_extract(self, system_prompt, user_prompt, json_schema):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "response_format": {
                "type": "json_schema",
                "json_schema": json_schema,
            },
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload, headers=headers
            )
        return json.loads(resp.json()["choices"][0]["message"]["content"])
```

---

## 8. Deduplication Strategy

> See: [`data-flow.puml`](diagrams/scraper/data-flow.puml) for where dedup fits in the pipeline.

### 8.1 Three-Layer Approach

| Layer | Method | Scope | Implementation |
|-------|--------|-------|----------------|
| 1 | Source URL uniqueness | Same source | `external_url + source_slug` check via `StorageBackend.get_known_urls()` |
| 2 | Content fingerprint | Cross-source | SHA-256 of `normalized(title + company + location)` via `StorageBackend.check_content_hash()` |
| 3 | Fuzzy title matching | Cross-source | Optional: `pg_trgm` similarity > 0.8 on title within same company (host app responsibility) |

### 8.2 Content Hash Algorithm

```python
import hashlib

def compute_content_hash(title: str, company: str, location: str | None) -> str:
    normalized = "|".join([
        title.lower().strip(),
        company.lower().strip(),
        (location or "").lower().strip(),
    ])
    return hashlib.sha256(normalized.encode()).hexdigest()
```

### 8.3 Dedup Flow

1. **Layer 1:** Is this `external_url` already known for this source? If yes → skip.
2. Fetch and enrich the listing via OpenAI pipeline.
3. Compute `content_hash` from enriched data.
4. **Layer 2:** Does this `content_hash` exist? If yes → mark as duplicate.
5. **Layer 3 (optional):** Host app runs fuzzy matching after job creation.

Layer 3 is intentionally left to the host app because it requires database-level operations (`pg_trgm`) that the standalone package doesn't own.

---

## 9. Engine Orchestration

> See: [`data-flow.puml`](diagrams/scraper/data-flow.puml)

### 9.1 Auto Scrape (scrape_source)

```python
async def scrape_source(self, source: SourceConfig) -> ScrapeResult:
    result = ScrapeResult(source_slug=source.slug, started_at=now())
    adapter = AdapterRegistry.get(source.adapter)()
    known_urls = set()
    if self.storage:
        known_urls = await self.storage.get_known_urls(source.slug)

    async for listing in adapter.fetch_listings(source):
        result.jobs_found += 1

        # Layer 1 dedup
        if listing.external_url in known_urls:
            result.jobs_duplicated += 1
            continue

        try:
            listing = await adapter.fetch_detail(listing, source)
            enriched = await self._enrich(listing, source)

            # Layer 2 dedup
            if self.storage and await self.storage.check_content_hash(enriched.content_hash):
                result.jobs_duplicated += 1
                continue

            if self.storage:
                await self.storage.save_raw_listing(source.slug, listing)
            if self.on_job:
                await self.on_job(enriched, source, listing)
            result.jobs_created += 1

        except Exception as e:
            result.jobs_failed += 1
            result.errors.append(f"{listing.external_url}: {e}")

    result.status = "completed" if not result.errors else "partial"
    result.completed_at = now()
    return result
```

### 9.2 Manual Scrape (parse_url)

```python
async def parse_url(self, url: str, hint: str | None = None) -> EnrichedJob:
    if hint:
        adapter_cls = AdapterRegistry.get(hint)
    else:
        adapter_cls = AdapterRegistry.detect_from_url(url)
    if not adapter_cls:
        raise AdapterError(f"No adapter found for URL: {url}")

    adapter = adapter_cls()
    source = SourceConfig(name="manual", slug="manual", adapter=hint or "auto",
                          source_type=SourceType.HTML, base_url=url)

    listing = RawListing(external_url=url)
    listing = await adapter.fetch_detail(listing, source)
    return await self._enrich(listing, source)
```

---

## 10. iJobs Backend Integration

> See: [`integration.puml`](diagrams/scraper/integration.puml)

### 10.1 Installation

```toml
# In iJobs pyproject.toml, add to dependencies:
"ijobs-scraper[all]>=0.1.0",
```

### 10.2 New Files in iJobs Backend

```
src/app/
  services/
    scraper_bridge.py            # AIProvider + StorageBackend + JobCallback implementations
  worker/tasks/
    scrape_source.py             # Background task: scrape a single source
    scrape_scheduled.py          # Background task: enqueue all due sources
  api/v1/endpoints/
    scraper.py                   # POST /scraper/parse-url
    admin_scraper.py             # Admin source management endpoints
  schemas/
    scraper.py                   # Request/response Pydantic schemas
  repositories/
    scraper_repository.py        # DB operations for ingestion tables
migrations/versions/
    xxxx_add_ingestion_tables.py
```

### 10.3 Bridge Implementation

```python
# src/app/services/scraper_bridge.py
from ijobs_scraper import ScraperEngine, EnrichedJob, SourceConfig, RawListing
from app.db.session import AsyncSessionLocal
from app.db.models import Job, Company
from app.constants.jobs import JobStatus

class IJobsAIProvider:
    """Implements ijobs_scraper.AIProvider using iJobs OpenAI config."""
    # ... (see section 7.4)

class IJobsStorage:
    """Implements ijobs_scraper.StorageBackend using iJobs database."""
    def __init__(self, session):
        self.session = session

    async def get_known_urls(self, source_slug):
        # SELECT external_url FROM ingestion_jobs WHERE source_slug = ...
        ...

    async def check_content_hash(self, content_hash):
        # SELECT 1 FROM ingestion_jobs WHERE content_hash = ...
        ...

async def handle_new_job(job: EnrichedJob, source: SourceConfig, raw: RawListing):
    """JobCallback: creates a Job record in iJobs database."""
    async with AsyncSessionLocal() as session:
        company = await find_or_create_company(session, job.company_name, job.company_website)
        db_job = Job(
            company_id=company.id,
            title=job.title,
            description=job.description,
            location=job.location,
            remote_type=job.remote_type,
            employment_type=job.employment_type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            currency=job.currency,
            skills=job.skills,
            benefits=job.benefits,
            category=job.category,
            external_url=job.external_url,
            posted_at=job.posted_at,
            expires_at=job.expires_at,
            status=JobStatus.PENDING,
            source="scraped",
        )
        session.add(db_job)
        await session.commit()
```

### 10.4 Background Task

```python
# src/app/worker/tasks/scrape_source.py
from app.worker.registry import TaskRegistry
from ijobs_scraper import ScraperEngine, SourceConfig

@TaskRegistry.register("scrape_source")
async def scrape_source_task(payload: dict) -> None:
    source = SourceConfig(**payload["source_config"])
    engine = ScraperEngine(
        ai_provider=IJobsAIProvider(settings.OPENAI_API_KEY, settings.OPENAI_MODEL),
        storage=IJobsStorage(session),
        on_job=handle_new_job,
    )
    result = await engine.scrape_source(source)
    await save_run_result(source.slug, result)
```

### 10.5 Database Schema (iJobs Side)

> See: [`db-schema.puml`](diagrams/scraper/db-schema.puml)

These tables live in the iJobs backend, not in the package:

#### ingestion_sources

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | gen_random_uuid() |
| name | VARCHAR | Human-readable name |
| slug | VARCHAR UNIQUE | URL-safe identifier |
| adapter | VARCHAR | Adapter name from registry |
| source_type | VARCHAR | api / html / browser / rss |
| config | JSONB | Adapter-specific config |
| cron_schedule | VARCHAR (nullable) | Cron expression |
| is_active | BOOLEAN | Default true |
| last_run_at | TIMESTAMPTZ (nullable) | Updated after each run |
| last_success_at | TIMESTAMPTZ (nullable) | Last successful run |
| total_jobs_scraped | INTEGER | Running total |
| error_count | INTEGER | Consecutive failures |
| created_at / updated_at | TIMESTAMPTZ | Auto-managed |

#### ingestion_runs

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | gen_random_uuid() |
| source_id | UUID FK | References ingestion_sources |
| status | VARCHAR | running / completed / failed / partial |
| jobs_found | INTEGER | Total listings found |
| jobs_created | INTEGER | New jobs created |
| jobs_duplicated | INTEGER | Duplicates skipped |
| jobs_failed | INTEGER | Failed enrichments |
| started_at | TIMESTAMPTZ | Run start |
| completed_at | TIMESTAMPTZ (nullable) | Run end |
| errors | JSONB (nullable) | Array of error messages |

#### ingestion_jobs

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | gen_random_uuid() |
| source_id | UUID FK | References ingestion_sources |
| run_id | UUID FK (nullable) | References ingestion_runs |
| external_url | VARCHAR | Source URL |
| content_hash | VARCHAR | SHA-256 for cross-source dedup |
| status | VARCHAR | scraped / enriched / created / duplicate / failed |
| job_id | UUID FK (nullable) | References jobs table after creation |
| raw_content | TEXT (nullable) | Raw HTML/JSON snapshot |
| created_at / updated_at | TIMESTAMPTZ | Auto-managed |

**Constraints:**
- `UNIQUE(source_id, external_url)` — Layer 1 dedup
- `INDEX ON content_hash` — Layer 2 dedup

#### Modifications to existing tables

- `jobs.source`: Add `"scraped"` to `JobSource` enum
- `jobs.ingestion_source_id`: New nullable FK to `ingestion_sources`

---

## 11. Cron Scheduling

The package includes schedule evaluation logic. Actual task enqueueing is the host app's responsibility.

### Package side

```python
# ijobs_scraper/scheduler.py
from croniter import croniter

def get_due_sources(
    sources: list[SourceConfig],
    last_runs: dict[str, datetime],
) -> list[SourceConfig]:
    now = datetime.now(UTC)
    due = []
    for source in sources:
        if not source.cron_schedule or not source.is_active:
            continue
        last = last_runs.get(source.slug)
        if last is None:
            due.append(source)
            continue
        cron = croniter(source.cron_schedule, last)
        if cron.get_next(datetime) <= now:
            due.append(source)
    return due
```

### Host app side

```python
@TaskRegistry.register("scrape_scheduled")
async def scrape_scheduled_task(payload: dict) -> None:
    from ijobs_scraper import get_due_sources

    sources = await load_active_sources(session)
    last_runs = await get_last_run_times(session)
    for source in get_due_sources(sources, last_runs):
        await enqueue_job(session, "scrape_source",
                          payload={"source_config": source.model_dump()})
    await session.commit()
```

The `scrape_scheduled` task itself runs on a fixed interval (e.g., every 5 minutes) via the worker loop.

---

## 12. Admin API Endpoints (iJobs Side)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/scraper/sources` | superadmin | List all sources with stats |
| POST | `/admin/scraper/sources` | superadmin | Create new source |
| PATCH | `/admin/scraper/sources/{id}` | superadmin | Update config or cron |
| DELETE | `/admin/scraper/sources/{id}` | superadmin | Deactivate source |
| POST | `/admin/scraper/sources/{id}/trigger` | superadmin | Manual trigger |
| GET | `/admin/scraper/runs` | superadmin | List recent runs |
| GET | `/admin/scraper/runs/{id}` | superadmin | Run detail with errors |
| GET | `/admin/settings/ai` | superadmin | View AI config |
| PUT | `/admin/settings/ai` | superadmin | Update OpenAI key/model |
| POST | `/scraper/parse-url` | authenticated | Manual URL parser |

---

## 13. Error Handling & Resilience

### 13.1 Exception Hierarchy

```python
class ScraperError(Exception):
    """Base exception for all scraper errors."""

class AdapterError(ScraperError):
    def __init__(self, adapter: str, message: str, retryable: bool = True): ...

class EnrichmentError(ScraperError):
    """AI enrichment failed."""

class DuplicateJobError(ScraperError):
    def __init__(self, content_hash: str, existing_url: str | None = None): ...

class RateLimitError(AdapterError):
    def __init__(self, adapter: str, retry_after: int | None = None): ...
```

### 13.2 Per-Job Error Isolation

A single failed job never stops the batch. The engine catches exceptions per-listing, logs them, increments `jobs_failed`, and continues. `ScrapeResult.errors` captures all failures.

### 13.3 Rate Limiting

Each adapter base class includes configurable rate limiting:

- **APIAdapter:** configurable delay between requests (default 1s)
- **HTMLAdapter:** configurable delay (default 2s) + random jitter
- **BrowserAdapter:** page load timeout + delay between navigations

On HTTP 429, the adapter raises `RateLimitError` with `retry_after`. The engine can wait or abort for later retry.

### 13.4 Circuit Breaker (Host App)

The host app tracks consecutive failures in `ingestion_sources.error_count` and auto-disables sources that exceed a threshold.

---

## 14. Implementation Phases

### Phase 1: Package Foundation (Week 1–2)

- Set up repository with pyproject.toml and hatchling
- Implement core models, protocols, and exceptions
- Build ScraperEngine orchestrator
- Build enrichment pipeline with OpenAI schema
- Implement dedup module (Layer 1 + 2)
- Build BaseAdapter, APIAdapter, HTMLAdapter, BrowserAdapter
- Unit tests with mock AI provider
- **Deliverable:** `pip install ijobs-scraper` works with stub adapter

### Phase 2: API Adapters (Week 2–3)

- Kenya Airways iRec adapter
- Greenhouse adapter (tested with One Acre Fund)
- SmartRecruiters adapter (tested with Amref: AmrefHealthAfrica4)
- Careerjet adapter via official Python SDK
- ReliefWeb adapter (appname approved by now)
- Integration tests against live APIs
- **Deliverable:** 5 API sources returning enriched jobs

### Phase 3: HTML Scrapers (Week 3–4)

- BrighterMonday adapter (Laravel, CSRF handling)
- MyJobMag adapter (PHP, simple HTML)
- MyGov adapter (/job-adverts)
- Fuzu adapter (Rails server-rendered)
- KCB Bank adapter
- **Deliverable:** 5 HTML scrapers with error handling

### Phase 4: Browser Scrapers (Week 4–5)

- Workday adapter (reusable for Absa, NCBA)
- Impactpool adapter
- World Vision adapter
- **Deliverable:** 3 browser scrapers with Playwright

### Phase 5: iJobs Integration (Week 5–6)

- Add `ijobs-scraper[all]` to iJobs dependencies
- Implement bridge classes
- Alembic migration for ingestion tables
- Add `"scraped"` to JobSource enum
- Background tasks: `scrape_source`, `scrape_scheduled`
- Admin API endpoints
- Manual scraper endpoint
- **Deliverable:** End-to-end scraping in iJobs

### Phase 6: Polish & Launch (Week 6–8)

- Publish v0.1.0 to PyPI
- README with quickstart and API docs
- Monitoring: structured logging, metrics, alerting
- Performance tuning: connection pooling, batch sizes
- Load testing and cron optimization
- **Deliverable:** Production-ready on PyPI

---

## 15. Dependencies

| Package | Purpose | Extra? | Notes |
|---------|---------|--------|-------|
| httpx >= 0.27 | Async HTTP client | Core | All API and HTML adapters |
| pydantic >= 2.0 | Data models | Core | All models, configs, results |
| beautifulsoup4 >= 4.12 | HTML parsing | Core | HTML adapters |
| lxml >= 5.0 | Fast parser backend | Core | BS4 speed |
| croniter >= 2.0 | Cron expressions | Core | Schedule evaluation |
| playwright >= 1.40 | Browser automation | `[browser]` | JS-rendered sites |
| careerjet-api >= 3.0 | Careerjet SDK | `[careerjet]` | Official API |
| pdfplumber >= 0.10 | PDF extraction | `[pdf]` | Government gazettes |

**No framework deps.** Zero dependency on FastAPI, SQLAlchemy, Django, or any web framework.

---

## 16. Monitoring & Observability

The package uses Python's standard `logging` module by default but accepts any logger with `.info()`, `.warning()`, `.error()` methods (structlog compatible).

### Structured Log Events

| Event | Level | Fields |
|-------|-------|--------|
| `scrape_source_started` | INFO | source_slug, adapter, source_type |
| `listing_fetched` | DEBUG | source_slug, external_url, title |
| `listing_enriched` | INFO | source_slug, external_url, title, category |
| `listing_duplicate` | INFO | source_slug, external_url, content_hash, layer |
| `listing_failed` | WARNING | source_slug, external_url, error |
| `enrichment_token_usage` | INFO | model, prompt_tokens, completion_tokens |
| `scrape_source_completed` | INFO | source_slug, jobs_found, jobs_created, duration_s |
| `adapter_rate_limited` | WARNING | adapter, retry_after |

### Metrics (Host App)

The `ScrapeResult` model provides all data needed for dashboards: jobs per source, duplicate rates, failure rates, AI token usage, run durations.
