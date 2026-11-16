from urllib.parse import urlparse

from connectors.common.articles import WordPressScraper


class RecorderScraper(WordPressScraper):
    name = "recorder"
    label = "Recorder"
    description = "WordPress API search on recorder.ro, HTML search as fallback"
    base_url = "https://recorder.ro"
    domains = ("recorder.ro", "www.recorder.ro")

    unwanted_fragments = (
        "Susține Recorder",
        "Sustine Recorder",
        "Donează",
        "Doneaza",
        "Abonează-te",
        "Aboneaza-te",
        "Newsletter",
        "Facebook",
        "Twitter",
        "Instagram",
        "YouTube",
        "Citește și",
        "Citeste si",
        "Distribuie",
        "Comentarii",
        "Politica de confidențialitate",
        "Politica de confidentialitate",
        "Cookie",
        "GDPR",
    )
    # Section landing pages, not articles.
    invalid_paths = frozenset(
        {
            "",
            "/english",
            "/investigatii",
            "/reportaj",
            "/documentare",
            "/contact",
            "/despre-noi",
            "/shop-recorder",
            "/contul-meu",
        }
    )
    invalid_path_parts = (
        "/wp-content/",
        "/wp-json/",
        "/tag/",
        "/category/",
        "/author/",
        "/privacy",
        "/politica",
    )

    def is_article_url(self, url: str) -> bool:
        path = urlparse(url).path.rstrip("/")
        if not self.on_site(url) or path in self.invalid_paths:
            return False
        return not any(part in path for part in self.invalid_path_parts)
