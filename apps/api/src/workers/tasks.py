"""Background jobs. Each function here runs inside an arq worker process."""

import asyncio
import logging
from typing import Any

from agents.state import PipelineContext
from core.config import get_settings
from core.events import EventBus, EventType
from core.runs import RunStatus, RunStore, utcnow

log = logging.getLogger(__name__)

RUN_INVESTIGATION = "run_investigation"


async def run_investigation(ctx: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Run one investigation end to end, reporting progress as run events."""
    runs: RunStore = ctx["runs"]
    bus: EventBus = ctx["bus"]

    run = await runs.get(run_id)
    if run is None:
        log.warning("run %s vanished before it started", run_id)
        return {}

    async def emit(type: str, data: dict[str, Any]) -> None:
        await bus.publish(run_id, type, data)

    async def fail(error: str) -> None:
        await runs.update(
            run_id, status=RunStatus.FAILED, finished_at=utcnow(), error=error
        )
        await emit(EventType.RUN_FAILED, {"error": error})

    await runs.beat(run_id)
    await runs.update(run_id, status=RunStatus.RUNNING, started_at=utcnow())
    await emit(EventType.RUN_STARTED, {"query": run.query, "scrapers": run.scrapers})
    heartbeat = asyncio.create_task(_heartbeat(runs, run_id))

    try:
        final = await ctx["graph"].ainvoke(
            {"run_id": run_id, "query": run.query, "scrapers": run.scrapers},
            context=PipelineContext(emit=emit, settings=get_settings()),
        )
    except asyncio.CancelledError:
        # Job timeout or worker shutdown. Shielded so the frontend still hears
        # about it while this task is being torn down.
        await asyncio.shield(fail("cancelled (timeout or worker shutdown)"))
        raise
    except Exception as exc:
        log.exception("run %s failed", run_id)
        await fail(f"{type(exc).__name__}: {exc}")
        return {}
    finally:
        heartbeat.cancel()
        await asyncio.shield(runs.stop_beating(run_id))

    stats = {
        "entities": len(final.get("entities", {})),
        "claims": len(final.get("claims", {})),
        "sources": len(final.get("sources", {})),
        "scrapers": final.get("scrape_reports", []),
        "iterations": final.get("iteration", 0),
        "leads": len(final.get("leads", [])),
        "seed_id": final.get("seed_id"),
    }
    await runs.update(
        run_id, status=RunStatus.COMPLETED, finished_at=utcnow(), stats=stats
    )
    await emit(EventType.RUN_COMPLETED, stats)
    return stats


async def _heartbeat(runs: RunStore, run_id: str) -> None:
    """Proof of life for the run. If this process dies the heartbeat key
    expires and the API fails the run (see `core.runs.fail_if_orphaned`)."""
    interval = get_settings().heartbeat_interval_seconds
    while True:
        await asyncio.sleep(interval)
        try:
            await runs.beat(run_id)
        except Exception:  # a Redis blip must not kill the investigation
            log.warning("heartbeat for run %s failed", run_id, exc_info=True)
