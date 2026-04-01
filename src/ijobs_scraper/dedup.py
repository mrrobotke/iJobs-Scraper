"""Deduplication logic for job listings.

Three-layer approach:
  1. Source URL uniqueness (same source)
  2. Content fingerprint via SHA-256 (cross-source)
  3. Fuzzy title matching (host app responsibility, not in this package)
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ijobs_scraper.protocols import StorageBackend


def compute_content_hash(title: str, company: str, location: str | None) -> str:
    """Compute SHA-256 hash of normalized ``title|company|location``.

    Args:
        title: Job title.
        company: Company name.
        location: Job location (may be None).

    Returns:
        Hex-encoded SHA-256 digest.
    """
    normalized = "|".join(
        [
            title.lower().strip(),
            company.lower().strip(),
            (location or "").lower().strip(),
        ]
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


def is_known_url(url: str, known_urls: set[str]) -> bool:
    """Layer 1: check if this URL was already scraped for this source."""
    return url in known_urls


async def check_content_duplicate(content_hash: str, storage: StorageBackend) -> bool:
    """Layer 2: check if this content hash exists across all sources."""
    return await storage.check_content_hash(content_hash)
