import re
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup, Tag

from connectors.common.articles import ArticleScraper
from connectors.scraper import ScraperCategory


class ZFScraper(ArticleScraper):
    name = "zf"
    label = "Ziarul Financiar"
    category = ScraperCategory.JOURNALISM
    description = "Site search on zf.ro"
    base_url = "https://www.zf.ro"
    domains = ("www.zf.ro", "zf.ro")
    title_from_parent = True
    # zf.ro's search page pads its results with unrelated headlines.
    require_query_match = True

    unwanted_fragments = (
        "Tweet",
        "Urmărește",
        "Print",
        "Mail",
        "Setări cookies",
        "Politica de confidențialitate",
        "Politica de cookies",
        "Termeni și condiții",
        "ABONEAZĂ-TE",
        "Abonează-te",
        "Preluarea fără cost a materialelor",
        "ZF Corporate",
        "Ziarul Financiar",
    )
    invalid_path_parts = (
        "/search",
        "/contact",
        "/termeni",
        "/politica",
        "/publicitate",
        "/abonamente",
        "/tags/",
        "/autor/",
    )
    # Promo blocks that zf.ro appends inside the article body.
    cutoff_markers = (
        "Ce arată primele date pe 2025:",
        "Bursă. OMV Petrom",
        "CEC Bank pentru afaceri româneşti:",
    )

    def search_urls(self, query: str) -> list[str]:
        return [f"{self.base_url}/search?q={quote_plus(query)}"]

    def is_article_url(self, url: str) -> bool:
        path = urlparse(url).path
        if not self.on_site(url):
            return False
        if any(part in path for part in self.invalid_path_parts):
            return False
        return bool(re.search(r"-\d+$", path))

    def extract_date(self, soup: BeautifulSoup) -> str | None:
        return self.time_text(soup) or self.meta_content(
            soup, "article:published_time"
        )

    def content_root(self, soup: BeautifulSoup) -> Tag:
        return (
            soup.find("div", class_="text")
            or soup.find("div", class_="article_content")
            or soup.find("div", class_="articleContent")
            or soup.find("article")
            or soup
        )

    def postprocess_text(self, text: str) -> str:
        for marker in self.cutoff_markers:
            if marker in text:
                return text.split(marker)[0].strip()
        return text
