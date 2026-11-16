import asyncio
import logging
import re
from typing import Any

from langgraph.runtime import Runtime

from agents.matching import LEGAL_FORMS
from agents.stages import graph_patch, stage
from agents.state import InvestigationState, PipelineContext
from connectors import registry
from connectors.common.cui import parse_cui
from connectors.common.text import fold
from core.events import EventType
from models.ids import company_id, stable_id
from models.schemas import Entity
from models.types import EntityType

log = logging.getLogger(__name__)


@stage("plan")
async def plan(
    state: InvestigationState, runtime: Runtime[PipelineContext]
) -> dict[str, Any]:
    """Turn the query into a seed entity and decide what each scraper is asked.

    A CUI only means something to the registries. So for a CUI query the
    company's name is looked up first, and the name-only sources (courts,
    press) are asked for that instead of for a number.

    Later: let an LLM classify the query (person / company / topic) and pick
    scrapers accordingly. For now every requested scraper runs.
    """
    query = state["query"]
    cui = parse_cui(query)
    scrapers = [name for name in state.get("scrapers") or registry.SCRAPERS if name in registry.SCRAPERS]

    company = await _company_name(cui) if cui and "anaf" in scrapers else None
    name_query = search_name(company) if company else query
    if company:
        await runtime.context.emit(
            EventType.AGENT_MESSAGE,
            {
                "agent": "plan",
                "text": f"CUI {cui} is {company}; courts and press are searched for “{name_query}”.",
            },
        )

    seed = Entity(
        id=company_id(cui) if cui else stable_id("entity", "seed", fold(query)),
        type=EntityType.ORGANIZATION if cui else EntityType.UNKNOWN,
        description=f"Subject of the investigation: {query}",
        aliases=[company or (f"CUI {cui}" if cui else query)],
        attributes={"cui": cui} if cui else {},
    ).model_dump(mode="json")

    await runtime.context.emit(
        EventType.GRAPH_PATCH, graph_patch("plan", entities=[seed], seed_id=seed["id"])
    )
    return {
        "seed_id": seed["id"],
        "scrapers": scrapers,
        "name_query": name_query,
        "entities": {seed["id"]: seed},
        "iteration": 0,
        "done": False,
    }


async def _company_name(cui: str) -> str | None:
    def lookup() -> str | None:
        with registry.get_scraper("anaf") as anaf:
            return anaf.company_name(cui)  # type: ignore[attr-defined]

    try:
        return await asyncio.wait_for(asyncio.to_thread(lookup), 20)
    except Exception:  # the run goes on without it, just less precisely
        log.warning("could not look up the name of CUI %s", cui, exc_info=True)
        return None


def search_name(company: str) -> str:
    """"S.C. DEDEMAN S.R.L." -> "DEDEMAN": what a journalist would type."""
    words = re.split(r"[^\w-]+", company.replace(".", ""))
    kept = [word for word in words if word and fold(word) not in LEGAL_FORMS]
    return " ".join(kept) or company
