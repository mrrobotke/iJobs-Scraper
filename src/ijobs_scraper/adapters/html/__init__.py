"""HTML scraping adapters using BeautifulSoup."""

from ijobs_scraper.adapters.html.brightermonday import BrighterMondayAdapter
from ijobs_scraper.adapters.html.fuzu import FuzuAdapter
from ijobs_scraper.adapters.html.kcb import KCBAdapter
from ijobs_scraper.adapters.html.mygov import MyGovAdapter
from ijobs_scraper.adapters.html.myjobmag import MyJobMagAdapter
from ijobs_scraper.adapters.html.ncba import NCBAAdapter

__all__ = [
    "BrighterMondayAdapter",
    "FuzuAdapter",
    "KCBAdapter",
    "MyGovAdapter",
    "MyJobMagAdapter",
    "NCBAAdapter",
]
