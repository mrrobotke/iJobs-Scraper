"""Tests for custom exception hierarchy."""

from ijobs_scraper.exceptions import (
    AdapterError,
    DuplicateJobError,
    EnrichmentError,
    RateLimitError,
    ScraperError,
)


class TestScraperError:
    def test_is_base_exception(self) -> None:
        err = ScraperError("something went wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something went wrong"


class TestAdapterError:
    def test_stores_adapter_name(self) -> None:
        err = AdapterError("greenhouse", "connection failed")
        assert err.adapter == "greenhouse"

    def test_retryable_default_true(self) -> None:
        err = AdapterError("greenhouse", "timeout")
        assert err.retryable is True

    def test_retryable_false(self) -> None:
        err = AdapterError("greenhouse", "not found", retryable=False)
        assert err.retryable is False

    def test_message_format(self) -> None:
        err = AdapterError("greenhouse", "connection failed")
        assert str(err) == "[greenhouse] connection failed"

    def test_is_scraper_error(self) -> None:
        err = AdapterError("test", "msg")
        assert isinstance(err, ScraperError)


class TestEnrichmentError:
    def test_is_scraper_error(self) -> None:
        err = EnrichmentError("AI failed")
        assert isinstance(err, ScraperError)

    def test_message(self) -> None:
        err = EnrichmentError("No content")
        assert str(err) == "No content"


class TestDuplicateJobError:
    def test_stores_content_hash(self) -> None:
        err = DuplicateJobError("abc123def456")
        assert err.content_hash == "abc123def456"

    def test_stores_existing_url(self) -> None:
        err = DuplicateJobError("abc123", existing_url="https://example.com/job/1")
        assert err.existing_url == "https://example.com/job/1"

    def test_existing_url_default_none(self) -> None:
        err = DuplicateJobError("abc123")
        assert err.existing_url is None

    def test_message_without_url(self) -> None:
        err = DuplicateJobError("abc123def456")
        assert "abc123def456" in str(err)

    def test_message_with_url(self) -> None:
        err = DuplicateJobError("abc123", existing_url="https://example.com/job/1")
        assert "https://example.com/job/1" in str(err)

    def test_is_scraper_error(self) -> None:
        err = DuplicateJobError("hash")
        assert isinstance(err, ScraperError)


class TestRateLimitError:
    def test_stores_retry_after(self) -> None:
        err = RateLimitError("greenhouse", retry_after=60)
        assert err.retry_after == 60

    def test_retry_after_default_none(self) -> None:
        err = RateLimitError("greenhouse")
        assert err.retry_after is None

    def test_retryable_always_true(self) -> None:
        err = RateLimitError("greenhouse", retry_after=30)
        assert err.retryable is True

    def test_is_adapter_error(self) -> None:
        err = RateLimitError("greenhouse")
        assert isinstance(err, AdapterError)

    def test_is_scraper_error(self) -> None:
        err = RateLimitError("greenhouse")
        assert isinstance(err, ScraperError)

    def test_message_with_retry(self) -> None:
        err = RateLimitError("greenhouse", retry_after=60)
        assert "60s" in str(err)

    def test_message_without_retry(self) -> None:
        err = RateLimitError("greenhouse")
        assert "Rate limited" in str(err)
