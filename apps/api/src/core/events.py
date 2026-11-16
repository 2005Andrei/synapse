"""Run events: what the worker tells the frontend while an investigation runs.

Every run has its own Redis Stream. The worker appends events to it; the API
reads them back and forwards them over SSE. A stream (not pub/sub) is used so
that nothing is lost when the browser connects late or reconnects: the SSE
event id IS the stream entry id, so `Last-Event-ID` resumes exactly where the
client left off.
"""

import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from core.config import get_settings
from core.redis import run_events_key

_STREAM_ID = re.compile(r"^\d+-\d+$")
START = "0-0"


class EventType(StrEnum):
    RUN_QUEUED = "run.queued"
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"

    STAGE_STARTED = "stage.started"
    STAGE_COMPLETED = "stage.completed"

    SCRAPER_STARTED = "scraper.started"
    SCRAPER_COMPLETED = "scraper.completed"

    # Upserts/removals for the frontend graph: entities, claims, sources.
    GRAPH_PATCH = "graph.patch"

    AGENT_SKIPPED = "agent.skipped"
    AGENT_MESSAGE = "agent.message"
    # Follow-up searches proposed by the discovery stage; the user decides
    # which ones to launch.
    AGENT_LEADS = "agent.leads"


TERMINAL = frozenset({EventType.RUN_COMPLETED, EventType.RUN_FAILED})


class Event(BaseModel):
    id: str | None = None
    type: str
    run_id: str
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    data: dict[str, Any] = Field(default_factory=dict)

    @property
    def terminal(self) -> bool:
        return self.type in TERMINAL


def parse_last_event_id(value: str | None) -> str:
    """Turn a client-supplied `Last-Event-ID` into a safe stream cursor."""
    return value if value and _STREAM_ID.match(value) else START


class EventBus:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.settings = get_settings()

    async def publish(
        self, run_id: str, type: str, data: dict[str, Any] | None = None
    ) -> Event:
        event = Event(type=str(type), run_id=run_id, data=data or {})
        key = run_events_key(run_id)
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.xadd(
                key,
                {"type": event.type, "ts": event.ts, "data": json.dumps(event.data)},
                maxlen=self.settings.run_events_maxlen,
                approximate=True,
            )
            pipe.expire(key, self.settings.run_ttl_seconds)
            event.id, _ = await pipe.execute()
        return event

    async def read(
        self, run_id: str, after: str = START, *, block_ms: int | None = None
    ) -> list[Event]:
        """Events newer than `after`; waits up to `block_ms` if there are none yet."""
        reply = await self.redis.xread(
            {run_events_key(run_id): after}, count=200, block=block_ms
        )
        return [
            Event(
                id=entry_id,
                type=fields["type"],
                run_id=run_id,
                ts=fields["ts"],
                data=json.loads(fields["data"]),
            )
            for _, entries in reply
            for entry_id, fields in entries
        ]

    async def follow(
        self, run_id: str, after: str = START, *, poll_ms: int = 5000
    ) -> AsyncIterator[list[Event]]:
        """Yield batches of events as they arrive; an empty batch means "still quiet".

        Stops by itself after a terminal event. Callers stop on quiet batches
        when they know the run is already over.
        """
        cursor = after
        while True:
            events = await self.read(run_id, cursor, block_ms=poll_ms)
            yield events
            if events:
                cursor = events[-1].id or cursor
                if any(event.terminal for event in events):
                    return
