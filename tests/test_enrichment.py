"""Tests for the enrichment pipeline."""

import pytest

from ijobs_scraper.enrichment import MAX_CONTENT_LENGTH, clean_content, enrich
from ijobs_scraper.exceptions import EnrichmentError
from ijobs_scraper.models import RawListing, SourceConfig, SourceType

from .conftest import FailingAIProvider, StubAIProvider


def _make_source() -> SourceConfig:
    return SourceConfig(
        name="Test Corp",
        slug="test",
        adapter="test",
        source_type=SourceType.API,
        base_url="https://example.com",
    )


class TestCleanContent:
    def test_json_priority(self) -> None:
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Engineer", "desc": "A role"},
            raw_html="<p>HTML content</p>",
            raw_text="Plain text",
        )
        content = clean_content(listing)
        assert "Engineer" in content
        assert "<p>" not in content

    def test_html_fallback(self) -> None:
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_html="<p>HTML <b>content</b></p>",
            raw_text="Plain text",
        )
        content = clean_content(listing)
        assert "HTML" in content
        assert "content" in content
        assert "<p>" not in content
        assert "<b>" not in content

    def test_text_fallback(self) -> None:
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_text="Plain text content",
        )
        content = clean_content(listing)
        assert content == "Plain text content"

    def test_title_last_resort(self) -> None:
        listing = RawListing(
            external_url="https://example.com/job/1",
            title="Software Engineer",
        )
        content = clean_content(listing)
        assert content == "Software Engineer"

    def test_empty_when_nothing(self) -> None:
        listing = RawListing(external_url="https://example.com/job/1")
        content = clean_content(listing)
        assert content == ""

    def test_truncation(self) -> None:
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_text="x" * (MAX_CONTENT_LENGTH + 5_000),
        )
        content = clean_content(listing)
        assert len(content) == MAX_CONTENT_LENGTH

    def test_html_tag_stripping(self) -> None:
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_html="<p>Hello</p><div>World</div>",
        )
        content = clean_content(listing)
        assert "<p>" not in content
        assert "<div>" not in content
        assert "Hello" in content
        assert "World" in content

    def test_html_block_normalization(self) -> None:
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_html="<li><b>SQL</b> skills</li><p>Lead team</p>",
        )
        content = clean_content(listing)
        assert "<" not in content
        lines = [line for line in content.splitlines() if line.strip()]
        # Inline tags (<b>) should not split a line; block tags separate lines
        assert any("SQL skills" in line for line in lines)
        assert any("Lead team" in line for line in lines)

    def test_html_anchor_destinations_are_preserved(self) -> None:
        listing = RawListing(
            external_url="https://source.example/job/1",
            raw_html=(
                '<h3>Method of Application</h3><p>Apply <a href="https://careers.example/jobs/1">'
                'here</a> or email <a href="mailto:jobs@example.com">HR</a>.</p>'
            ),
        )

        content = clean_content(listing)

        assert "https://careers.example/jobs/1" in content
        assert "mailto:jobs@example.com" in content

    def test_json_with_embedded_html_normalized(self) -> None:
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={
                "title": "Engineer",
                "content": "<p>We need <b>Python</b> skills.</p>",
            },
        )
        content = clean_content(listing)
        assert "<p>" not in content
        assert "<b>" not in content
        assert "Python" in content


class TestEnrich:
    async def test_returns_enriched_job(self) -> None:
        ai = StubAIProvider()
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Software Engineer", "description": "Great role"},
            company_name="Test Corp",
        )
        job = await enrich(listing, _make_source(), ai)

        assert job.title == "Software Engineer"
        assert job.description == "A great role at a great company."
        assert job.company_name == "Test Corp"
        assert job.external_url is None
        assert job.source_slug == "test"
        assert job.content_hash  # not empty

    async def test_calls_ai_provider(self) -> None:
        ai = StubAIProvider()
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Engineer"},
            company_name="Corp",
        )
        await enrich(listing, _make_source(), ai)

        assert len(ai.calls) == 1
        call = ai.calls[0]
        assert "system" in call
        assert "user" in call
        assert "schema" in call
        assert "Corp" in call["user"]

    async def test_handles_requirements(self) -> None:
        response = {
            "title": "Senior Dev",
            "description": "Lead role",
            "company_name": "Corp",
            "company_website": None,
            "location": "Nairobi, Kenya",
            "remote_type": "hybrid",
            "employment_type": "full_time",
            "experience_level": "Senior",
            "salary_min": 100000,
            "salary_max": 200000,
            "currency": "KES",
            "skills": ["Python"],
            "benefits": ["Health insurance"],
            "category": "technology-engineering",
            "requirements": {
                "education_level": "Bachelor's",
                "min_years_experience": 5,
                "certifications": ["AWS"],
                "languages": ["English"],
            },
            "posted_at": None,
            "expires_at": None,
        }
        ai = StubAIProvider(response=response)
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Senior Dev"},
        )
        job = await enrich(listing, _make_source(), ai)

        assert job.requirements is not None
        assert job.requirements.education_level == "Bachelor's"
        assert job.requirements.min_years_experience == 5
        assert job.salary_min == 100000

    async def test_raises_on_empty_content(self) -> None:
        ai = StubAIProvider()
        listing = RawListing(external_url="https://example.com/job/1")
        with pytest.raises(EnrichmentError, match="No content"):
            await enrich(listing, _make_source(), ai)

    async def test_raises_on_ai_failure(self) -> None:
        ai = FailingAIProvider()
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Engineer"},
        )
        with pytest.raises(EnrichmentError, match="AI extraction failed"):
            await enrich(listing, _make_source(), ai)

    async def test_content_hash_computed(self) -> None:
        ai = StubAIProvider()
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Engineer"},
        )
        job = await enrich(listing, _make_source(), ai)
        assert len(job.content_hash) == 64  # SHA-256 hex

    async def test_datetime_parsing(self) -> None:
        response = {
            "title": "Dev",
            "description": "Role",
            "company_name": "Corp",
            "company_website": None,
            "location": None,
            "remote_type": "onsite",
            "employment_type": "full_time",
            "experience_level": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "KES",
            "skills": [],
            "benefits": [],
            "category": "technology-engineering",
            "requirements": None,
            "posted_at": "2026-04-01T10:00:00",
            "expires_at": "invalid-date",
        }
        ai = StubAIProvider(response=response)
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Dev"},
        )
        job = await enrich(listing, _make_source(), ai)
        assert job.posted_at is not None
        assert job.expires_at is None  # invalid date → None

    async def test_number_of_openings_extracted(self) -> None:
        response = {
            "title": "Dev",
            "description": "Role",
            "company_name": "Corp",
            "company_website": None,
            "location": None,
            "remote_type": "onsite",
            "employment_type": "full_time",
            "experience_level": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "KES",
            "skills": [],
            "benefits": [],
            "category": "technology-engineering",
            "requirements": None,
            "posted_at": None,
            "expires_at": None,
            "number_of_openings": 2,
            "application_instructions": None,
        }
        ai = StubAIProvider(response=response)
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Dev"},
        )
        job = await enrich(listing, _make_source(), ai)
        assert job.number_of_openings == 2

    async def test_number_of_openings_defaults_to_1(self) -> None:
        response = {
            "title": "Dev",
            "description": "Role",
            "company_name": "Corp",
            "company_website": None,
            "location": None,
            "remote_type": "onsite",
            "employment_type": "full_time",
            "experience_level": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "KES",
            "skills": [],
            "benefits": [],
            "category": "technology-engineering",
            "requirements": None,
            "posted_at": None,
            "expires_at": None,
            "number_of_openings": None,
            "application_instructions": None,
        }
        ai = StubAIProvider(response=response)
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Dev"},
        )
        job = await enrich(listing, _make_source(), ai)
        assert job.number_of_openings == 1

    async def test_requirements_new_fields_populated(self) -> None:
        response = {
            "title": "Dev",
            "description": "Role",
            "company_name": "Corp",
            "company_website": None,
            "location": None,
            "remote_type": "onsite",
            "employment_type": "full_time",
            "experience_level": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "KES",
            "skills": [],
            "benefits": [],
            "category": "technology-engineering",
            "requirements": {
                "education_level": None,
                "min_years_experience": None,
                "certifications": [],
                "languages": [],
                "key_responsibilities": ["Foo"],
                "minimum_qualifications": ["Bar"],
                "preferred_qualifications": ["Baz"],
            },
            "posted_at": None,
            "expires_at": None,
            "number_of_openings": 1,
            "application_instructions": None,
        }
        ai = StubAIProvider(response=response)
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Dev"},
        )
        job = await enrich(listing, _make_source(), ai)
        assert job.requirements is not None
        assert job.requirements.key_responsibilities == ["Foo"]
        assert job.requirements.minimum_qualifications == ["Bar"]
        assert job.requirements.preferred_qualifications == ["Baz"]

    async def test_application_instructions_stored(self) -> None:
        response = {
            "title": "Dev",
            "description": "Role",
            "company_name": "Corp",
            "company_website": None,
            "location": None,
            "remote_type": "onsite",
            "employment_type": "full_time",
            "experience_level": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "KES",
            "skills": [],
            "benefits": [],
            "category": "technology-engineering",
            "requirements": None,
            "posted_at": None,
            "expires_at": None,
            "number_of_openings": 1,
            "application_instructions": "Email CV to hr@corp.com",
        }
        ai = StubAIProvider(response=response)
        listing = RawListing(
            external_url="https://example.com/job/1",
            raw_json={"title": "Dev"},
        )
        job = await enrich(listing, _make_source(), ai)
        assert job.application_instructions == "Email CV to hr@corp.com"
        assert job.external_url == "mailto:hr@corp.com?subject=Dev"

    async def test_adapter_resolved_application_url_takes_precedence(self) -> None:
        response = {
            "title": "Procurement Coordinator",
            "description": "Role",
            "company_name": "SevenTwenty Holdings",
            "company_website": None,
            "location": "Nairobi, Kenya",
            "remote_type": "onsite",
            "employment_type": "full_time",
            "experience_level": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "KES",
            "skills": [],
            "benefits": [],
            "category": "supply-chain-logistics",
            "requirements": None,
            "posted_at": None,
            "expires_at": None,
            "number_of_openings": 1,
            "application_instructions": "Go to seventwentyholdings.co.ke to apply",
        }
        ai = StubAIProvider(response=response)
        listing = RawListing(
            external_url="https://www.myjobmag.co.ke/job/procurement-coordinator",
            application_url=("https://seventwentyholdings.co.ke/jobs/procurement-coordinator"),
            raw_text="Procurement Coordinator role",
        )

        job = await enrich(listing, _make_source(), ai)

        assert job.external_url == (
            "https://seventwentyholdings.co.ke/jobs/procurement-coordinator"
        )
