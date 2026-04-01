"""Tests for cron schedule evaluation."""

from datetime import UTC, datetime, timedelta

from ijobs_scraper.models import SourceConfig, SourceType
from ijobs_scraper.scheduler import get_due_sources


def _make_source(
    slug: str,
    cron: str | None = "0 */6 * * *",
    is_active: bool = True,
) -> SourceConfig:
    return SourceConfig(
        name=slug,
        slug=slug,
        adapter="test",
        source_type=SourceType.API,
        base_url="https://example.com",
        cron_schedule=cron,
        is_active=is_active,
    )


class TestGetDueSources:
    def test_never_run_always_due(self) -> None:
        source = _make_source("test")
        due = get_due_sources([source], {})
        assert len(due) == 1
        assert due[0].slug == "test"

    def test_no_cron_skipped(self) -> None:
        source = _make_source("test", cron=None)
        due = get_due_sources([source], {})
        assert len(due) == 0

    def test_inactive_skipped(self) -> None:
        source = _make_source("test", is_active=False)
        due = get_due_sources([source], {})
        assert len(due) == 0

    def test_past_due(self) -> None:
        source = _make_source("test", cron="0 */6 * * *")
        # Last run was 7 hours ago, cron is every 6 hours → due
        last_run = datetime.now(UTC) - timedelta(hours=7)
        due = get_due_sources([source], {"test": last_run})
        assert len(due) == 1

    def test_not_yet_due(self) -> None:
        source = _make_source("test", cron="0 */6 * * *")
        # Last run was 1 hour ago, cron is every 6 hours → not due
        last_run = datetime.now(UTC) - timedelta(hours=1)
        due = get_due_sources([source], {"test": last_run})
        assert len(due) == 0

    def test_multiple_sources_mixed(self) -> None:
        s1 = _make_source("due", cron="0 */6 * * *")
        s2 = _make_source("not-due", cron="0 */6 * * *")
        s3 = _make_source("never-run", cron="0 0 * * *")
        s4 = _make_source("no-cron", cron=None)
        s5 = _make_source("inactive", is_active=False)

        last_runs = {
            "due": datetime.now(UTC) - timedelta(hours=7),
            "not-due": datetime.now(UTC) - timedelta(hours=1),
        }

        due = get_due_sources([s1, s2, s3, s4, s5], last_runs)
        slugs = [s.slug for s in due]
        assert "due" in slugs
        assert "never-run" in slugs
        assert "not-due" not in slugs
        assert "no-cron" not in slugs
        assert "inactive" not in slugs

    def test_empty_sources(self) -> None:
        assert get_due_sources([], {}) == []
