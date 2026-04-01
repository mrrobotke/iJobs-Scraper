"""OpenAI enrichment pipeline for raw job listings.

Takes raw scraped content and uses the host app's AIProvider to extract
structured, validated job data via JSON schema enforcement.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from ijobs_scraper.dedup import compute_content_hash
from ijobs_scraper.exceptions import EnrichmentError
from ijobs_scraper.models import EnrichedJob, JobRequirements, RawListing, SourceConfig
from ijobs_scraper.protocols import AIProvider

MAX_CONTENT_LENGTH = 15_000

SYSTEM_PROMPT = """\
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
8. If a field cannot be determined, use null.\
"""

EXTRACTION_SCHEMA: dict[str, Any] = {
    "name": "job_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "required": [
            "title",
            "description",
            "company_name",
            "location",
            "remote_type",
            "employment_type",
            "category",
            "skills",
        ],
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "company_name": {"type": "string"},
            "company_website": {"type": ["string", "null"]},
            "location": {"type": ["string", "null"]},
            "remote_type": {
                "type": "string",
                "enum": ["onsite", "hybrid", "remote"],
            },
            "employment_type": {
                "type": "string",
                "enum": ["full_time", "part_time", "contract", "internship"],
            },
            "experience_level": {"type": ["string", "null"]},
            "salary_min": {"type": ["integer", "null"]},
            "salary_max": {"type": ["integer", "null"]},
            "currency": {"type": "string"},
            "skills": {"type": "array", "items": {"type": "string"}},
            "benefits": {"type": "array", "items": {"type": "string"}},
            "category": {
                "type": "string",
                "enum": [
                    "technology-engineering",
                    "it-support-helpdesk",
                    "finance-accounting",
                    "banking-insurance",
                    "sales-business-development",
                    "marketing-communications",
                    "healthcare-medical",
                    "education-training",
                    "legal-compliance",
                    "human-resources",
                    "administration-secretarial",
                    "supply-chain-logistics",
                    "engineering-construction",
                    "ngo-un-development",
                    "internships-attachments",
                ],
            },
            "requirements": {
                "type": ["object", "null"],
                "properties": {
                    "education_level": {"type": ["string", "null"]},
                    "min_years_experience": {"type": ["integer", "null"]},
                    "certifications": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "education_level",
                    "min_years_experience",
                    "certifications",
                    "languages",
                ],
                "additionalProperties": False,
            },
            "posted_at": {"type": ["string", "null"]},
            "expires_at": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    },
}


def clean_content(raw: RawListing) -> str:
    """Extract text content from a raw listing, stripping HTML and truncating.

    Priority: raw_json > raw_html > raw_text. Truncates to 15,000 chars.
    """
    if raw.raw_json is not None:
        text = json.dumps(raw.raw_json, indent=2, default=str)
    elif raw.raw_html is not None:
        soup = BeautifulSoup(raw.raw_html, "lxml")
        text = " ".join(soup.get_text(separator=" ", strip=True).split())
    elif raw.raw_text is not None:
        text = raw.raw_text
    else:
        text = raw.title or ""

    return text[:MAX_CONTENT_LENGTH]


def _parse_datetime(value: str | None) -> datetime | None:
    """Best-effort ISO datetime parsing. Returns None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


async def enrich(
    raw: RawListing,
    source: SourceConfig,
    ai_provider: AIProvider,
) -> EnrichedJob:
    """Run the AI enrichment pipeline on a raw listing.

    Args:
        raw: The raw listing to enrich.
        source: Source configuration for context.
        ai_provider: Host-provided AI extraction implementation.

    Returns:
        A fully enriched and validated EnrichedJob.

    Raises:
        EnrichmentError: If AI extraction or validation fails.
    """
    content = clean_content(raw)
    if not content:
        raise EnrichmentError("No content available for enrichment")

    company_hint = raw.company_name or source.name
    user_prompt = (
        f"Extract job data from the following listing.\n"
        f"Company: {company_hint}\n"
        f"Source URL: {raw.external_url}\n\n"
        f"Content:\n{content}"
    )

    try:
        extracted = await ai_provider.structured_extract(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_schema=EXTRACTION_SCHEMA,
        )
    except Exception as exc:
        raise EnrichmentError(f"AI extraction failed: {exc}") from exc

    # Parse optional requirements
    requirements = None
    req_data = extracted.get("requirements")
    if req_data and isinstance(req_data, dict):
        requirements = JobRequirements(**req_data)

    content_hash = compute_content_hash(
        title=extracted.get("title", ""),
        company=extracted.get("company_name", ""),
        location=extracted.get("location"),
    )

    try:
        return EnrichedJob(
            title=extracted["title"],
            description=extracted["description"],
            company_name=extracted["company_name"],
            company_website=extracted.get("company_website"),
            location=extracted.get("location"),
            remote_type=extracted.get("remote_type", "onsite"),
            employment_type=extracted.get("employment_type", "full_time"),
            experience_level=extracted.get("experience_level"),
            salary_min=extracted.get("salary_min"),
            salary_max=extracted.get("salary_max"),
            currency=extracted.get("currency", "KES"),
            skills=extracted.get("skills", []),
            benefits=extracted.get("benefits", []),
            category=extracted.get("category"),
            requirements=requirements,
            external_url=raw.external_url,
            posted_at=_parse_datetime(extracted.get("posted_at")),
            expires_at=_parse_datetime(extracted.get("expires_at")),
            content_hash=content_hash,
            source_slug=source.slug,
        )
    except Exception as exc:
        raise EnrichmentError(f"Failed to build EnrichedJob: {exc}") from exc
