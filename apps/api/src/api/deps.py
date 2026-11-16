from typing import Annotated

from arq.connections import ArqRedis
from fastapi import Depends, HTTPException, Request

from core.events import EventBus
from core.runs import Run, RunStore


def get_runs(request: Request) -> RunStore:
    return request.app.state.runs


def get_bus(request: Request) -> EventBus:
    return request.app.state.bus


def get_queue(request: Request) -> ArqRedis:
    return request.app.state.queue


async def get_run(run_id: str, runs: Annotated[RunStore, Depends(get_runs)]) -> Run:
    run = await runs.get(run_id)
    if run is None:
        raise HTTPException(404, "investigation not found (or expired)")
    return run


Runs = Annotated[RunStore, Depends(get_runs)]
Bus = Annotated[EventBus, Depends(get_bus)]
Queue = Annotated[ArqRedis, Depends(get_queue)]
CurrentRun = Annotated[Run, Depends(get_run)]
