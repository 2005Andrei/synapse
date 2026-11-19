import pytest

from connectors import registry
from connectors.common.articles import ArticleScraper
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from models.ids import company_id, mention_id
from models.types import EntityType, Predicate, SourceType

SEARCH_PAGE = """
<a href="/stiri/first-article-about-acme-1">Acme wins a very large public contract</a>
<a href="/stiri/second-article-about-acme-2">Acme director questioned by prosecutors</a>
<a href="/tag/acme">tag</a>
"""
ARTICLE_PAGE = """
<h1>{title}</h1><time>12 martie 2024, 14:05</time>
<p>This paragraph is long enough to count as real article text about Acme SRL.</p>
<p>short</p>
<p>Abonează-te la newsletter ca sa primesti cele mai noi stiri in fiecare zi.</p>
"""


class FakeNews(ArticleScraper):
    """An article scraper whose "website" is two canned pages."""

    name = "fake_news"
    label = "Fake News"
    base_url = "https://news.test"
    domains = ("news.test",)
    unwanted_fragments = ("Abonează-te",)
    delay = 0

    def __init__(self) -> None:
        super().__init__()
        self.http.try_html = self.page  # type: ignore[method-assign]

    def is_article_url(self, url: str) -> bool:
        return self.on_site(url) and "/stiri/" in url

    def page(self, url: str, **_: object) -> str:
        if "?s=" in url:
            return SEARCH_PAGE
        return ARTICLE_PAGE.format(title=url.rsplit("/", 1)[-1])


class FakeRegistry(BaseScraper):
    name = "fake_registry"
    label = "Fake Registry"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.OFFICIAL_REGISTRY

    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        record = out.source(url="https://registry.test/1", title="Acme", content="{}")
        company = out.entity(company_id("123"), EntityType.ORGANIZATION, "ACME SRL", cui="123")
        director = out.entity(
            mention_id(self.name, EntityType.PERSON, "popescu ion"),
            EntityType.PERSON,
            "POPESCU ION",
        )
        out.claim(director, Predicate.DIRECTOR_OF, "director", company, sources=[record])


class FakeCourt(BaseScraper):
    """Mentions the same company and person as FakeRegistry, spelled differently."""

    name = "fake_court"
    label = "Fake Court"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.COURT_DOCUMENT

    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        for kind, name in ((EntityType.ORGANIZATION, "S.C. Acme S.R.L."), (EntityType.PERSON, "Ion Popescu")):
            out.entity(mention_id(self.name, kind, name), kind, name)


class Broken(BaseScraper):
    name = "broken"
    label = "Broken"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.UNKNOWN

    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        raise RuntimeError("upstream exploded")


FAKES = {cls.name: cls for cls in (FakeNews, FakeRegistry, FakeCourt, Broken)}


@pytest.fixture(autouse=True)
def no_real_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never call a real (paid) model, whatever LLM_MODEL says locally.
    A test that wants a model patches `get_chat_model` with a fake."""
    from agents.nodes import discover

    monkeypatch.setattr(discover, "get_chat_model", lambda: None)
    monkeypatch.setattr(discover, "llm_status", lambda: {"model": None, "ready": False, "problem": None})
    # ... nor a local one: a run that names its own model gets none either.
    monkeypatch.setattr(
        "workers.tasks.resolve_model",
        lambda choice: (None, {"model": (choice or {}).get("model"), "ready": False, "problem": None}),
    )


@pytest.fixture(autouse=True)
def no_local_register(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests do not depend on whether this machine has built the ONRC index."""
    monkeypatch.setattr("connectors.onrc.index.get_index", lambda: None)
    monkeypatch.setattr("connectors.onrc.onrc.get_index", lambda: None)


@pytest.fixture
def fake_scrapers(monkeypatch: pytest.MonkeyPatch) -> dict[str, type[BaseScraper]]:
    """Swap the real scraper registry for offline fakes."""
    monkeypatch.setattr(registry, "SCRAPERS", FAKES)
    return FAKES
