"""iJobs backend integration example.

This is a reference for how the iJobs backend integrates the scraper package.
It demonstrates the three Protocol implementations (AIProvider, StorageBackend,
JobCallback) and full engine wiring.

This file is illustrative — it references iJobs backend modules that are not
part of this package.

Requires: pip install ijobs-scraper[all]
"""

from __future__ import annotations

import json
from typing import Any

from ijobs_scraper import (
    EnrichedJob,
    RawListing,
    ScraperEngine,
    SourceConfig,
    get_due_sources,
)

# ---------------------------------------------------------------------------
# 1. AIProvider — bridges to OpenAI via iJobs config
# ---------------------------------------------------------------------------


class IJobsAIProvider:
    """Implements ijobs_scraper.AIProvider using the iJobs OpenAI configuration."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        self.api_key = api_key
        self.model = model

    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Send prompts to OpenAI with JSON schema enforcement."""
        import httpx

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
            "response_format": {"type": "json_schema", "json_schema": json_schema},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()

        content: str = resp.json()["choices"][0]["message"]["content"]
        result: dict[str, Any] = json.loads(content)
        return result


# ---------------------------------------------------------------------------
# 2. StorageBackend — bridges to iJobs database
# ---------------------------------------------------------------------------


class IJobsStorage:
    """Implements ijobs_scraper.StorageBackend using the iJobs database.

    In production, this would receive an async SQLAlchemy session and query
    the ingestion_jobs table for deduplication data.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_known_urls(self, source_slug: str) -> set[str]:
        """Query ingestion_jobs for already-scraped URLs for this source."""
        # SELECT external_url FROM ingestion_jobs
        # JOIN ingestion_sources ON ingestion_jobs.source_id = ingestion_sources.id
        # WHERE ingestion_sources.slug = :source_slug
        return set()  # Placeholder

    async def save_raw_listing(self, source_slug: str, listing: RawListing) -> None:
        """Insert a raw listing record into ingestion_jobs."""
        # INSERT INTO ingestion_jobs (source_id, external_url, raw_content, status)
        # VALUES (:source_id, :external_url, :raw_content, 'scraped')
        pass  # Placeholder

    async def mark_duplicate(
        self, source_slug: str, listing: RawListing, content_hash: str
    ) -> None:
        """Mark a listing as duplicate in ingestion_jobs."""
        # UPDATE ingestion_jobs SET status = 'duplicate'
        # WHERE external_url = :external_url AND source_id = :source_id
        pass  # Placeholder

    async def check_content_hash(self, content_hash: str) -> bool:
        """Check if this content hash already exists (cross-source dedup)."""
        # SELECT 1 FROM ingestion_jobs WHERE content_hash = :content_hash LIMIT 1
        return False  # Placeholder


# ---------------------------------------------------------------------------
# 3. JobCallback — creates a Job record in the iJobs database
# ---------------------------------------------------------------------------


async def handle_new_job(
    job: EnrichedJob,
    source: SourceConfig,
    raw: RawListing,
) -> None:
    """Callback invoked for each enriched job.

    Creates a Job record in the iJobs database with status=pending.
    In production, this would use the iJobs ORM models and session.
    """
    # async with AsyncSessionLocal() as session:
    #     company = await find_or_create_company(session, job.company_name)
    #     db_job = Job(
    #         company_id=company.id,
    #         title=job.title,
    #         description=job.description,
    #         location=job.location,
    #         remote_type=job.remote_type,
    #         employment_type=job.employment_type,
    #         salary_min=job.salary_min,
    #         salary_max=job.salary_max,
    #         skills=job.skills,
    #         external_url=job.external_url,
    #         status=JobStatus.PENDING,
    #         source="scraped",
    #     )
    #     session.add(db_job)
    #     await session.commit()
    print(f"Created job: {job.title} @ {job.company_name}")


# ---------------------------------------------------------------------------
# 4. Engine wiring — putting it all together
# ---------------------------------------------------------------------------


async def create_engine(api_key: str, db_session: Any) -> ScraperEngine:
    """Create a fully-wired ScraperEngine for the iJobs backend."""
    return ScraperEngine(
        ai_provider=IJobsAIProvider(api_key),
        storage=IJobsStorage(db_session),
        on_job=handle_new_job,
        dedup_enabled=True,
    )


# ---------------------------------------------------------------------------
# 5. Background task — scrape all due sources
# ---------------------------------------------------------------------------


async def scrape_scheduled(api_key: str, db_session: Any) -> None:
    """Background task: find due sources and scrape each one.

    Called on a fixed interval (e.g., every 5 minutes) by the worker loop.
    Uses get_due_sources() to evaluate cron schedules.
    """
    from datetime import datetime

    engine = await create_engine(api_key, db_session)

    # In production, load from the ingestion_sources DB table
    all_sources: list[SourceConfig] = []
    last_runs: dict[str, datetime] = {}

    due = get_due_sources(all_sources, last_runs)
    for source in due:
        result = await engine.scrape_source(source)
        print(
            f"[{source.slug}] {result.status}: "
            f"{result.jobs_created} created, {result.jobs_duplicated} dupes"
        )
