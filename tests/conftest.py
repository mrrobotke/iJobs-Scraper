"""Test configuration and shared fixtures."""

from typing import Any

import pytest

from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.models import RawListing


class StubAIProvider:
    """Returns canned enrichment data for testing."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response = response or {
            "title": "Software Engineer",
            "description": "A great role at a great company.",
            "company_name": "Test Corp",
            "company_website": None,
            "location": "Nairobi, Kenya",
            "remote_type": "onsite",
            "employment_type": "full_time",
            "experience_level": "Mid-level",
            "salary_min": None,
            "salary_max": None,
            "currency": "KES",
            "skills": ["Python", "SQL"],
            "benefits": [],
            "category": "technology-engineering",
            "requirements": None,
            "posted_at": None,
            "expires_at": None,
        }

    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append({"system": system_prompt, "user": user_prompt, "schema": json_schema})
        return self._response


class StubStorageBackend:
    """In-memory storage for testing dedup."""

    def __init__(self) -> None:
        self.known_urls: dict[str, set[str]] = {}
        self.content_hashes: set[str] = set()
        self.saved_listings: list[tuple[str, RawListing]] = []
        self.duplicates: list[tuple[str, RawListing, str]] = []

    async def get_known_urls(self, source_slug: str) -> set[str]:
        return self.known_urls.get(source_slug, set())

    async def save_raw_listing(self, source_slug: str, listing: RawListing) -> None:
        self.saved_listings.append((source_slug, listing))

    async def mark_duplicate(
        self, source_slug: str, listing: RawListing, content_hash: str
    ) -> None:
        self.duplicates.append((source_slug, listing, content_hash))

    async def check_content_hash(self, content_hash: str) -> bool:
        return content_hash in self.content_hashes


class FailingAIProvider:
    """AI provider that always raises an error."""

    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        raise RuntimeError("AI service unavailable")


@pytest.fixture
def stub_ai() -> StubAIProvider:
    return StubAIProvider()


@pytest.fixture
def stub_storage() -> StubStorageBackend:
    return StubStorageBackend()


@pytest.fixture(autouse=True)
def _clean_registry() -> None:  # noqa: PT004
    """Clear the adapter registry before each test to avoid pollution."""
    AdapterRegistry._clear()
