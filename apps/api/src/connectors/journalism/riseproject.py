from urllib.parse import urlparse

from connectors.common.articles import WordPressScraper


class RiseProjectScraper(WordPressScraper):
    name = "riseproject"
    label = "RISE Project"
    description = "WordPress API search on riseproject.ro, HTML search as fallback"
    base_url = "https://www.riseproject.ro"
    domains = ("www.riseproject.ro", "riseproject.ro")
    wp_endpoints = (
        "posts",
        "pages",
        "investigations",
        "projects",
        "video",
        "workshops",
    )

    unwanted_fragments = (
        "Donează",
        "Susține RISE Project",
        "Sustine RISE Project",
        "Abonează-te",
        "Aboneaza-te",
        "Newsletter",
        "Facebook",
        "Twitter",
        "Instagram",
        "Citește și",
        "Citeste si",
        "Distribuie",
        "Comentarii",
        "Politica de confidențialitate",
        "Politica de confidentialitate",
        "Cookie",
        "GDPR",
    )
    invalid_path_parts = (
        "/tag/",
        "/author/",
        "/category/",
        "/wp-content/",
        "/wp-json/",
        "/contact",
        "/despre-noi",
        "/privacy",
        "/politica",
    )

    def is_article_url(self, url: str) -> bool:
        path = urlparse(url).path
        return self.on_site(url) and not any(
            part in path for part in self.invalid_path_parts
        )
