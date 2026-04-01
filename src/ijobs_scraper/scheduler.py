"""Cron schedule evaluation for source scraping.

Determines which sources are due for scraping based on their cron
expressions and last run times. Does NOT enqueue work — that is the
host application's responsibility.
"""

from __future__ import annotations

from datetime import UTC, datetime

from croniter import croniter

from ijobs_scraper.models import SourceConfig


def get_due_sources(
    sources: list[SourceConfig],
    last_runs: dict[str, datetime],
) -> list[SourceConfig]:
    """Return sources whose next cron-scheduled run time has passed.

    Args:
        sources: All configured sources.
        last_runs: Map of source slug to its last run timestamp.

    Returns:
        Sources that are due for scraping now.
    """
    now = datetime.now(UTC)
    due: list[SourceConfig] = []

    for source in sources:
        if not source.cron_schedule or not source.is_active:
            continue

        last = last_runs.get(source.slug)
        if last is None:
            # Never run before — always due
            due.append(source)
            continue

        cron = croniter(source.cron_schedule, last)
        next_run: datetime = cron.get_next(datetime)
        if next_run <= now:
            due.append(source)

    return due
