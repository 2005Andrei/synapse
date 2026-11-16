"""State and context of the investigation graph.

State holds plain JSON-able dicts (not pydantic objects) so it can be
checkpointed to Redis later without custom serializers.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from core.config import Settings

Record = dict[str, Any]
Records = dict[str, Record | None]


def merge_records(current: Records, update: Records) -> Records:
    """Reducer: upsert by id. A None value deletes the record."""
    merged = {**current}
    for key, value in update.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


class InvestigationState(TypedDict, total=False):
    run_id: str
    query: str
    scrapers: list[str]
    # What name-only sources are asked for. Differs from `query` when the
    # query is a CUI: then it is the company's name (see nodes/plan.py).
    name_query: str

    # The entity the investigation is about. Starts as a placeholder built from
    # the query; resolution swaps it for the real record once one is found.
    seed_id: str

    # The knowledge graph so far, keyed by id.
    entities: Annotated[Records, merge_records]
    claims: Annotated[Records, merge_records]
    sources: Annotated[Records, merge_records]

    scrape_reports: list[Record]

    # Follow-up searches worth running next (see agents/leads.py).
    leads: list[Record]

    # Agent loop bookkeeping.
    iteration: int
    done: bool


Emit = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class PipelineContext:
    """Per-run dependencies handed to every node (not part of the state)."""

    emit: Emit  # publish a run event to the frontend
    settings: Settings
