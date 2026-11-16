import logging
from typing import Any

from langgraph.runtime import Runtime

from agents.leads import heuristic_leads, llm_leads
from agents.llm import get_chat_model
from agents.stages import stage
from agents.state import InvestigationState, PipelineContext
from core.events import EventType

log = logging.getLogger(__name__)
AGENT = "discovery"


@stage("discover")
async def discover(
    state: InvestigationState, runtime: Runtime[PipelineContext]
) -> dict[str, Any]:
    """Discovery stage: decide what is worth looking up next.

    Works today as "propose leads" (see `agents.leads`): the most connected
    people / companies, picked by a chat model when LLM_MODEL is set and by
    claim count otherwise. The frontend offers each lead as a new search.

    Still to come, in this same node:
      1. Read the full text of `state["sources"]` and extract entities and
         claims from it (structured output, each claim citing `source_ids`),
         returned as {"entities": ..., "claims": ...} + a `graph.patch` event.
      2. Let the model run follow-up scrapers itself through `agents.tools`.
    """
    ctx = runtime.context
    limit = ctx.settings.max_leads
    model = get_chat_model()
    leads, by = [], "heuristic"

    if model is not None:
        try:
            leads, by = await llm_leads(model, state, limit), "llm"
        except Exception as exc:  # a model outage must not fail the run
            log.warning("lead selection by the model failed", exc_info=True)
            await ctx.emit(
                EventType.AGENT_MESSAGE,
                {"agent": AGENT, "text": f"Model call failed ({type(exc).__name__}); used the heuristic instead."},
            )
    if by == "heuristic":
        leads = heuristic_leads(state, limit)

    how = "picked by the model" if by == "llm" else "most connected entities; set LLM_MODEL for model-picked leads"
    await ctx.emit(
        EventType.AGENT_MESSAGE,
        {"agent": AGENT, "text": f"{len(leads)} follow-up lead(s) proposed ({how})."},
    )
    await ctx.emit(EventType.AGENT_LEADS, {"agent": AGENT, "by": by, "leads": leads})
    return {"leads": leads}
