"""Searching an entity of an existing graph further, and doing so unasked for
the person who runs a searched company."""

from typing import Any, ClassVar

import pytest
from conftest import FakeRegistry
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from agents import leads
from agents.graph import build_graph
from agents.resolution import resolve_entities
from agents.state import PipelineContext
from connectors import registry
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from core.config import Settings
from core.events import EventBus
from core.redis import RUNS_INDEX, create_redis, run_key
from core.runs import Run, RunStore
from models.ids import company_id, mention_id
from models.types import EntityType, Predicate, SourceType
from workers.tasks import run_investigation


def person(id: str, name: str, **attributes: Any) -> dict:
    return {"id": id, "type": "Person", "aliases": [name], "description": "", "attributes": attributes}


def test_officers_are_ranked_by_how_much_they_run_the_company() -> None:
    company = {"id": "c", "type": "Organization", "aliases": ["ACME SRL"], "attributes": {}}

    def claim(id: str, subject: str, predicate: Predicate, text: str) -> dict:
        return {"id": id, "predicate": predicate.value, "claim_text": text, "subject_ids": [subject], "reference_ids": ["c"]}

    state = {
        "seed_id": "c",
        "entities": {"c": company, "a": person("a", "A"), "b": person("b", "B"), "l": person("l", "L"), "x": person("x", "X")},
        "claims": {
            "1": claim("1", "l", Predicate.REPRESENTS, "L — lichidator judiciar la ACME SRL"),
            "2": claim("2", "a", Predicate.DIRECTOR_OF, "A — administrator la ACME SRL"),
            "3": claim("3", "b", Predicate.DIRECTOR_OF, "B este Director General la ACME SRL."),
            "4": claim("4", "a", Predicate.REPRESENTS, "A reprezintă ACME SRL (avocat)"),
            "5": {"id": "5", "predicate": "Defendant_In", "claim_text": "X", "subject_ids": ["x"], "reference_ids": ["c"]},
        },
    }
    ranked = leads.with_officers(state, [{"entity_id": "x", "query": "X"}, {"entity_id": "a", "query": "A"}], limit=6)

    assert [(lead["query"], lead.get("role"), lead.get("score")) for lead in ranked] == [
        ("B", "director general", 100), ("A", "administrator", 90), ("L", "lichidator", 10), ("X", None, None),
    ]  # fmt: skip
    assert [lead.get("follow") for lead in ranked] == [True, None, None, None]  # only the top one, unasked
    # A person's search has no officers; a liquidator at the top is not worth an automatic search.
    assert leads.officers({**state, "seed_id": "a"}) == []
    del state["claims"]["2"], state["claims"]["3"], state["claims"]["4"]
    assert "follow" not in leads.with_officers(state, [], 6)[0]


def test_same_name_with_different_birthdays_is_never_merged() -> None:
    entities = {
        "old": person("old", "POPESCU ION", date_of_birth="1950-01-01"),
        "young": person("young", "Ion Popescu", date_of_birth="1990-05-05"),
        "court": person("court", "Popescu Ion"),
        "press": person("press", "Ion POPESCU"),
    }
    resolution = resolve_entities(entities, "young", "Ion Popescu")
    # The two undated mentions are one record, but nobody knows whose.
    assert resolution.merged in ({"press": "court"}, {"court": "press"})

    del entities["old"]  # one birthday known: everything is taken to be that person...
    resolution = resolve_entities(entities, "young", "Ion Popescu")
    assert set(resolution.merged) == {"court", "press"}
    assert set(resolution.merged.values()) == {"young"}  # ...and the searched entity keeps its id


class Companies(BaseScraper):
    """A register that knows which companies Ion Popescu runs."""

    name = "companies"
    label = "Companies"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.OFFICIAL_REGISTRY
    asked: ClassVar[list[str]] = []

    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        self.asked.append(query)
        if "popescu" not in query.lower():
            return
        record = out.source(url="https://registry.test/2", title="Beta", content="{}")
        other = out.entity(company_id("456"), EntityType.ORGANIZATION, "BETA SRL", cui="456")
        man = out.entity(mention_id(self.name, EntityType.PERSON, "ion popescu"), EntityType.PERSON, "Ion Popescu")
        out.claim(man, Predicate.DIRECTOR_OF, "Ion Popescu — administrator la BETA SRL", other, sources=[record])


async def test_searching_an_entity_further_keeps_its_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "SCRAPERS", {"companies": Companies})
    seed = person("11111111-1111-5111-8111-111111111111", "POPESCU ION", public_roles=["Director — ACME SRL"])
    events: list[tuple[str, dict]] = []

    async def emit(type: str, data: dict) -> None:
        events.append((str(type), data))

    final = await build_graph().ainvoke(
        {"run_id": "t", "query": "POPESCU ION", "scrapers": ["companies"], "seed": seed},
        context=PipelineContext(emit=emit, settings=Settings()),
    )

    assert final["seed_id"] == seed["id"]
    merged = final["entities"][seed["id"]]
    # What the register calls "Ion Popescu" is this node; it keeps what was known about it.
    assert merged["aliases"] == ["POPESCU ION", "Ion Popescu"] and merged["attributes"]["public_roles"]
    (runs_beta,) = [claim for claim in final["claims"].values() if claim["predicate"] == "Director_Of"]
    assert runs_beta["subject_ids"] == [seed["id"]]
    assert merged["attributes"]["match_of"] == seed["id"]  # flags say which search they belong to


@pytest.fixture
async def redis() -> Redis:
    """The app's Redis, like tests/test_events.py; only this test's keys are removed."""
    client = create_redis()
    try:
        await client.ping()
    except RedisConnectionError:
        await client.aclose()
        pytest.skip("Redis is not running (`just redis`)")
    before = set(await client.zrange(RUNS_INDEX, 0, -1))
    yield client
    for run_id in set(await client.zrange(RUNS_INDEX, 0, -1)) - before:
        await client.zrem(RUNS_INDEX, run_id)
        await client.delete(*[key async for key in client.scan_iter(f"{run_key(run_id)}*")])
    await client.aclose()


class Queue:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, *args: Any, **kwargs: Any) -> None:
        self.jobs.append(args)


async def test_a_company_search_starts_a_search_of_its_top_officer(redis: Redis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "SCRAPERS", {"fake_registry": FakeRegistry})
    runs, bus, queue = RunStore(redis), EventBus(redis), Queue()
    ctx = {"runs": runs, "bus": bus, "graph": build_graph(), "redis": queue}
    run = await runs.create(Run(query="RO123", scrapers=["fake_registry"], llm="ollama:test"))
    await runs.put_secret(run.id, {"api_key": "sk-user"})

    await run_investigation(ctx, run.id)

    (job,) = queue.jobs
    child = await runs.get(job[1])
    assert (child.query, child.parent_id, child.origin, child.llm) == ("POPESCU ION", run.id, "auto", "ollama:test")
    assert child.seed["aliases"] == ["POPESCU ION"] and "director of RO123" in child.reason
    # The user's key travels to the child, is not in any document or event, and the parent's copy is gone.
    assert await runs.take_secret(child.id) == {"api_key": "sk-user"} and await runs.take_secret(run.id) is None
    events = await bus.read(run.id)
    (spawned,) = [event for event in events if event.type == "run.spawned"]
    assert spawned.data["run"]["id"] == child.id
    assert [event.type for event in events][-1] == "run.completed"  # announced before the stream ends
    dump = str(events) + (await runs.get(run.id)).model_dump_json() + child.model_dump_json()
    assert "sk-user" not in dump

    # The child is one level deep: it does not start searches of its own.
    queue.jobs.clear()
    await run_investigation(ctx, child.id)
    assert queue.jobs == [] and (await runs.get(child.id)).status == "completed"
