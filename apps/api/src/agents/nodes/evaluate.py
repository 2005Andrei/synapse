from typing import Any

from langgraph.runtime import Runtime

from agents.stages import stage
from agents.state import InvestigationState, PipelineContext
from core.events import EventType


@stage("evaluate")
async def evaluate(
    state: InvestigationState, runtime: Runtime[PipelineContext]
) -> dict[str, Any]:
    """Evaluation agent. NOT IMPLEMENTED YET: this node is the seam for it.

    What goes here: grade the claims the discovery agent produced (is the
    claim supported by its sources? do sources contradict each other?), set
    `claim_status` / `confidence`, and decide whether another discovery round
    is worth it. Returning `done=False` loops back to `discover`.
    """
    await runtime.context.emit(
        EventType.AGENT_SKIPPED,
        {"agent": "evaluation", "reason": "evaluation agent is not implemented yet"},
    )
    return {"iteration": state.get("iteration", 0) + 1, "done": True}
