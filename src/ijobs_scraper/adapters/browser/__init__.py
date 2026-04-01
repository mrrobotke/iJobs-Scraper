"""Browser automation adapters using Playwright."""

from ijobs_scraper.adapters.browser.impactpool import ImpactpoolAdapter
from ijobs_scraper.adapters.browser.workday import WorkdayAdapter
from ijobs_scraper.adapters.browser.world_vision import WorldVisionAdapter

__all__ = [
    "ImpactpoolAdapter",
    "WorkdayAdapter",
    "WorldVisionAdapter",
]
