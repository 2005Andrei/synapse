"""Helpers shared by the graph nodes."""

import functools
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from langgraph.runtime import Runtime

from agents.state import InvestigationState, PipelineContext, Record
from core.events import EventType

Node = Callable[[InvestigationState, Runtime[PipelineContext]], Awaitable[dict[str, Any]]]

_EXCERPT_LENGTH = 280


def stage(name: str) -> Callable[[Node], Node]:
    """Announce a node's start and end on the run's event stream."""

    def decorate(node: Node) -> Node:
        @functools.wraps(node)
        async def wrapper(
            state: InvestigationState, runtime: Runtime[PipelineContext]
        ) -> dict[str, Any]:
            emit = runtime.context.emit
            info = {"stage": name, "iteration": state.get("iteration", 0)}
            await emit(EventType.STAGE_STARTED, info)
            started = time.perf_counter()
            update = await node(state, runtime)
            duration_ms = int((time.perf_counter() - started) * 1000)
            await emit(EventType.STAGE_COMPLETED, {**info, "duration_ms": duration_ms})
            return update

        return wrapper

    return decorate


def graph_patch(
    origin: str,
    *,
    entities: Iterable[Record] = (),
    claims: Iterable[Record] = (),
    sources: Iterable[Record] = (),
    **extra: Any,
) -> dict[str, Any]:
    """Payload of a `graph.patch` event: records to upsert into the frontend
    graph. Sources travel without their full text, only an excerpt."""
    return {
        "origin": origin,
        "entities": list(entities),
        "claims": list(claims),
        "sources": [_light(source) for source in sources],
        **extra,
    }


def _light(source: Record) -> Record:
    content = source.get("content") or ""
    excerpt = content[:_EXCERPT_LENGTH] + ("…" if len(content) > _EXCERPT_LENGTH else "")
    return {**source, "content": excerpt, "content_length": len(content)}
