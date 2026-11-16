from conftest import Broken, FakeNews, FakeRegistry

from connectors.registry import SCRAPERS, list_scrapers
from connectors.scraper import BaseScraper, ScraperCategory, ScrapeStatus
from models.types import EntityType, SourceType


def test_every_registered_scraper_declares_its_identity() -> None:
    assert len(SCRAPERS) == 11
    for name, cls in SCRAPERS.items():
        assert issubclass(cls, BaseScraper)
        assert cls.name == name and name.isidentifier()
        assert cls.label
        assert isinstance(cls.category, ScraperCategory)
        assert isinstance(cls.source_type, SourceType)
    assert [info.name for info in list_scrapers()] == list(SCRAPERS)


def test_every_registered_scraper_can_be_built_and_closed() -> None:
    for cls in SCRAPERS.values():
        with cls():
            pass


def test_registry_scraper_result_uses_the_shared_model() -> None:
    with FakeRegistry() as scraper:
        result = scraper.search("  acme  ")

    assert result.status is ScrapeStatus.OK
    assert (result.scraper, result.query) == ("fake_registry", "acme")
    assert [e.type for e in result.entities] == [EntityType.ORGANIZATION, EntityType.PERSON]
    (claim,) = result.claims
    assert claim.subject_ids == [result.entities[1].id]
    assert claim.reference_ids == [result.entities[0].id]
    assert claim.source_ids == [result.sources[0].id]
    assert claim.confidence == FakeRegistry.confidence


def test_ids_are_stable_across_runs() -> None:
    with FakeRegistry() as first, FakeRegistry() as second:
        a, b = first.search("acme"), second.search("acme")
    assert [e.id for e in a.entities] == [e.id for e in b.entities]
    assert [c.id for c in a.claims] == [c.id for c in b.claims]


def test_search_never_raises() -> None:
    with Broken() as scraper:
        result = scraper.search("acme")
    assert result.status is ScrapeStatus.ERROR
    assert result.error == "RuntimeError: upstream exploded"

    with FakeRegistry() as scraper:
        assert scraper.search("   ").status is ScrapeStatus.ERROR


def test_cancelled_scraper_stops_at_next_request() -> None:
    with FakeNews() as scraper:
        del scraper.http.try_html  # back to the real client
        scraper.cancel()
        result = scraper.search("acme")
    assert (result.status, result.error) == (ScrapeStatus.ERROR, "cancelled")


def test_article_scraper_flow() -> None:
    with FakeNews() as scraper:
        result = scraper.search("acme", limit=5)

    assert result.status is ScrapeStatus.OK
    assert result.metadata == {"candidates": 2}  # the /tag/ link is not an article
    assert len(result.sources) == len(result.entities) == 2

    source, document = result.sources[0], result.entities[0]
    assert source.url == "https://news.test/stiri/first-article-about-acme-1"
    assert source.published_at == "2024-03-12 14:05"
    # Short paragraphs and site chrome are dropped from the text.
    assert source.content == (
        "This paragraph is long enough to count as real article text about Acme SRL."
    )
    assert document.type is EntityType.DOCUMENT
    assert document.attributes["document_type"] == "article"
    assert document.attributes["source_id"] == str(source.id)


def test_article_scraper_respects_limit() -> None:
    with FakeNews() as scraper:
        assert len(scraper.search("acme", limit=1).sources) == 1
