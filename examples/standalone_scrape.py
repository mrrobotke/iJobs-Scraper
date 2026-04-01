"""Standalone scrape example — scrape One Acre Fund via Greenhouse adapter.

This example demonstrates how to use ijobs-scraper without any web framework
or database. It uses a stub AI provider that returns mock enrichment data,
so it runs without live API keys.

Usage:
    python examples/standalone_scrape.py
"""

from __future__ import annotations

import asyncio
from typing import Any

from ijobs_scraper import (
    AIProvider,
    EnrichedJob,
    RawListing,
    ScraperEngine,
    SourceConfig,
)
from ijobs_scraper.models import SourceType


class StubAIProvider:
    """Mock AI provider that returns plausible enrichment data.

    Implements the AIProvider protocol without calling any external API.
    Useful for testing, development, and CI.
    """

    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Return mock enriched job data extracted from the raw content."""
        return {
            "title": "Program Associate",
            "description": "Join our team to support agricultural programs across East Africa.",
            "company_name": "One Acre Fund",
            "company_website": "https://oneacrefund.org",
            "location": "Nairobi, Kenya",
            "remote_type": "hybrid",
            "employment_type": "full_time",
            "experience_level": "Mid-level",
            "salary_min": None,
            "salary_max": None,
            "currency": "KES",
            "skills": ["program management", "data analysis", "stakeholder engagement"],
            "benefits": ["health insurance", "professional development"],
            "category": "ngo-un-development",
            "requirements": {
                "education_level": "Bachelor's degree",
                "min_years_experience": 3,
                "certifications": [],
                "languages": ["English"],
            },
            "posted_at": None,
            "expires_at": None,
        }


# Verify StubAIProvider satisfies the AIProvider protocol
_: type[AIProvider] = StubAIProvider  # type: ignore[assignment]


async def main() -> None:
    """Scrape One Acre Fund jobs and print results."""
    source = SourceConfig(
        name="One Acre Fund",
        slug="one-acre-fund",
        adapter="greenhouse",
        source_type=SourceType.API,
        base_url="https://boards-api.greenhouse.io",
        config={"board_token": "oneacrefund"},
    )

    engine = ScraperEngine(ai_provider=StubAIProvider())

    collected_jobs: list[EnrichedJob] = []

    async def collect_job(job: EnrichedJob, source: SourceConfig, raw: RawListing) -> None:
        collected_jobs.append(job)
        print(f"  [{job.category}] {job.title} @ {job.company_name} — {job.location}")

    engine._on_job = collect_job

    print(f"Scraping {source.name} via Greenhouse API...")
    result = await engine.scrape_source(source)

    print(
        f"\nDone! {result.jobs_found} found, {result.jobs_created} created, "
        f"{result.jobs_duplicated} duplicates, {result.jobs_failed} failed."
    )
    if result.errors:
        print(f"Errors: {result.errors[:3]}")


if __name__ == "__main__":
    asyncio.run(main())
