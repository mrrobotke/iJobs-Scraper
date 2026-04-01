"""Custom exception hierarchy for ijobs-scraper."""


class ScraperError(Exception):
    """Base exception for all scraper errors."""


class AdapterError(ScraperError):
    """An adapter encountered an error during scraping."""

    def __init__(self, adapter: str, message: str, *, retryable: bool = True) -> None:
        self.adapter = adapter
        self.retryable = retryable
        super().__init__(f"[{adapter}] {message}")


class EnrichmentError(ScraperError):
    """AI enrichment pipeline failed."""


class DuplicateJobError(ScraperError):
    """Job already exists (detected by dedup)."""

    def __init__(self, content_hash: str, existing_url: str | None = None) -> None:
        self.content_hash = content_hash
        self.existing_url = existing_url
        msg = f"Duplicate job (hash={content_hash[:12]}...)"
        if existing_url:
            msg += f" matches {existing_url}"
        super().__init__(msg)


class RateLimitError(AdapterError):
    """Source returned HTTP 429 or equivalent rate limit signal."""

    def __init__(self, adapter: str, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limited"
        if retry_after is not None:
            msg += f", retry after {retry_after}s"
        super().__init__(adapter, msg, retryable=True)
