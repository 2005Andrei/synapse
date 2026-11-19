"""The model reads articles; code decides what of its answer enters the graph."""

from typing import Any

from conftest import FakeRegistry
from test_pipeline import run_pipeline

from agents.extraction import Reading, extract, readable_sources
from agents.leads import LeadChoices
from agents.nodes import discover as discover_node
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from core.config import Settings
from models.ids import company_id, mention_id, source_id
from models.types import SourceType

ARTICLE = (
    "Procurorii DNA au anunțat joi că Ion Popescu, directorul Acme SRL, este cercetat "
    "pentru   dare de mită în legătură cu un contract de 12 milioane de lei. "
    "Potrivit Registrului Comerțului, Ion Popescu este administratorul Acme SRL din 2015. "
    "Firma a fost fondată de Maria Ionescu, care a vândut-o în 2014. "
    "Contactat de redacție, Ion Popescu jr., fiul directorului, a refuzat să comenteze. "
    "Compania Beta Construct SA a câștigat licitația alături de Acme."
)

# What a model might answer: mostly right, with the mistakes models make.
ANSWER = {
    "entities": [
        {"name": "Ion Popescu", "type": "Person", "role": "directorul Acme SRL"},
        {"name": "Acme SRL", "type": "Organization", "role": ""},
        {"name": "Maria Ionescu", "type": "Person", "role": "fondatoarea Acme SRL"},
        {"name": "Ion Popescu jr.", "type": "Person", "role": "fiul directorului"},
        {"name": "Beta Construct SA", "type": "Organization", "role": ""},
    ],
    "claims": [
        {  # already known from the registry: the article becomes a second source
            "subject": "Ion Popescu", "predicate": "Director_Of", "object": "Acme SRL",
            "text": "Ion Popescu este administratorul Acme SRL din 2015.",
            "quote": "Ion Popescu este administratorul Acme SRL din 2015", "alleged": False,
        },
        {  # an accusation, quoted with different case, spacing and no diacritics
            "subject": "Ion Popescu", "predicate": "Investigated_In", "object": None,
            "text": "Ion Popescu este cercetat de DNA pentru dare de mită.",
            "quote": "ion popescu, directorul acme srl, este CERCETAT pentru dare de mita", "alleged": True,
        },
        {
            "subject": "Maria Ionescu", "predicate": "Founded", "object": "Acme SRL",
            "text": "Maria Ionescu a fondat Acme SRL.",
            "quote": "Firma a fost fondată de Maria Ionescu", "alleged": False,
        },
        {  # the right fact told backwards, as small models do: a company cannot found a person
            "subject": "Acme SRL", "predicate": "Controls", "object": "Maria Ionescu",
            "text": "Maria Ionescu a controlat Acme SRL până în 2014.",
            "quote": "care a vândut-o în 2014", "alleged": False,
        },
        {  # invented: nothing like this is in the article
            "subject": "Beta Construct SA", "predicate": "Owns", "object": "Acme SRL",
            "text": "Beta Construct deține Acme.",
            "quote": "Beta Construct SA este acționarul majoritar al Acme", "alleged": False,
        },
        {  # object is not an entity anyone listed
            "subject": "Maria Ionescu", "predicate": "Owns", "object": "Gamma Holding",
            "text": "Maria Ionescu deține Gamma Holding.",
            "quote": "Firma a fost fondată de Maria Ionescu", "alleged": False,
        },
    ],
}


class FakeModel:
    """A chat model that reads every article as ANSWER and proposes no leads."""

    def __init__(self, answer: dict | Exception = ANSWER) -> None:
        self.answer, self.prompts = answer, []

    def with_structured_output(self, schema: type) -> "FakeModel":
        self.schema = schema
        return self

    async def ainvoke(self, messages: list) -> object:
        if self.schema is LeadChoices:
            return LeadChoices(leads=[])
        self.prompts.append(messages)
        if isinstance(self.answer, Exception):
            raise self.answer
        return Reading.model_validate(self.answer)


def state_with_article() -> dict[str, Any]:
    """The graph as the scrapers left it: a company, its director, one article."""
    company, director = str(company_id("123")), str(mention_id("reg", "Person", "popescu ion"))
    article, registry = str(source_id("https://news.test/a")), str(source_id("https://registry.test/1"))
    known = "claim-director"
    return {
        "query": "Acme",
        "seed_id": company,
        "entities": {
            company: {"id": company, "type": "Organization", "aliases": ["ACME SRL"], "attributes": {}},
            director: {"id": director, "type": "Person", "aliases": ["POPESCU ION"], "attributes": {}},
        },
        "claims": {},
        "sources": {
            article: {"id": article, "type": SourceType.NEWS_ARTICLE.value, "title": "Anchetă", "url": "https://news.test/a",
                      "publisher": "News", "published_at": "2024-03-12", "content": ARTICLE},
            registry: {"id": registry, "type": SourceType.OFFICIAL_REGISTRY.value, "title": "Acme", "url": "https://registry.test/1",
                       "content": "{}" * 400},
        },
        "_ids": {"company": company, "director": director, "article": article, "registry": registry, "known": known},
    }


async def test_only_grounded_statements_about_known_names_are_kept() -> None:
    state = state_with_article()
    ids = state.pop("_ids")
    model = FakeModel()

    found = await extract(model, state, Settings())

    assert found.read == [ids["article"]] and found.eligible == 1  # the registry record is not prose
    assert found.discarded == 2  # the invented quote, the unlisted object

    # Names the scrapers already had are linked, not duplicated; the only new
    # entity is the one a kept claim is about (not Beta, not the son).
    assert [entity["aliases"] for entity in found.entities.values()] == [["Maria Ionescu"]]
    (maria,) = found.entities
    by_predicate = {claim["predicate"]: claim for claim in found.claims.values()}
    assert set(by_predicate) == {"Director_Of", "Investigated_In", "Founded", "Controls"}
    assert by_predicate["Controls"]["subject_ids"] == [maria]  # turned the right way round

    founded = by_predicate["Founded"]
    assert founded["subject_ids"] == [maria] and founded["reference_ids"] == [ids["company"]]
    assert founded["source_ids"] == [ids["article"]] and founded["quote"] == "Firma a fost fondată de Maria Ionescu"
    assert (founded["claim_status"], founded["confidence"], founded["type"]) == ("Reported", 0.6, "Relationship")

    accused = by_predicate["Investigated_In"]
    assert accused["subject_ids"] == [ids["director"]] and accused["reference_ids"] == []
    assert (accused["claim_status"], accused["confidence"], accused["type"]) == ("Alleged", 0.4, "Fact")

    # The model was told what the investigation is about and given the text.
    (messages,) = model.prompts
    assert "The investigation is about: ACME SRL" in messages[1][1] and ARTICLE in messages[1][1]


async def test_a_claim_the_graph_already_has_gains_the_article_as_a_source() -> None:
    state = state_with_article()
    ids = state.pop("_ids")
    known = "an-id-that-says-nothing-about-its-content"
    state["claims"][known] = {
        "id": known, "predicate": "Director_Of", "claim_text": "director", "claim_status": "Verified",
        "confidence": 0.95, "subject_ids": [ids["director"]], "reference_ids": [ids["company"]],
        "source_ids": [ids["registry"]],
    }

    found = await extract(FakeModel(), state, Settings())

    corroborated = found.claims[known]
    assert corroborated["source_ids"] == [ids["registry"], ids["article"]]
    assert (corroborated["claim_status"], corroborated["confidence"], corroborated["claim_text"]) == ("Verified", 0.95, "director")


async def test_sources_already_read_and_the_per_run_limit() -> None:
    state = state_with_article()
    ids = state.pop("_ids")
    older = [str(source_id(f"https://news.test/older-{n}")) for n in range(3)]
    for n in range(3):
        extra = {**state["sources"][ids["article"]], "id": older[n], "published_at": f"2023-01-0{n + 1}"}
        state["sources"][extra["id"]] = extra

    assert [s["id"] for s in readable_sources(state)] == [ids["article"], *reversed(older)]  # newest first
    found = await extract(FakeModel(), state, Settings(llm_max_sources=2))
    assert found.read == [ids["article"], older[2]] and found.eligible == 4
    # Two articles saying the same thing make one claim with two sources.
    assert all(len(claim["source_ids"]) == 2 for claim in found.claims.values() if claim["reference_ids"])

    state["sources_read"] = found.read
    assert [s["id"] for s in readable_sources(state)] == [older[1], older[0]]


async def test_a_slow_model_stops_at_its_deadline() -> None:
    """Articles not started when a local model's time is up are left unread, not failed."""
    import time

    state = state_with_article()
    state.pop("_ids")

    found = await extract(FakeModel(), state, Settings(), deadline=time.monotonic() - 1)

    assert (found.read, found.failed, found.out_of_time) == ([], 0, 1)
    assert not found.claims


class LongNews(BaseScraper):
    """A press scraper whose one article is long enough to be read."""

    name = "long_news"
    label = "Long News"
    category = ScraperCategory.JOURNALISM
    source_type = SourceType.NEWS_ARTICLE

    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        out.source(url="https://news.test/a", title="Anchetă Acme", content=ARTICLE, published_at="2024-03-12")


async def test_discover_adds_what_the_model_read_to_the_graph(monkeypatch) -> None:
    from connectors import registry

    monkeypatch.setattr(registry, "SCRAPERS", {"fake_registry": FakeRegistry, "long_news": LongNews})
    monkeypatch.setattr(discover_node, "get_chat_model", lambda: FakeModel())

    final, events = await run_pipeline("Acme", ["fake_registry", "long_news"])

    names = {entity["aliases"][0] for entity in final["entities"].values()}
    assert "Maria Ionescu" in names and "Beta Construct SA" not in names
    assert len(final["sources_read"]) == 1

    (patch,) = [data for type, data in events if type == "graph.patch" and data["origin"] == "discover"]
    assert patch["by"] == "llm" and {claim["predicate"] for claim in patch["claims"]} == {"Director_Of", "Investigated_In", "Founded", "Controls"}
    director_of = next(claim for claim in final["claims"].values() if claim["predicate"] == "Director_Of")
    assert len(director_of["source_ids"]) == 2  # registry + article

    texts = [data["text"] for type, data in events if type == "agent.message"]
    assert any(text.startswith("Read 1 of 1 article(s): 1 new entities, 4 claims. 2 statement(s) discarded") for text in texts)


async def test_a_model_that_is_down_costs_the_reading_not_the_run(monkeypatch) -> None:
    from connectors import registry

    monkeypatch.setattr(registry, "SCRAPERS", {"fake_registry": FakeRegistry, "long_news": LongNews})
    monkeypatch.setattr(discover_node, "get_chat_model", lambda: FakeModel(TimeoutError()))

    final, events = await run_pipeline("Acme", ["fake_registry", "long_news"])

    assert final["done"] is True and "sources_read" not in final
    texts = [data["text"] for type, data in events if type == "agent.message"]
    assert any("Model call failed while reading the sources (TimeoutError)" in text for text in texts)
    assert not [data for type, data in events if type == "graph.patch" and data["origin"] == "discover"]


async def test_a_local_model_out_of_time_leaves_the_rest_to_the_rules(monkeypatch) -> None:
    """With its time budget spent, the model is not called: nothing read, heuristic leads, run completes."""
    from agents.llm import Limits
    from connectors import registry

    model = FakeModel()
    monkeypatch.setattr(registry, "SCRAPERS", {"fake_registry": FakeRegistry, "long_news": LongNews})
    monkeypatch.setattr(discover_node, "get_chat_model", lambda: model)
    monkeypatch.setattr(discover_node, "limits_for", lambda name: Limits(1, 4, 16_000, 300, budget=0))

    final, events = await run_pipeline("Acme", ["fake_registry", "long_news"])

    assert final["done"] is True and not final.get("sources_read")
    texts = " ".join(data["text"] for type, data in events if type == "agent.message")
    assert "1 article(s) left unread: the model ran out of time" in texts
    assert "no time left to pick the leads" in texts


async def test_a_model_that_cannot_be_loaded_is_reported(monkeypatch, fake_scrapers: dict) -> None:
    monkeypatch.setattr(
        discover_node, "llm_status",
        lambda: {"model": "anthropic:x", "ready": False, "problem": "ImportError: no langchain_anthropic"},
    )
    _, events = await run_pipeline("Acme", list(fake_scrapers))
    texts = [data["text"] for type, data in events if type == "agent.message"]
    assert any("could not be loaded (ImportError: no langchain_anthropic)" in text for text in texts)
