"""arq worker entrypoint:  arq workers.settings.WorkerSettings"""

import logging
from typing import Any

from agents.graph import build_graph
from core.config import get_settings
from core.events import EventBus
from core.redis import arq_redis_settings, create_redis
from core.runs import RunStore
from workers.tasks import run_investigation

settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # arq's own connection (ctx["redis"]) is for the job queue; this one is for
    # run metadata and event streams.
    ctx["data_redis"] = create_redis()
    ctx["runs"] = RunStore(ctx["data_redis"])
    ctx["bus"] = EventBus(ctx["data_redis"])
    ctx["graph"] = build_graph()


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["data_redis"].aclose()


class WorkerSettings:
    functions = [run_investigation]
    redis_settings = arq_redis_settings()
    on_startup = startup
    on_shutdown = shutdown

    max_jobs = settings.worker_max_jobs
    job_timeout = settings.job_timeout_seconds
    # A half-finished investigation has already streamed events to the browser;
    # re-running it silently would duplicate them. Fail it and let the user retry.
    max_tries = 1
    keep_result = 3600
