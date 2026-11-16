"""Event bus + run store against a real Redis (skipped when none is running)."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from core.events import START, EventBus, EventType, parse_last_event_id
from core.redis import RUNS_INDEX, create_redis, run_events_key, run_heartbeat_key, run_key
from core.runs import ORPHANED, Run, RunStatus, RunStore, fail_if_orphaned


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = create_redis()
    try:
        await client.ping()
    except RedisConnectionError:
        await client.aclose()
        pytest.skip("Redis is not running (`just redis`)")
    yield client
    await client.aclose()


@pytest.fixture
async def run_id(redis: Redis) -> AsyncIterator[str]:
    run_id = f"test-{uuid4().hex}"
    yield run_id
    await redis.delete(
        run_key(run_id), run_events_key(run_id), run_heartbeat_key(run_id), f"{run_key(run_id)}:reaped"
    )


def test_parse_last_event_id_rejects_garbage() -> None:
    assert parse_last_event_id("1700000000000-3") == "1700000000000-3"
    for bad in (None, "", "$", "abc", "1-2; DROP"):
        assert parse_last_event_id(bad) == START


async def test_events_replay_in_order_and_resume(redis: Redis, run_id: str) -> None:
    bus = EventBus(redis)
    first = await bus.publish(run_id, EventType.RUN_STARTED, {"query": "acme"})
    await bus.publish(run_id, EventType.STAGE_STARTED, {"stage": "scrape"})
    await bus.publish(run_id, EventType.RUN_COMPLETED)

    events = await bus.read(run_id)
    assert [e.type for e in events] == ["run.started", "stage.started", "run.completed"]
    assert events[0].data == {"query": "acme"} and events[0].id == first.id

    # A reconnecting client only gets what it has not seen.
    assert [e.type for e in await bus.read(run_id, first.id)] == ["stage.started", "run.completed"]
    assert await redis.ttl(run_events_key(run_id)) > 0


async def test_follow_ends_after_terminal_event(redis: Redis, run_id: str) -> None:
    bus = EventBus(redis)
    await bus.publish(run_id, EventType.RUN_STARTED)
    await bus.publish(run_id, EventType.RUN_FAILED, {"error": "boom"})

    batches = [batch async for batch in bus.follow(run_id, poll_ms=50)]
    assert [e.type for batch in batches for e in batch] == ["run.started", "run.failed"]


async def test_follow_reports_quiet_periods(redis: Redis, run_id: str) -> None:
    async for batch in EventBus(redis).follow(run_id, poll_ms=50):
        assert batch == []  # nothing published yet: the caller decides whether to keep waiting
        break


async def test_run_store_roundtrip(redis: Redis, run_id: str) -> None:
    runs = RunStore(redis)
    await runs.save(Run(id=run_id, query="acme", scrapers=["anaf"]))
    updated = await runs.update(run_id, status=RunStatus.RUNNING)
    assert updated.status is RunStatus.RUNNING
    assert (await runs.get(run_id)) == updated
    assert await runs.get("missing") is None
    with pytest.raises(KeyError):
        await runs.update("missing", status=RunStatus.FAILED)


async def test_run_whose_worker_died_is_failed_once(redis: Redis, run_id: str) -> None:
    runs, bus = RunStore(redis), EventBus(redis)
    await runs.save(Run(id=run_id, query="acme", scrapers=["anaf"], status=RunStatus.QUEUED))

    # Queued (no worker yet) and running-with-heartbeat are both healthy.
    assert not await fail_if_orphaned(run_id, runs, bus)
    await runs.update(run_id, status=RunStatus.RUNNING)
    await runs.beat(run_id)
    assert await runs.alive(run_id) and not await fail_if_orphaned(run_id, runs, bus)

    # The worker dies: its heartbeat expires.
    await runs.stop_beating(run_id)
    assert await fail_if_orphaned(run_id, runs, bus)
    assert not await fail_if_orphaned(run_id, runs, bus)  # a second watcher does not repeat it

    run = await runs.get(run_id)
    assert run is not None and run.status is RunStatus.FAILED and run.error == ORPHANED
    assert [e.type for e in await bus.read(run_id)] == ["run.failed"]


async def test_recent_runs_are_listed_newest_first_until_forgotten(redis: Redis, run_id: str) -> None:
    runs = RunStore(redis)
    older, newer = f"{run_id}-a", f"{run_id}-b"
    try:
        await runs.create(Run(id=older, query="first", scrapers=[]))
        await runs.create(Run(id=newer, query="second", scrapers=[]))
        listed = [run.id for run in await runs.recent(50)]
        assert listed.index(newer) < listed.index(older)

        await runs.forget(newer)
        await redis.delete(run_key(older))  # expired: drops off by itself
        listed = [run.id for run in await runs.recent(50)]
        assert newer not in listed and older not in listed
        assert await redis.zscore(RUNS_INDEX, older) is None
    finally:
        await redis.delete(run_key(older), run_key(newer))
        await redis.zrem(RUNS_INDEX, older, newer)
