from collections.abc import AsyncIterable
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from api.deps import Bus, CurrentRun, Queue, Runs
from connectors.registry import SCRAPERS, list_scrapers
from connectors.scraper import ScraperInfo
from core.config import get_settings
from core.events import EventType, parse_last_event_id
from core.runs import Run, fail_if_orphaned
from workers.tasks import RUN_INVESTIGATION

router = APIRouter(prefix="/api")

# How long the SSE loop waits for new events before checking on the run.
sse_poll_ms = 5000


class SeedEntity(BaseModel):
    """An entity of an existing graph, as the browser holds it."""

    id: str
    type: str
    aliases: list[str] = Field(min_length=1)
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class LlmChoice(BaseModel):
    """The model a user wants this search to use, with their own key."""

    model: str = Field(min_length=3, max_length=120, description='langchain "provider:model"')
    api_key: str | None = Field(default=None, max_length=400)
    base_url: str | None = Field(default=None, max_length=300)


class InvestigationRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    scrapers: list[str] | None = Field(
        default=None, description="Scraper names to run; omit to run all of them."
    )
    parent_id: str | None = Field(
        default=None, description="Search further inside this run's graph instead of starting a new one."
    )
    seed: SeedEntity | None = Field(default=None, description="With parent_id: the entity to search further.")
    llm: LlmChoice | None = None


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    await request.app.state.redis.ping()
    return {"status": "ok"}


@router.get("/scrapers")
async def scrapers() -> list[ScraperInfo]:
    return list_scrapers()


@router.post("/investigations", status_code=202)
async def create_investigation(
    body: InvestigationRequest, runs: Runs, bus: Bus, queue: Queue
) -> Run:
    """Queue an investigation. Returns immediately; follow it on `/events`."""
    query = body.query.strip()
    if len(query) < 2:
        raise HTTPException(422, "query is too short")

    names = body.scrapers if body.scrapers is not None else list(SCRAPERS)
    unknown = sorted(set(names) - set(SCRAPERS))
    if unknown:
        raise HTTPException(422, f"unknown scrapers: {', '.join(unknown)}")

    settings = get_settings()
    if body.parent_id and await runs.get(body.parent_id) is None:
        raise HTTPException(404, "the search to extend was not found (expired?)")
    if body.llm and not settings.allow_user_llm:
        raise HTTPException(403, "this server does not accept a model chosen by the user")

    run = Run(
        query=query,
        scrapers=names,
        parent_id=body.parent_id,
        seed=body.seed.model_dump() if body.seed and body.parent_id else None,
        llm=body.llm.model if body.llm else None,
    )
    if body.llm:
        secret = {"api_key": body.llm.api_key or ""}
        if body.llm.base_url and settings.allow_user_llm_base_url:
            secret["base_url"] = body.llm.base_url
        await runs.put_secret(run.id, secret)
    await runs.create(run)
    await bus.publish(run.id, EventType.RUN_QUEUED, {"query": query, "scrapers": names})
    await queue.enqueue_job(RUN_INVESTIGATION, run.id, _job_id=run.id)
    return run


@router.get("/investigations")
async def list_investigations(
    runs: Runs, limit: Annotated[int, Query(ge=1, le=50)] = 10
) -> list[Run]:
    """Recent investigations, newest first: lets the dashboard pick up where
    it left off after a reload. (Shared by everyone until there are accounts.)"""
    return await runs.recent(limit)


@router.get("/investigations/{run_id}")
async def get_investigation(run: CurrentRun) -> Run:
    return run


@router.delete("/investigations/{run_id}", status_code=204)
async def forget_investigation(run_id: str, runs: Runs) -> None:
    """Remove a run from the recent list (the dashboard's "dismiss")."""
    await runs.forget(run_id)


@router.get("/investigations/{run_id}/events", response_class=EventSourceResponse)
async def investigation_events(
    run: CurrentRun,
    runs: Runs,
    bus: Bus,
    last_event_id: Annotated[str | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    """Server-sent events for one run.

    Replays everything from the start (or from `Last-Event-ID` on reconnect),
    then stays open until the run finishes. FastAPI adds keep-alive pings.
    """
    cursor = parse_last_event_id(last_event_id)

    async for events in bus.follow(run.id, cursor, poll_ms=sse_poll_ms):
        for event in events:
            yield ServerSentEvent(id=event.id, raw_data=event.model_dump_json())

        if not events:
            # Nothing new. If the run is already over (client reconnected after
            # the end, or the run expired), there never will be: close.
            current = await runs.get(run.id)
            if current is None or current.status.finished:
                return
            # Still "running" but nobody is working on it: say so. The failure
            # event lands on the stream and closes it on the next read.
            await fail_if_orphaned(run.id, runs, bus)
