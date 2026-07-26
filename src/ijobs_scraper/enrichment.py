"""OpenAI enrichment pipeline for raw job listings.

Takes raw scraped content and uses the host app's AIProvider to extract
structured, validated job data via JSON schema enforcement.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from ijobs_scraper.application_destination import resolve_application_destination
from ijobs_scraper.dedup import compute_content_hash
from ijobs_scraper.exceptions import EnrichmentError
from ijobs_scraper.models import EnrichedJob, JobRequirements, RawListing, SourceConfig
from ijobs_scraper.protocols import AIProvider

# Keep enrichment requests comfortably below provider context and request-size
# limits while preserving enough source material for a useful structured result.
MAX_CONTENT_LENGTH = 16_000

_BLOCK_TAGS = {
    "p",
    "div",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "br",
    "tr",
    "section",
    "article",
    "header",
    "footer",
    "ul",
    "ol",
}


def _html_to_structured_text(html: str) -> str:
    """Convert HTML to text preserving block-level structure, not inline breaks."""
    soup = BeautifulSoup(html, "lxml")
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if href.lower().startswith(("http://", "https://", "mailto:")):
            label = anchor.get_text(" ", strip=True)
            if href not in label:
                anchor.append(NavigableString(f" [{href}]"))
    parts: list[str] = []
    for node in soup.descendants:
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif isinstance(node, Tag) and node.name in _BLOCK_TAGS:
            parts.append("\n")
    raw = "".join(parts)
    # Collapse intra-line whitespace while preserving block boundaries.
    lines = (" ".join(line.split()) for line in raw.splitlines())
    return "\n".join(line for line in lines if line)


def _contains_html(text: str) -> bool:
    """Heuristic: text likely contains HTML markup."""
    return "<" in text and ">" in text


def _normalise_json_values(obj: Any) -> Any:
    """Recursively strip HTML from string values inside a JSON structure.

    Walks dicts and lists, normalising any string leaf that looks like HTML.
    Strings that lack the combination of ``<`` and ``>`` (e.g. ``"< 3 years"``,
    ``"salary > 100k"``, ``"hr@company.com"``) pass through untouched so the
    surrounding text is not silently destroyed.
    """
    if isinstance(obj, dict):
        return {k: _normalise_json_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalise_json_values(i) for i in obj]
    if isinstance(obj, str) and _contains_html(obj):
        return _html_to_structured_text(obj)
    return obj


SYSTEM_PROMPT = """\
You are a senior HR content writer and job data extractor for the African job market.

Your dual role is to (1) extract structured fields from raw job content AND
(2) actively rewrite and enhance the description into a professional, well-formatted
job listing that candidates will want to read.

CONTENT ENHANCEMENT RULES:
- You are NOT just copying content. You are improving it. Write like a skilled recruiter.
- If the raw content is sparse or poorly written, extrapolate professionally from the
  job title, company name, category, and industry norms. Never return thin, generic text.
- Use Markdown formatting throughout. Never return a plain paragraph blob.

FIELD-SPECIFIC RULES:

1. TITLE
   - SEO-friendly, clear, specific. Remove company name from the title.
   - Good: "Senior Data Analyst - Finance" Bad: "Senior Data Analyst at KCB"
   - Max 200 characters.

2. DESCRIPTION
   - MUST be structured Markdown with these sections (use ## headings):
       ## About the Role
       2-4 sentence intro: what this role is, why it matters, what impact the person
       will have. Write this even if raw content lacks it - infer from context.

       ## Key Responsibilities
       Bullet list (- item) of 5-10 specific responsibilities. Extract from content;
       infer plausible duties from this title and category if content is thin.

       ## Requirements
       Bullet list of 5-8 minimum requirements (education, experience, skills).
       Infer from job title, seniority, and industry norms if not stated.

       ## What We Offer
       Bullet list of benefits. Infer plausible benefits for this company type if absent.
   - Minimum 350 words. Expand with inferred professional content if raw is short.
   - Remove all navigation, footer, cookie banners, and unrelated HTML cruft.

3. LOCATION - Normalize to "City, Country". Default country: Kenya.

4. SALARY - Extract min/max as annual integers. Multiply monthly x 12.
   Default currency: KES unless explicitly stated.

5. SKILLS - Extract specific technical AND soft skills. Minimum 5.
   Good: ["Python", "SQL", "data visualization", "stakeholder management"]
   Bad: ["computer skills", "communication"]

6. REQUIREMENTS (structured sub-object):
   - education_level: Highest degree required. Infer from seniority if absent.
   - min_years_experience: Integer. Infer from seniority if absent
     (junior=0-2, mid=3-5, senior=5-8, lead=8+).
   - certifications: Specific certs. Empty array if none.
   - languages: Always include "English" for Kenyan roles.
   - key_responsibilities: Array of 5-10 bullet strings (same as ## Key Responsibilities).
   - minimum_qualifications: Array of 5-8 must-have requirement strings.
   - preferred_qualifications: Array of 3-5 nice-to-have strings. Infer if absent.

7. BENEFITS - Minimum 3. Infer from company type if not stated.

8. CATEGORY - Closest matching enum value.

9. NUMBER OF OPENINGS - Integer. Default 1 if not stated.

10. APPLICATION INSTRUCTIONS - Exact how-to-apply text if present, including any
    employer email address or application link, else null. The Source URL is provenance
    only and must never be treated as an application destination unless the listing text
    explicitly identifies a different application action.

11. EMPLOYMENT TYPE / REMOTE TYPE - Infer from context. Default: full_time / onsite.

12. POSTED AT / EXPIRES AT - ISO 8601 strings if found, else null.\
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
            "company_website",
            "location",
            "remote_type",
            "employment_type",
            "experience_level",
            "salary_min",
            "salary_max",
            "currency",
            "skills",
            "benefits",
            "category",
            "requirements",
            "posted_at",
            "expires_at",
            "number_of_openings",
            "application_instructions",
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
                "anyOf": [
                    {
                        "type": "object",
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
                            "key_responsibilities": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "minimum_qualifications": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "preferred_qualifications": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "education_level",
                            "min_years_experience",
                            "certifications",
                            "languages",
                            "key_responsibilities",
                            "minimum_qualifications",
                            "preferred_qualifications",
                        ],
                        "additionalProperties": False,
                    },
                    {"type": "null"},
                ],
            },
            "posted_at": {"type": ["string", "null"]},
            "expires_at": {"type": ["string", "null"]},
            "number_of_openings": {"type": ["integer", "null"]},
            "application_instructions": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    },
}


def clean_content(raw: RawListing, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """Extract text content from a raw listing, applying block-aware HTML normalisation.

    Priority: raw_json > raw_html > raw_text. Truncates to ``max_length`` chars.
    For raw_json, recurses into the structure and normalises only string
    values that look like HTML, so non-HTML strings containing ``<`` or ``>``
    (salary ranges, emails, etc.) are preserved verbatim.
    """
    if raw.raw_json is not None:
        normalised = _normalise_json_values(raw.raw_json)
        text = json.dumps(normalised, indent=2, default=str)
    elif raw.raw_html is not None:
        text = _html_to_structured_text(raw.raw_html)
    elif raw.raw_text is not None:
        text = raw.raw_text
    else:
        text = raw.title or ""

    return text[:max_length]


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
    configured_limit = source.config.get("max_content_length", MAX_CONTENT_LENGTH)
    try:
        max_content_length = int(configured_limit)
    except (TypeError, ValueError):
        max_content_length = MAX_CONTENT_LENGTH
    max_content_length = max(1_000, min(max_content_length, 40_000))
    content = clean_content(raw, max_content_length)
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
        enriched = EnrichedJob(
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
            external_url=resolve_application_destination(
                application_instructions=extracted.get("application_instructions"),
                source_url=raw.external_url,
                job_title=extracted["title"],
                candidate_url=raw.application_url,
            ),
            posted_at=_parse_datetime(extracted.get("posted_at")),
            expires_at=_parse_datetime(extracted.get("expires_at")),
            content_hash=content_hash,
            source_slug=source.slug,
            number_of_openings=extracted.get("number_of_openings"),
            application_instructions=extracted.get("application_instructions"),
        )
    except Exception as exc:
        raise EnrichmentError(f"Failed to build EnrichedJob: {exc}") from exc

    # Post-validate: default number_of_openings to 1 if model returned null
    if enriched.number_of_openings is None:
        enriched = enriched.model_copy(update={"number_of_openings": 1})

    return enriched
