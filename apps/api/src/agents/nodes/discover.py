import logging
import time
from typing import Any

from langgraph.runtime import Runtime

from agents.extraction import ORIGIN, Extraction, extract
from agents.leads import heuristic_leads, llm_leads, with_officers
from agents.llm import get_chat_model, limits_for, llm_status
from agents.nodes.resolve import flag_name_matches
from agents.stages import graph_patch, stage
from agents.state import InvestigationState, PipelineContext
from core.events import EventType

log = logging.getLogger(__name__)
AGENT = "discovery"


@stage("discover")
async def discover(
    state: InvestigationState, runtime: Runtime[PipelineContext]
) -> dict[str, Any]:
    """Discovery stage: get more out of what the scrapers brought back.

    With a chat model (LLM_MODEL):
      1. read the article texts and add the people, companies and claims they
         state to the graph (`agents.extraction`),
      2. pick the follow-up searches worth running (`agents.leads`).
    Without one, step 1 is skipped and step 2 goes by claim count.

    Still to come, in this same node: letting the model run follow-up scrapers
    itself through `agents.tools` instead of only proposing them.
    """
    ctx = runtime.context

    async def say(text: str) -> None:
        await ctx.emit(EventType.AGENT_MESSAGE, {"agent": AGENT, "text": text})

    # The run's own model when the worker resolved one, else the server default.
    model = ctx.model if ctx.llm is not None else get_chat_model()
    status = ctx.llm or llm_status()
    update: dict[str, Any] = {}

    if model is None and status["problem"]:
        await say(f"The model {status['model']} could not be loaded ({status['problem']}). Continuing without it.")

    limits = limits_for(status["model"])
    started = time.monotonic()
    # The reading gets three quarters of a slow model's time; picking leads the rest.
    deadline = None if limits.budget is None else started + limits.budget

    if model is not None:
        try:
            reading_until = None if limits.budget is None else started + limits.budget * 0.75
            found = await extract(model, state, ctx.settings, limits, reading_until)
        except Exception as exc:  # a model outage must not fail the run
            log.warning("reading the sources with the model failed", exc_info=True)
            await say(f"Model call failed while reading the sources ({_why(exc, status)}); skipped.")
        else:
            update = await _add_to_graph(found, state, ctx)
            await say(_summary(found))
            # The leads below should see what the articles added.
            state = {
                **state,
                "entities": {**state.get("entities", {}), **update.get("entities", {})},
                "claims": {**state.get("claims", {}), **update.get("claims", {})},
            }

    limit = ctx.settings.max_leads
    leads, by = [], "heuristic"
    left = None if deadline is None else deadline - time.monotonic()
    if model is not None and left is not None and left < 20:
        await say("The model had no time left to pick the leads; used the heuristic instead.")
    elif model is not None:
        try:
            # A local model silently drops what does not fit its context window,
            # and is slow: it gets a shorter briefing than an article.
            fits = limits.max_source_chars // 2 if status.get("local") else None
            timeout = limits.timeout if left is None else min(limits.timeout, left)
            leads, by = await llm_leads(model, state, limit, fits, timeout), "llm"
        except Exception as exc:
            log.warning("lead selection by the model failed", exc_info=True)
            await say(f"Model call failed ({_why(exc, status)}); used the heuristic instead.")
    if by == "heuristic":
        leads = heuristic_leads(state, limit)
    # Whoever picked the rest, the people who run the searched company lead the list.
    leads = with_officers(state, leads, limit)

    how = "picked by the model" if by == "llm" else "most connected entities; set LLM_MODEL for model-picked leads"
    await say(f"{len(leads)} follow-up lead(s) proposed ({how}).")
    await ctx.emit(EventType.AGENT_LEADS, {"agent": AGENT, "by": by, "leads": leads})
    return {**update, "leads": leads}


async def _add_to_graph(
    found: Extraction, state: InvestigationState, ctx: PipelineContext
) -> dict[str, Any]:
    """Publish what the model read and return it as a state update."""
    update: dict[str, Any] = {"sources_read": [*state.get("sources_read", []), *found.read]}
    if not (found.entities or found.claims):
        return update

    # A new name may resemble the search ("Ion Popescu jr."): flag it like the
    # resolve stage flags scraped ones, so it lands in its own identity.
    name = state.get("name_query") or state["query"]
    flagged, name_claims = flag_name_matches(list(found.entities.values()), state.get("seed_id", ""), name)
    entities = {**found.entities, **flagged}
    claims = {**found.claims, **name_claims}

    await ctx.emit(
        EventType.GRAPH_PATCH,
        graph_patch(ORIGIN, entities=entities.values(), claims=claims.values(), by="llm"),
    )
    return {**update, "entities": entities, "claims": claims}


def _why(exc: Exception, status: dict[str, Any] | None = None) -> str:
    """"AuthenticationError: invalid x-api-key", short enough for the event log."""
    if isinstance(exc, TimeoutError) and (status or {}).get("local"):
        # By far the usual reason: an Ollama build without GPU support.
        return "the local model was too slow; `ollama ps` showing 100% CPU means it is not using the GPU"
    detail = " ".join(str(exc).split())[:160]
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def _summary(found: Extraction) -> str:
    if not found.eligible:
        return "No article text to read."
    parts = [
        (
            f"Read {len(found.read)} of {found.eligible} article(s): "
            f"{len(found.entities)} new entities, {len(found.claims)} claims."
        )
    ]
    if found.discarded:
        parts.append(f"{found.discarded} statement(s) discarded: no matching quote in the text, or an unknown name.")
    if found.failed:
        parts.append(f"{found.failed} article(s) could not be read.")
    if found.out_of_time:
        parts.append(f"{found.out_of_time} article(s) left unread: the model ran out of time (LLM_LOCAL_BUDGET_SECONDS).")
    if found.truncated:
        parts.append(f"{found.truncated} long article(s) were read only in part.")
    if found.eligible > len(found.read) + found.failed + found.out_of_time:
        parts.append("The rest are over the per-search limit (LLM_MAX_SOURCES; LLM_LOCAL_MAX_SOURCES for a local model).")
    return " ".join(parts)
