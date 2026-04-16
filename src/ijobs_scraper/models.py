"""Pydantic v2 data models for ijobs-scraper."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    """Classification of how a source is scraped."""

    API = "api"
    HTML = "html"
    BROWSER = "browser"
    RSS = "rss"


class SourceConfig(BaseModel):
    """Configuration for a single job portal source."""

    name: str
    slug: str
    adapter: str
    source_type: SourceType
    base_url: str
    cron_schedule: str | None = None
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class RawListing(BaseModel):
    """Raw job listing data as fetched from a source, before enrichment."""

    external_id: str | None = None
    external_url: str
    title: str | None = None
    raw_html: str | None = None
    raw_json: dict[str, Any] | None = None
    raw_text: str | None = None
    company_name: str | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobRequirements(BaseModel):
    """Structured requirements extracted from a job listing."""

    education_level: str | None = None
    min_years_experience: int | None = None
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    key_responsibilities: list[str] = Field(default_factory=list)
    minimum_qualifications: list[str] = Field(default_factory=list)
    preferred_qualifications: list[str] = Field(default_factory=list)


class EnrichedJob(BaseModel):
    """Fully enriched job data after AI extraction and validation."""

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
    skills: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    category: str | None = None
    requirements: JobRequirements | None = None
    external_url: str
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    content_hash: str
    source_slug: str
    number_of_openings: int | None = None
    application_instructions: str | None = None


class ScrapeResult(BaseModel):
    """Summary of a single source scrape run."""

    source_slug: str
    status: Literal["completed", "partial", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    jobs_found: int = 0
    jobs_created: int = 0
    jobs_duplicated: int = 0
    jobs_failed: int = 0
    errors: list[str] = Field(default_factory=list)
