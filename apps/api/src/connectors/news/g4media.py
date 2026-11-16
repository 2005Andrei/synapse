from urllib.parse import urlparse

from bs4 import BeautifulSoup

from connectors.common.articles import SPONSORED_MARKERS, ArticleScraper


class G4MediaScraper(ArticleScraper):
    name = "g4media"
    label = "G4Media"
    description = "Site search on g4media.ro"
    base_url = "https://www.g4media.ro"
    domains = ("www.g4media.ro", "g4media.ro")

    unwanted_fragments = (
        "Funcționăm ca organizație non-profit",
        "Citește și:",
        "Vezi și:",
        "Abonează-te",
        "Newsletter",
        "Distribuie",
        "Facebook",
        "Twitter",
        "WhatsApp",
        "Cookie",
    )
    sponsored_markers = (*SPONSORED_MARKERS, "articol susținut")
    invalid_path_parts = ("/tag/", "/category/", "/video/")

    def is_article_url(self, url: str) -> bool:
        path = urlparse(url).path
        if not self.on_site(url) or not path.endswith(".html"):
            return False
        return not any(part in path for part in self.invalid_path_parts)

    def extract_date(self, soup: BeautifulSoup) -> str | None:
        return self.time_text(soup) or self.meta_content(
            soup, "article:published_time"
        )
