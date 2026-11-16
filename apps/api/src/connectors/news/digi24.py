from urllib.parse import quote_plus, urlparse

from connectors.common.articles import SPONSORED_MARKERS, ArticleScraper


class Digi24Scraper(ArticleScraper):
    name = "digi24"
    label = "Digi24"
    description = "Site search on digi24.ro"
    base_url = "https://www.digi24.ro"
    domains = ("www.digi24.ro", "digi24.ro")
    max_workers = 20

    unwanted_fragments = (
        "Urmărește știrile Digi24.ro",
        "Abonează-te",
        "Newsletter",
        "Facebook",
        "Twitter",
        "WhatsApp",
        "Cookie",
    )
    sponsored_markers = (*SPONSORED_MARKERS, "articol susținut")

    def search_urls(self, query: str) -> list[str]:
        return [f"{self.base_url}/cautare?q={quote_plus(query)}"]

    def is_article_url(self, url: str) -> bool:
        return self.on_site(url) and "/stiri/" in urlparse(url).path
