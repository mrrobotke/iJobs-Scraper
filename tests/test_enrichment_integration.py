"""Live integration tests for the enrichment pipeline.

These tests hit real external APIs (OpenAI + Careerjet) and are marked
with ``@pytest.mark.live`` so they are excluded from default CI runs.

Run with::

    pytest tests/test_enrichment_integration.py -v -m live
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.adapters.api.careerjet import CareerjetAdapter
from ijobs_scraper.enrichment import EXTRACTION_SCHEMA, enrich
from ijobs_scraper.models import EnrichedJob, RawListing, SourceConfig, SourceType

VALID_CATEGORIES = {
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
}

VALID_REMOTE_TYPES = {"onsite", "hybrid", "remote"}
VALID_EMPLOYMENT_TYPES = {"full_time", "part_time", "contract", "internship"}


def _load_env_key(key: str) -> str | None:
    """Load a key from env var, falling back to .env.local/.env files."""
    value = os.environ.get(key)
    if value:
        return value
    for env_file in (".env.local", ".env"):
        path = Path(__file__).resolve().parents[1] / env_file
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == key:
                    return v.strip()
    return None


class OpenAIProvider:
    """Minimal AIProvider that calls the real OpenAI chat completions API."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        self.api_key = api_key
        self.model = model

    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
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
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if content is None:
            raise ValueError(
                f"OpenAI returned null content "
                f"(finish_reason={data['choices'][0].get('finish_reason')})"
            )
        result: dict[str, Any] = json.loads(content)
        return result


@pytest.fixture
def real_ai_provider() -> OpenAIProvider:
    """Provide an OpenAIProvider using OPEN_AI_KEY from env or .env.local."""
    openai_key = _load_env_key("OPEN_AI_KEY")
    if not openai_key:
        pytest.skip("OPEN_AI_KEY not set (env var or .env.local)")
    return OpenAIProvider(api_key=openai_key)


class TestLiveEnrichmentPipeline:
    """End-to-end tests: Careerjet fetch -> OpenAI enrichment -> EnrichedJob."""

    @pytest.mark.live
    async def test_enrich_careerjet_listing(self) -> None:
        """Fetch a real Careerjet listing and enrich it via OpenAI."""
        openai_key = _load_env_key("OPEN_AI_KEY")
        if not openai_key:
            pytest.skip("OPEN_AI_KEY not set (env var or .env.local)")

        careerjet_key = _load_env_key("CAREERJET_API_KEY")
        if not careerjet_key:
            pytest.skip("CAREERJET_API_KEY not set (env var or .env.local)")

        # Register the adapter (tests clear registry via autouse fixture)
        AdapterRegistry.register("careerjet")(CareerjetAdapter)

        config = SourceConfig(
            name="Careerjet Kenya",
            slug="careerjet-kenya",
            adapter="careerjet",
            source_type=SourceType.API,
            base_url="https://www.careerjet.co.ke",
            config={
                "api_key": careerjet_key,
                "location": "Kenya",
                "user_ip": "127.0.0.1",
            },
        )

        # Fetch 1-2 real listings
        adapter = CareerjetAdapter()
        listings = []
        async for listing in adapter.fetch_listings(config):
            listings.append(listing)
            if len(listings) >= 2:
                break

        assert len(listings) >= 1, "Careerjet returned no listings"
        raw = listings[0]
        assert raw.external_url, "First listing has no external_url"

        # Enrich with real OpenAI
        ai = OpenAIProvider(api_key=openai_key)
        enriched = await enrich(raw, config, ai)

        # Validate the EnrichedJob
        assert isinstance(enriched, EnrichedJob)
        assert enriched.title, "title must not be empty"
        assert enriched.description, "description must not be empty"
        assert enriched.company_name, "company_name must not be empty"
        assert len(enriched.content_hash) == 64, "content_hash must be SHA-256 hex"
        assert enriched.source_slug == "careerjet-kenya"
        assert enriched.external_url == raw.external_url

        # Category must be one of the valid enum values
        assert enriched.category in VALID_CATEGORIES, (
            f"category '{enriched.category}' not in valid set"
        )

        # Enum fields must be valid
        assert enriched.remote_type in VALID_REMOTE_TYPES
        assert enriched.employment_type in VALID_EMPLOYMENT_TYPES

        # Skills must be a list (can be empty for some jobs)
        assert isinstance(enriched.skills, list)

        # Currency must be a non-empty string
        assert enriched.currency

    @pytest.mark.live
    async def test_enrich_synthetic_listing_via_openai(self) -> None:
        """Validate the schema fix: send a synthetic listing through real OpenAI.

        This directly tests that the EXTRACTION_SCHEMA is accepted by OpenAI's
        strict mode (which rejects schemas where required != property keys).
        """
        openai_key = _load_env_key("OPEN_AI_KEY")
        if not openai_key:
            pytest.skip("OPEN_AI_KEY not set (env var or .env.local)")

        source = SourceConfig(
            name="Test Corp",
            slug="test-corp",
            adapter="test",
            source_type=SourceType.API,
            base_url="https://example.com",
        )
        raw = RawListing(
            external_url="https://example.com/jobs/senior-python-dev",
            title="Senior Python Developer",
            raw_json={
                "title": "Senior Python Developer",
                "company": "Test Corp Kenya",
                "description": (
                    "We are looking for a Senior Python Developer to join our team "
                    "in Nairobi, Kenya. Requirements: 5+ years Python experience, "
                    "FastAPI, PostgreSQL, AWS. Salary: KES 200,000 - 350,000/month. "
                    "Benefits: health insurance, remote work 2 days/week. "
                    "Bachelor's degree in Computer Science required."
                ),
                "location": "Nairobi, Kenya",
                "type": "Full-time",
            },
            company_name="Test Corp Kenya",
        )

        ai = OpenAIProvider(api_key=openai_key)
        enriched = await enrich(raw, source, ai)

        # Core fields must be populated
        assert isinstance(enriched, EnrichedJob)
        assert enriched.title, "title must not be empty"
        assert enriched.description, "description must not be empty"
        assert enriched.company_name, "company_name must not be empty"
        assert len(enriched.content_hash) == 64, "content_hash must be SHA-256 hex"
        assert enriched.source_slug == "test-corp"
        assert enriched.external_url == "https://example.com/jobs/senior-python-dev"

        # Enum validations
        assert enriched.category in VALID_CATEGORIES
        assert enriched.remote_type in VALID_REMOTE_TYPES
        assert enriched.employment_type in VALID_EMPLOYMENT_TYPES

        # Structured fields
        assert isinstance(enriched.skills, list)
        assert len(enriched.skills) >= 1, "should extract at least one skill"
        assert enriched.currency

    async def test_extraction_schema_has_all_required_keys(self) -> None:
        """Verify the EXTRACTION_SCHEMA lists all property keys as required.

        OpenAI strict mode rejects schemas where required != property keys.
        """
        schema = EXTRACTION_SCHEMA["schema"]
        properties = set(schema["properties"].keys())
        required = set(schema["required"])
        assert required == properties, (
            f"required/properties mismatch: "
            f"missing from required={properties - required}, "
            f"extra in required={required - properties}"
        )
        # New top-level fields must be present
        assert "number_of_openings" in required
        assert "application_instructions" in required
        # New requirements sub-object fields must be required in the anyOf object branch
        req_branch = schema["properties"]["requirements"]["anyOf"][0]
        req_required = set(req_branch["required"])
        assert "key_responsibilities" in req_required
        assert "minimum_qualifications" in req_required
        assert "preferred_qualifications" in req_required

    @pytest.mark.live
    async def test_enriched_description_is_markdown(self, real_ai_provider: OpenAIProvider) -> None:
        """Verify the rewritten description has Markdown headings and bullets."""
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_text="Software Engineer. Python. 5 years experience required.",
            company_name="Test Corp",
        )
        source = SourceConfig(
            name="Test Corp",
            slug="test",
            adapter="test",
            source_type=SourceType.API,
            base_url="https://example.com",
        )
        job = await enrich(listing, source, real_ai_provider)
        assert "##" in job.description, "Description should have Markdown headings"
        assert "- " in job.description, "Description should have bullet points"
        assert len(job.description.split()) >= 100, "Description should be substantive"

    @pytest.mark.live
    async def test_number_of_openings_defaults_to_1_live(
        self, real_ai_provider: OpenAIProvider
    ) -> None:
        listing = RawListing(
            external_url="https://x.com/j/1",
            raw_text="Software Engineer role at Safaricom.",
            company_name="Safaricom",
        )
        source = SourceConfig(
            name="Safaricom",
            slug="safaricom",
            adapter="test",
            source_type=SourceType.API,
            base_url="https://x.com",
        )
        job = await enrich(listing, source, real_ai_provider)
        assert job.number_of_openings is not None
        assert job.number_of_openings >= 1

    @pytest.mark.live
    async def test_requirements_inferred_when_absent_live(
        self, real_ai_provider: OpenAIProvider
    ) -> None:
        listing = RawListing(
            external_url="https://x.com/j/2",
            raw_text="Senior Data Analyst needed.",
            company_name="KCB Bank",
        )
        source = SourceConfig(
            name="KCB Bank",
            slug="kcb",
            adapter="test",
            source_type=SourceType.API,
            base_url="https://x.com",
        )
        job = await enrich(listing, source, real_ai_provider)
        assert job.requirements is not None
        assert len(job.requirements.key_responsibilities) >= 3
        assert len(job.requirements.minimum_qualifications) >= 3
        assert len(job.skills) >= 3


class TestMyJobMagEnrichmentLive:
    """End-to-end: MyJobMag HTML fetch -> OpenAI enrichment -> EnrichedJob."""

    @pytest.mark.live
    async def test_enrich_myjobmag_listing(self) -> None:
        openai_key = _load_env_key("OPEN_AI_KEY")
        if not openai_key:
            pytest.skip("OPEN_AI_KEY not set (env var or .env.local)")

        from ijobs_scraper.adapters.html.myjobmag import MyJobMagAdapter

        config = SourceConfig(
            name="MyJobMag Kenya",
            slug="myjobmag",
            adapter="myjobmag",
            source_type=SourceType.HTML,
            base_url="https://www.myjobmag.co.ke",
        )
        adapter = MyJobMagAdapter()
        listings: list[RawListing] = []
        try:
            async for listing in adapter.fetch_listings(config):
                listings.append(listing)
                if len(listings) >= 2:
                    break
        finally:
            await adapter.close()

        assert len(listings) >= 1, "MyJobMag returned no listings"
        raw = listings[0]

        ai = OpenAIProvider(api_key=openai_key)
        enriched = await enrich(raw, config, ai)

        assert isinstance(enriched, EnrichedJob)
        assert enriched.title
        assert enriched.description
        assert enriched.company_name
        assert len(enriched.content_hash) == 64
        assert enriched.source_slug == "myjobmag"
        assert enriched.category in VALID_CATEGORIES
        assert enriched.remote_type in VALID_REMOTE_TYPES
        assert enriched.employment_type in VALID_EMPLOYMENT_TYPES
        assert isinstance(enriched.skills, list)
        assert enriched.currency
