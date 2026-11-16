"""Run metadata: one small JSON document per investigation, kept in Redis.

Created by the API, then only the worker that picked up the job writes to it.
"""

import time
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from core.config import get_settings
from core.events import EventBus, EventType
from core.redis import RUNS_INDEX, run_heartbeat_key, run_key


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def finished(self) -> bool:
        return self in (RunStatus.COMPLETED, RunStatus.FAILED)


class Run(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    query: str
    scrapers: list[str]
    status: RunStatus = RunStatus.QUEUED
    created_at: str = Field(default_factory=utcnow)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)


class RunStore:
    def __init__(self, redis: Redis):
        self.redis = redis
        settings = get_settings()
        self.ttl = settings.run_ttl_seconds
        self.heartbeat_ttl = settings.heartbeat_ttl_seconds

    async def save(self, run: Run) -> Run:
        await self.redis.set(run_key(run.id), run.model_dump_json(), ex=self.ttl)
        return run

    async def get(self, run_id: str) -> Run | None:
        raw = await self.redis.get(run_key(run_id))
        return Run.model_validate_json(raw) if raw else None

    async def update(self, run_id: str, **changes: Any) -> Run:
        run = await self.get(run_id)
        if run is None:
            raise KeyError(f"run {run_id} not found (expired?)")
        return await self.save(run.model_copy(update=changes))

    # --- recent runs -------------------------------------------------------
    async def create(self, run: Run) -> Run:
        """Save a new run and list it under recent searches."""
        await self.save(run)
        await self.redis.zadd(RUNS_INDEX, {run.id: time.time()})
        return run

    async def recent(self, limit: int = 20) -> list[Run]:
        """Newest first. Runs whose data has expired drop off the list."""
        ids = await self.redis.zrevrange(RUNS_INDEX, 0, limit - 1)
        if not ids:
            return []
        documents = await self.redis.mget([run_key(run_id) for run_id in ids])
        expired = [run_id for run_id, raw in zip(ids, documents) if raw is None]
        if expired:
            await self.redis.zrem(RUNS_INDEX, *expired)
        return [Run.model_validate_json(raw) for raw in documents if raw]

    async def forget(self, run_id: str) -> None:
        """Take a run off the recent list. Its data stays until it expires, so
        a worker still busy with it is not disturbed."""
        await self.redis.zrem(RUNS_INDEX, run_id)

    # --- liveness ----------------------------------------------------------
    async def beat(self, run_id: str) -> None:
        """Called by the worker every few seconds while it works on the run."""
        await self.redis.set(run_heartbeat_key(run_id), utcnow(), ex=self.heartbeat_ttl)

    async def alive(self, run_id: str) -> bool:
        return bool(await self.redis.exists(run_heartbeat_key(run_id)))

    async def stop_beating(self, run_id: str) -> None:
        await self.redis.delete(run_heartbeat_key(run_id))


ORPHANED = "the worker stopped responding (it crashed or was killed); start the search again"


async def fail_if_orphaned(run_id: str, runs: RunStore, bus: EventBus) -> bool:
    """Fail a run that is marked running but whose worker is gone.

    A worker that dies (OOM, kill -9, power) cannot report its own death, so
    whoever is watching the run does it: the SSE endpoint calls this whenever
    the stream has been quiet. Returns True if the run was failed here.
    """
    run = await runs.get(run_id)
    if run is None or run.status is not RunStatus.RUNNING or await runs.alive(run_id):
        return False

    # Several browsers may be watching the same run; only one reports.
    claimed = await runs.redis.set(
        f"{run_key(run_id)}:reaped", "1", nx=True, ex=runs.ttl
    )
    if not claimed:
        return False

    await runs.update(run_id, status=RunStatus.FAILED, finished_at=utcnow(), error=ORPHANED)
    await bus.publish(run_id, EventType.RUN_FAILED, {"error": ORPHANED})
    return True
