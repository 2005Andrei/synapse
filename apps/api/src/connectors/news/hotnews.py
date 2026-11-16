from urllib.parse import urlparse

from bs4 import BeautifulSoup

from connectors.common.articles import ArticleScraper


class HotNewsScraper(ArticleScraper):
    name = "hotnews"
    label = "HotNews"
    description = "Site search on hotnews.ro"
    base_url = "https://hotnews.ro"
    domains = ("hotnews.ro", "www.hotnews.ro")

    unwanted_fragments = (
        "HotNews.ro utilizează cookie-uri",
        "Continuarea navigării implică acceptarea",
        "Urmărește HotNews.ro",
        "Citește și:",
        "Accesați Modifică Setările",
        "Politica de confidențialitate",
        "Cookie",
    )
    invalid_path_parts = ("/c/", "/tag/", "/video/")

    def is_article_url(self, url: str) -> bool:
        path = urlparse(url).path
        return self.on_site(url) and not any(
            part in path for part in self.invalid_path_parts
        )

    def extract_date(self, soup: BeautifulSoup) -> str | None:
        return self.time_text(soup) or self.labelled_text(soup, "Publicat:")
