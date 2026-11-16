"""Every scraper the app knows about, by name. Add new ones to `_SCRAPERS`."""

from connectors.anaf.anaf import AnafScraper
from connectors.anaf.portal_just import PortalJustScraper
from connectors.ani.ani import AniScraper
from connectors.journalism.recorder import RecorderScraper
from connectors.journalism.riseproject import RiseProjectScraper
from connectors.journalism.zf import ZFScraper
from connectors.news.adevarul import AdevarulScraper
from connectors.news.digi24 import Digi24Scraper
from connectors.news.g4media import G4MediaScraper
from connectors.news.hotnews import HotNewsScraper
from connectors.scraper import BaseScraper, ScraperInfo
from connectors.seap.seap import ElicitatieScraper

_SCRAPERS: tuple[type[BaseScraper], ...] = (
    AnafScraper,
    PortalJustScraper,
    AniScraper,
    ElicitatieScraper,
    HotNewsScraper,
    AdevarulScraper,
    Digi24Scraper,
    G4MediaScraper,
    ZFScraper,
    RecorderScraper,
    RiseProjectScraper,
)

SCRAPERS: dict[str, type[BaseScraper]] = {cls.name: cls for cls in _SCRAPERS}
assert len(SCRAPERS) == len(_SCRAPERS), "two scrapers share a name"


def get_scraper(name: str) -> BaseScraper:
    """A fresh, single-use instance."""
    return SCRAPERS[name]()


def list_scrapers() -> list[ScraperInfo]:
    return [cls.info() for cls in SCRAPERS.values()]
