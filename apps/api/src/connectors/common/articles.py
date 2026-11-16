"""Base classes for the news / journalism scrapers.

All of these sites work the same way: run a site search, collect article links,
fetch each article, keep the readable text. What differs per site (search URL,
which links are articles, where the date lives, which boilerplate to drop) is
expressed as class attributes and small hook methods.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, ClassVar
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from connectors.common.text import clean_text, normalize_date, query_matches
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from models.ids import document_id
from models.types import EntityType, SourceType

SPONSORED_MARKERS = (
    "advertorial",
    "articol sponsorizat",
    "conținut sponsorizat",
    "continut sponsorizat",
)

_NON_CONTENT_TAGS = ["script", "style", "noscript", "iframe", "form", "svg"]
_MIN_PARAGRAPH_LENGTH = 40


@dataclass
class ArticleLink:
    url: str
    title: str | None = None
    api_item: dict[str, Any] | None = None


@dataclass
class Article:
    url: str
    title: str | None
    date: str | None
    text: str
    sponsored: bool = False


class ArticleScraper(BaseScraper):
    category = ScraperCategory.NEWS
    source_type = SourceType.NEWS_ARTICLE
    headers = {"User-Agent": "Mozilla/5.0"}
    timeout = 10

    # --- per-site configuration -------------------------------------------
    base_url: ClassVar[str]
    domains: ClassVar[tuple[str, ...]]
    # Paragraphs containing any of these are site chrome, not article text.
    unwanted_fragments: ClassVar[tuple[str, ...]] = ()
    sponsored_markers: ClassVar[tuple[str, ...]] = SPONSORED_MARKERS
    skip_sponsored: ClassVar[bool] = True
    # Search-result links with a shorter text are navigation, not headlines.
    min_title_length: ClassVar[int] = 20
    # Some sites wrap the headline around the <a>; then use the parent's text.
    title_from_parent: ClassVar[bool] = False
    paragraph_tags: ClassVar[tuple[str, ...]] = ("p",)
    # Use the whole page text when no paragraph qualifies.
    full_text_fallback: ClassVar[bool] = False
    # Site search is fuzzy: keep only articles that really mention the query.
    require_query_match: ClassVar[bool] = False
    max_workers: ClassVar[int] = 5

    # --- per-site hooks ----------------------------------------------------
    def search_urls(self, query: str) -> list[str]:
        """Result pages to try, in order; the first one with links wins."""
        return [f"{self.base_url}/?s={quote_plus(query)}"]

    def is_article_url(self, url: str) -> bool:
        return self.on_site(url)

    def extract_date(self, soup: BeautifulSoup) -> str | None:
        return self.time_text(soup)

    def content_root(self, soup: BeautifulSoup) -> Tag:
        return soup

    def postprocess_text(self, text: str) -> str:
        return text

    # --- helpers for the hooks ---------------------------------------------
    def on_site(self, url: str) -> bool:
        return urlparse(url).netloc in self.domains

    @staticmethod
    def time_text(soup: BeautifulSoup) -> str | None:
        tag = soup.find("time")
        return tag.get_text(" ", strip=True) if tag else None

    @staticmethod
    def meta_content(soup: BeautifulSoup, prop: str) -> str | None:
        tag = soup.find("meta", {"property": prop})
        return tag.get("content") or None if tag else None

    @staticmethod
    def labelled_text(soup: BeautifulSoup, prefix: str) -> str | None:
        """First text node on the page starting with e.g. "Publicat:"."""
        for string in soup.stripped_strings:
            text = clean_text(string)
            if text.startswith(prefix):
                return text
        return None

    # --- shared flow -------------------------------------------------------
    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        links = self.find_links(query)
        out.metadata["candidates"] = len(links)
        kept = 0

        # Fetch a few at a time, in search order, and stop once we have enough.
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for start in range(0, len(links), self.max_workers):
                chunk = links[start : start + self.max_workers]
                for article in pool.map(self.fetch_article, chunk):
                    if article is None or not article.text:
                        continue
                    if article.sponsored and self.skip_sponsored:
                        continue
                    if self.require_query_match and not query_matches(
                        f"{article.title or ''} {article.text}", query
                    ):
                        continue

                    self.add_article(out, article)
                    kept += 1
                    if kept >= limit:
                        return

    def find_links(self, query: str) -> list[ArticleLink]:
        for page_url in self.search_urls(query):
            html = self.http.try_html(page_url)
            if not html:
                continue
            links = self.parse_links(BeautifulSoup(html, "lxml"))
            if links:
                return links
        return []

    def parse_links(self, soup: BeautifulSoup) -> list[ArticleLink]:
        links: list[ArticleLink] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            url = urljoin(self.base_url, anchor["href"])
            if url in seen or not self.is_article_url(url):
                continue

            title = clean_text(anchor.get_text(" ", strip=True))
            if len(title) < self.min_title_length and self.title_from_parent:
                parent = anchor.find_parent()
                if parent:
                    title = clean_text(parent.get_text(" ", strip=True))
            if len(title) < self.min_title_length:
                continue

            seen.add(url)
            links.append(ArticleLink(url=url, title=title))

        return links

    def fetch_article(self, link: ArticleLink) -> Article | None:
        html = self.http.try_html(link.url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        heading = soup.find("h1")
        title = clean_text(heading.get_text(" ", strip=True)) if heading else None
        date = normalize_date(self.extract_date(soup))

        return Article(
            url=link.url,
            title=title or link.title,
            date=date,
            text=self.extract_text(self.content_root(soup)),
            sponsored=self.is_sponsored(html),
        )

    def extract_text(self, root: Tag) -> str:
        """Readable article text: the long paragraphs, minus site chrome."""
        for tag in root(_NON_CONTENT_TAGS):
            tag.decompose()

        unwanted = [fragment.lower() for fragment in self.unwanted_fragments]
        paragraphs = []

        for paragraph in root.find_all(list(self.paragraph_tags)):
            text = clean_text(paragraph.get_text(" ", strip=True))
            if len(text) < _MIN_PARAGRAPH_LENGTH:
                continue
            lowered = text.lower()
            if any(fragment in lowered for fragment in unwanted):
                continue
            paragraphs.append(text)

        text = clean_text(" ".join(paragraphs))
        if not text and self.full_text_fallback:
            text = clean_text(root.get_text(" ", strip=True))
        return self.postprocess_text(text)

    def is_sponsored(self, html: str) -> bool:
        lowered = html.lower()
        return any(marker in lowered for marker in self.sponsored_markers)

    def add_article(self, out: ScrapeBatch, article: Article) -> None:
        """An article is both evidence (a Source, with its full text) and a
        node in the graph (a Document entity)."""
        title = article.title or article.url
        source = out.source(
            url=article.url,
            title=title,
            content=article.text,
            published_at=article.date,
        )
        out.entity(
            document_id(article.url),
            EntityType.DOCUMENT,
            title,
            description=" · ".join(
                part for part in (self.label, article.date or "") if part
            ),
            document_type="article",
            publisher=self.label,
            published_at=article.date,
            url=article.url,
            sponsored=article.sponsored or None,
            source_id=str(source.id),
        )


class WordPressScraper(ArticleScraper):
    """Sites that expose the WordPress REST API: search through it (it also
    returns the content, saving a page fetch), fall back to the HTML search."""

    category = ScraperCategory.JOURNALISM
    source_type = SourceType.INVESTIGATIVE_ARTICLE
    timeout = 15
    min_title_length = 30
    paragraph_tags = ("p", "li")
    full_text_fallback = True
    require_query_match = True
    skip_sponsored = False

    wp_endpoints: ClassVar[tuple[str, ...]] = ("posts", "pages")

    def content_root(self, soup: BeautifulSoup) -> Tag:
        return (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_="entry-content")
            or soup.find("div", class_="post-content")
            or soup
        )

    def extract_date(self, soup: BeautifulSoup) -> str | None:
        return self.time_text(soup) or self.meta_content(
            soup, "article:published_time"
        )

    def find_links(self, query: str) -> list[ArticleLink]:
        return self.find_links_via_api(query) or super().find_links(query)

    def find_links_via_api(self, query: str) -> list[ArticleLink]:
        api = f"{self.base_url}/wp-json/wp/v2"
        params = {"search": query, "per_page": 20, "page": 1}
        links: list[ArticleLink] = []
        seen: set[str] = set()

        def add(url: str | None, title: str | None, item: dict | None) -> None:
            if url and url not in seen and self.is_article_url(url):
                seen.add(url)
                links.append(ArticleLink(url=url, title=title, api_item=item))

        hits = self.http.try_json(f"{api}/search", params=params)
        if isinstance(hits, list):
            for hit in hits:
                add(hit.get("url"), clean_text(hit.get("title")), None)

        for endpoint in self.wp_endpoints:
            items = self.http.try_json(f"{api}/{endpoint}", params=params)
            if isinstance(items, list):
                for item in items:
                    add(item.get("link") or item.get("url"), _rendered(item, "title"), item)

        return links

    def fetch_article(self, link: ArticleLink) -> Article | None:
        if link.api_item:
            article = self.article_from_api(link)
            if article.text:
                return article
        return super().fetch_article(link)

    def article_from_api(self, link: ArticleLink) -> Article:
        item = link.api_item or {}
        parts = [
            self.extract_text(BeautifulSoup(html, "lxml"))
            for html in (_raw(item, "content"), _raw(item, "excerpt"))
            if html
        ]
        return Article(
            url=link.url,
            title=_rendered(item, "title") or link.title,
            date=normalize_date(item.get("date") or item.get("date_gmt")),
            text=clean_text(" ".join(parts)),
        )


def _raw(item: dict, field: str) -> str | None:
    """WordPress returns text fields as either "..." or {"rendered": "..."}."""
    value = item.get(field)
    if isinstance(value, dict):
        value = value.get("rendered")
    return value if isinstance(value, str) and value else None


def _rendered(item: dict, field: str) -> str | None:
    value = _raw(item, field)
    return clean_text(value) if value else None
