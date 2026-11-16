import re
from urllib.parse import quote, quote_plus, urlparse

from bs4 import BeautifulSoup

from connectors.common.articles import ArticleScraper


class AdevarulScraper(ArticleScraper):
    name = "adevarul"
    label = "Adevărul"
    description = "Tag page, then site search, on adevarul.ro"
    base_url = "https://adevarul.ro"
    domains = ("adevarul.ro",)
    title_from_parent = True
    # Every adevarul.ro page links to its "Advertorial" section, so the generic
    # "advertorial" marker would flag (and drop) every single article.
    sponsored_markers = (
        "articol sponsorizat",
        "conținut sponsorizat",
        "continut sponsorizat",
    )

    unwanted_fragments = (
        "Citește și",
        "Urmărește-ne pe",
        "Abonează-te",
        "Newsletter",
        "Facebook",
        "Twitter",
        "WhatsApp",
        "Publicitate",
        "Comentarii",
        "Politică de confidențialitate",
        "Cookie",
    )
    invalid_path_parts = (
        "/search",
        "/tag/",
        "/autori/",
        "/video/",
        "/foto/",
        "/politica-confidentialitate",
        "/politica-cookie",
        "/politica-cookies",
        "/termeni-si-conditii",
        "/contact",
        "/redactie",
    )

    def search_urls(self, query: str) -> list[str]:
        return [
            f"{self.base_url}/tag/{quote(query.lower())}",
            f"{self.base_url}/search?q={quote_plus(query)}",
        ]

    def is_article_url(self, url: str) -> bool:
        path = urlparse(url).path
        if not self.on_site(url):
            return False
        if any(part in path for part in self.invalid_path_parts):
            return False
        return bool(re.search(r"-\d+\.html$", path))

    def extract_date(self, soup: BeautifulSoup) -> str | None:
        time_tag = soup.find("time")
        from_time_tag = time_tag and (
            time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        )
        return (
            from_time_tag
            or self.meta_content(soup, "article:published_time")
            or self.meta_content(soup, "og:updated_time")
            or self.labelled_text(soup, "Publicat:")
        )
