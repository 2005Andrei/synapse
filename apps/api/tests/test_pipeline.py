from typing import Any

import pytest
from conftest import FakeRegistry

from agents.graph import build_graph
from agents.nodes.plan import search_name
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from models.types import SourceType
from agents.state import PipelineContext
from core.config import Settings


async def run_pipeline(query: str, scrapers: list[str]) -> tuple[dict, list[tuple[str, dict]]]:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(type: str, data: dict[str, Any]) -> None:
        events.append((str(type), data))

    final = await build_graph().ainvoke(
        {"run_id": "test", "query": query, "scrapers": scrapers},
        context=PipelineContext(emit=emit, settings=Settings(scraper_timeout_seconds=5)),
    )
    return final, events


async def test_pipeline_runs_every_stage_and_reports_progress(fake_scrapers: dict) -> None:
    final, events = await run_pipeline("Acme", list(fake_scrapers))
    types = [type for type, _ in events]

    stages = [data["stage"] for type, data in events if type == "stage.completed"]
    assert stages == ["plan", "scrape", "resolve", "discover", "evaluate"]
    assert types.count("scraper.started") == types.count("scraper.completed") == 4

    statuses = {data["scraper"]: data["status"] for type, data in events if type == "scraper.completed"}
    assert statuses == {"fake_news": "ok", "fake_registry": "ok", "fake_court": "ok", "broken": "error"}

    # One failing scraper does not fail the run.
    assert final["done"] is True and final["iteration"] == 1


async def test_pipeline_builds_one_connected_graph(fake_scrapers: dict) -> None:
    final, events = await run_pipeline("Acme", list(fake_scrapers))
    entities, claims = final["entities"], final["claims"]

    # 2 articles + 1 company + 1 person: the court mentions and the seed merged away.
    by_type = sorted(e["type"] for e in entities.values())
    assert by_type == ["Document", "Document", "Organization", "Person"]

    seed = entities[final["seed_id"]]
    assert seed["attributes"]["cui"] == "123"
    assert "Acme" in seed["aliases"]

    # Both articles point at the seed; the director claim survived the merge.
    mentions = [c for c in claims.values() if c["predicate"] == "Mentions"]
    assert len(mentions) == 2
    assert all(c["reference_ids"] == [final["seed_id"]] for c in mentions)
    (director,) = [c for c in claims.values() if c["predicate"] == "Director_Of"]
    assert director["subject_ids"][0] in entities and director["reference_ids"] == [final["seed_id"]]

    # The frontend was told which nodes disappeared, and never got full article text.
    (resolve_patch,) = [d for t, d in events if t == "graph.patch" and d["origin"] == "resolve"]
    assert len(resolve_patch["removed_entity_ids"]) == 3
    news_patch = next(d for t, d in events if t == "graph.patch" and d["origin"] == "fake_news")
    assert all("content_length" in source for source in news_patch["sources"])


async def test_cui_query_seeds_the_company_directly(fake_scrapers: dict) -> None:
    final, _ = await run_pipeline("RO123", ["fake_registry"])
    seed = final["entities"][final["seed_id"]]
    assert seed["aliases"][0] == "ACME SRL"  # the registry record replaced the placeholder


async def test_cui_query_asks_name_only_sources_for_the_company_name(
    fake_scrapers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: dict[str, str] = {}

    class FakeAnaf(FakeRegistry):
        name = "anaf"
        accepts_cui = True

        def company_name(self, cui: str) -> str:
            return "S.C. ACME S.R.L."

        def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
            asked[self.name] = query
            super().scrape(query, limit, out)

    class Press(BaseScraper):
        name = "press"
        label = "Press"
        category = ScraperCategory.NEWS
        source_type = SourceType.NEWS_ARTICLE

        def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
            asked[self.name] = query

    monkeypatch.setitem(fake_scrapers, "anaf", FakeAnaf)
    monkeypatch.setitem(fake_scrapers, "press", Press)

    final, events = await run_pipeline("RO123", ["anaf", "press"])

    # The registry gets the CUI, the press gets a name it can search for.
    assert asked == {"anaf": "RO123", "press": "ACME"}
    assert final["name_query"] == "ACME"
    assert any("CUI 123 is S.C. ACME S.R.L." in data.get("text", "") for _, data in events)


def test_search_name_drops_legal_forms() -> None:
    assert search_name("S.C. DEDEMAN S.R.L.") == "DEDEMAN"
    assert search_name("OMV PETROM SA") == "OMV PETROM"
    assert search_name("SRL") == "SRL"  # nothing left: keep the original
