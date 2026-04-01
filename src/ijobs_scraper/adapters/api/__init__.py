"""API-based adapters for REST and SDK-based job portal sources."""

from ijobs_scraper.adapters.api.careerjet import CareerjetAdapter
from ijobs_scraper.adapters.api.greenhouse import GreenhouseAdapter
from ijobs_scraper.adapters.api.kenya_airways import KenyaAirwaysAdapter
from ijobs_scraper.adapters.api.reliefweb import ReliefWebAdapter
from ijobs_scraper.adapters.api.smartrecruiters import SmartRecruitersAdapter

__all__ = [
    "CareerjetAdapter",
    "GreenhouseAdapter",
    "KenyaAirwaysAdapter",
    "ReliefWebAdapter",
    "SmartRecruitersAdapter",
]
