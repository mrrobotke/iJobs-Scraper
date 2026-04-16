"""Tests for Pydantic data models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ijobs_scraper.models import (
    EnrichedJob,
    JobRequirements,
    RawListing,
    ScrapeResult,
    SourceConfig,
    SourceType,
)


class TestSourceType:
    def test_values(self) -> None:
        assert SourceType.API == "api"
        assert SourceType.HTML == "html"
        assert SourceType.BROWSER == "browser"
        assert SourceType.RSS == "rss"

    def test_str_enum(self) -> None:
        assert str(SourceType.API) == "api"
        assert f"type={SourceType.HTML}" == "type=html"


class TestSourceConfig:
    def test_required_fields(self) -> None:
        cfg = SourceConfig(
            name="Test",
            slug="test",
            adapter="test_adapter",
            source_type=SourceType.API,
            base_url="https://example.com",
        )
        assert cfg.name == "Test"
        assert cfg.slug == "test"
        assert cfg.adapter == "test_adapter"
        assert cfg.source_type == SourceType.API
        assert cfg.base_url == "https://example.com"

    def test_defaults(self) -> None:
        cfg = SourceConfig(
            name="Test",
            slug="test",
            adapter="test_adapter",
            source_type=SourceType.HTML,
            base_url="https://example.com",
        )
        assert cfg.cron_schedule is None
        assert cfg.is_active is True
        assert cfg.config == {}

    def test_with_optional_fields(self) -> None:
        cfg = SourceConfig(
            name="Test",
            slug="test",
            adapter="greenhouse",
            source_type=SourceType.API,
            base_url="https://example.com",
            cron_schedule="0 */6 * * *",
            is_active=False,
            config={"board_token": "abc123"},
        )
        assert cfg.cron_schedule == "0 */6 * * *"
        assert cfg.is_active is False
        assert cfg.config["board_token"] == "abc123"

    def test_missing_required_raises(self) -> None:
        with pytest.raises(ValidationError):
            SourceConfig(name="Test")  # type: ignore[call-arg]

    def test_serialization_roundtrip(self) -> None:
        cfg = SourceConfig(
            name="Test",
            slug="test",
            adapter="test_adapter",
            source_type=SourceType.API,
            base_url="https://example.com",
            config={"key": "value"},
        )
        data = cfg.model_dump()
        restored = SourceConfig(**data)
        assert restored == cfg


class TestRawListing:
    def test_required_external_url(self) -> None:
        listing = RawListing(external_url="https://example.com/job/1")
        assert listing.external_url == "https://example.com/job/1"

    def test_defaults(self) -> None:
        listing = RawListing(external_url="https://example.com/job/1")
        assert listing.external_id is None
        assert listing.title is None
        assert listing.raw_html is None
        assert listing.raw_json is None
        assert listing.raw_text is None
        assert listing.company_name is None
        assert listing.fetched_at is not None

    def test_fetched_at_auto_set(self) -> None:
        before = datetime.now(UTC)
        listing = RawListing(external_url="https://example.com/job/1")
        after = datetime.now(UTC)
        assert before <= listing.fetched_at <= after

    def test_all_fields(self) -> None:
        listing = RawListing(
            external_id="123",
            external_url="https://example.com/job/123",
            title="Software Engineer",
            raw_json={"id": 123, "title": "Software Engineer"},
            company_name="Test Corp",
        )
        assert listing.external_id == "123"
        assert listing.title == "Software Engineer"
        assert listing.raw_json == {"id": 123, "title": "Software Engineer"}
        assert listing.company_name == "Test Corp"

    def test_missing_url_raises(self) -> None:
        with pytest.raises(ValidationError):
            RawListing()  # type: ignore[call-arg]


class TestJobRequirements:
    def test_defaults(self) -> None:
        req = JobRequirements()
        assert req.education_level is None
        assert req.min_years_experience is None
        assert req.certifications == []
        assert req.languages == []

    def test_with_values(self) -> None:
        req = JobRequirements(
            education_level="Bachelor's",
            min_years_experience=3,
            certifications=["PMP"],
            languages=["English", "Swahili"],
        )
        assert req.education_level == "Bachelor's"
        assert req.min_years_experience == 3
        assert req.certifications == ["PMP"]
        assert req.languages == ["English", "Swahili"]

    def test_job_requirements_new_fields_default_empty(self) -> None:
        req = JobRequirements()
        assert req.key_responsibilities == []
        assert req.minimum_qualifications == []
        assert req.preferred_qualifications == []


class TestEnrichedJob:
    def test_required_fields(self) -> None:
        job = EnrichedJob(
            title="Software Engineer",
            description="Great role",
            company_name="Test Corp",
            external_url="https://example.com/job/1",
            content_hash="abc123",
            source_slug="test",
        )
        assert job.title == "Software Engineer"
        assert job.content_hash == "abc123"

    def test_defaults(self) -> None:
        job = EnrichedJob(
            title="Software Engineer",
            description="Great role",
            company_name="Test Corp",
            external_url="https://example.com/job/1",
            content_hash="abc123",
            source_slug="test",
        )
        assert job.remote_type == "onsite"
        assert job.employment_type == "full_time"
        assert job.currency == "KES"
        assert job.skills == []
        assert job.benefits == []
        assert job.company_website is None
        assert job.location is None
        assert job.requirements is None
        assert job.posted_at is None
        assert job.expires_at is None

    def test_with_requirements(self) -> None:
        req = JobRequirements(education_level="Master's", min_years_experience=5)
        job = EnrichedJob(
            title="Data Scientist",
            description="ML role",
            company_name="AI Corp",
            external_url="https://example.com/job/2",
            content_hash="def456",
            source_slug="test",
            requirements=req,
        )
        assert job.requirements is not None
        assert job.requirements.education_level == "Master's"
        assert job.requirements.min_years_experience == 5

    def test_literal_validation(self) -> None:
        with pytest.raises(ValidationError):
            EnrichedJob(
                title="Job",
                description="Desc",
                company_name="Corp",
                external_url="https://example.com/job/1",
                content_hash="hash",
                source_slug="test",
                remote_type="invalid",  # type: ignore[arg-type]
            )

    def test_enriched_job_new_fields_default_none(self) -> None:
        job = EnrichedJob(
            title="t",
            description="d",
            company_name="c",
            external_url="https://x.com",
            content_hash="abc" * 21,
            source_slug="s",
        )
        assert job.number_of_openings is None
        assert job.application_instructions is None


class TestScrapeResult:
    def test_required_fields(self) -> None:
        now = datetime.now(UTC)
        result = ScrapeResult(source_slug="test", status="completed", started_at=now)
        assert result.source_slug == "test"
        assert result.status == "completed"
        assert result.started_at == now

    def test_defaults(self) -> None:
        result = ScrapeResult(
            source_slug="test",
            status="completed",
            started_at=datetime.now(UTC),
        )
        assert result.completed_at is None
        assert result.jobs_found == 0
        assert result.jobs_created == 0
        assert result.jobs_duplicated == 0
        assert result.jobs_failed == 0
        assert result.errors == []

    def test_status_literal(self) -> None:
        with pytest.raises(ValidationError):
            ScrapeResult(
                source_slug="test",
                status="invalid",  # type: ignore[arg-type]
                started_at=datetime.now(UTC),
            )

    def test_serialization(self) -> None:
        now = datetime.now(UTC)
        result = ScrapeResult(
            source_slug="test",
            status="partial",
            started_at=now,
            jobs_found=10,
            jobs_created=7,
            jobs_duplicated=2,
            jobs_failed=1,
            errors=["https://example.com/job/1: timeout"],
        )
        data = result.model_dump()
        assert data["jobs_found"] == 10
        assert data["errors"] == ["https://example.com/job/1: timeout"]
