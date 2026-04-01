"""Tests for deduplication logic."""

from ijobs_scraper.dedup import check_content_duplicate, compute_content_hash, is_known_url

from .conftest import StubStorageBackend


class TestComputeContentHash:
    def test_deterministic(self) -> None:
        h1 = compute_content_hash("Engineer", "Corp", "Nairobi")
        h2 = compute_content_hash("Engineer", "Corp", "Nairobi")
        assert h1 == h2

    def test_case_insensitive(self) -> None:
        h1 = compute_content_hash("Software Engineer", "Test Corp", "Nairobi")
        h2 = compute_content_hash("software engineer", "test corp", "nairobi")
        assert h1 == h2

    def test_strips_whitespace(self) -> None:
        h1 = compute_content_hash("Engineer", "Corp", "Nairobi")
        h2 = compute_content_hash("  Engineer  ", "  Corp  ", "  Nairobi  ")
        assert h1 == h2

    def test_none_location(self) -> None:
        h = compute_content_hash("Engineer", "Corp", None)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_different_inputs_differ(self) -> None:
        h1 = compute_content_hash("Engineer", "Corp A", "Nairobi")
        h2 = compute_content_hash("Engineer", "Corp B", "Nairobi")
        assert h1 != h2

    def test_location_matters(self) -> None:
        h1 = compute_content_hash("Engineer", "Corp", "Nairobi")
        h2 = compute_content_hash("Engineer", "Corp", "Mombasa")
        assert h1 != h2

    def test_none_vs_empty_location(self) -> None:
        h1 = compute_content_hash("Engineer", "Corp", None)
        h2 = compute_content_hash("Engineer", "Corp", "")
        assert h1 == h2

    def test_returns_hex_string(self) -> None:
        h = compute_content_hash("Title", "Company", "Location")
        assert all(c in "0123456789abcdef" for c in h)


class TestIsKnownUrl:
    def test_known_url(self) -> None:
        known = {"https://example.com/job/1", "https://example.com/job/2"}
        assert is_known_url("https://example.com/job/1", known) is True

    def test_unknown_url(self) -> None:
        known = {"https://example.com/job/1"}
        assert is_known_url("https://example.com/job/99", known) is False

    def test_empty_set(self) -> None:
        assert is_known_url("https://example.com/job/1", set()) is False


class TestCheckContentDuplicate:
    async def test_duplicate_found(self) -> None:
        storage = StubStorageBackend()
        storage.content_hashes.add("abc123")
        assert await check_content_duplicate("abc123", storage) is True

    async def test_not_duplicate(self) -> None:
        storage = StubStorageBackend()
        assert await check_content_duplicate("abc123", storage) is False
