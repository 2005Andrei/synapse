"""Leads: follow-up searches worth running after the first pass.

The discovery stage does not launch them itself. Every lead is a real person
or company that would get looked up across all sources, so the user decides:
leads are sent to the frontend, which offers them as one-click searches (each
becomes its own run, on its own worker).

Two ways to pick them, same output:
  - `heuristic_leads`: the people / companies with the most claims attached.
  - `llm_leads`: a chat model reads the same candidates plus the source
    excerpts and picks and explains. Used when LLM_MODEL is set.
"""

from collections import Counter

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from agents.resolution import name_key
from agents.state import InvestigationState, Record
from models.types import ClaimType, EntityType

_LEAD_TYPES = {EntityType.PERSON.value, EntityType.ORGANIZATION.value}
_MAX_CANDIDATES = 40
_MAX_SOURCES = 15

SYSTEM_PROMPT = """You help an investigative journalist decide what to look up next.
You get the subject of an investigation, the people and companies found so far
(with the claims that mention them) and excerpts of the sources. Pick the few
that are most worth a search of their own in public registries, court records
and the press. Prefer entities with a concrete, documented link to the subject.
Only pick names from the candidate list, spelled exactly as given. Give one
short, factual reason each; do not speculate about wrongdoing."""


class LeadChoice(BaseModel):
    query: str = Field(description="Candidate name, exactly as listed")
    reason: str = Field(description="One short sentence: why this is worth a search")


class LeadChoices(BaseModel):
    leads: list[LeadChoice]


def name_of(entity: Record) -> str:
    return (entity.get("aliases") or [""])[0]


def candidates(state: InvestigationState) -> list[tuple[Record, list[Record]]]:
    """People and companies other than the subject, most connected first,
    each with the claims they take part in."""
    entities = state.get("entities", {})
    seed_id = state.get("seed_id")
    claims_of: dict[str, list[Record]] = {}
    for claim in state.get("claims", {}).values():
        if claim.get("type") == ClaimType.HYPOTHESIS.value:
            continue  # name resemblance is not a connection
        for entity_id in (*claim.get("subject_ids", []), *claim.get("reference_ids", [])):
            claims_of.setdefault(entity_id, []).append(claim)

    found = [
        (entity, claims_of.get(entity_id, []))
        for entity_id, entity in entities.items()
        if entity_id != seed_id and entity["type"] in _LEAD_TYPES and name_of(entity)
    ]
    # Ties (very common: most court parties appear once) go to people first.
    found.sort(
        key=lambda pair: (
            -len(pair[1]),
            pair[0]["type"] != EntityType.PERSON.value,
            name_of(pair[0]),
        )
    )
    return found[:_MAX_CANDIDATES]


def _lead(entity: Record, reason: str, score: int, by: str) -> Record:
    return {
        "query": name_of(entity),
        "entity_id": entity["id"],
        "entity_type": entity["type"],
        "reason": reason,
        "score": score,
        "by": by,
    }


def heuristic_leads(state: InvestigationState, limit: int) -> list[Record]:
    leads = []
    for entity, claims in candidates(state):
        if not claims:
            break  # sorted by claim count: nothing connected from here on
        kinds = Counter(str(claim["predicate"]).replace("_", " ").lower() for claim in claims)
        summary = ", ".join(f"{count}× {kind}" for kind, count in kinds.most_common(3))
        leads.append(_lead(entity, f"Appears in {len(claims)} claim(s): {summary}", len(claims), "heuristic"))
    return leads[:limit]


def briefing(state: InvestigationState) -> str:
    """What the model gets to read: subject, candidates, source excerpts."""
    lines = [f"Subject of the investigation: {state['query']}", "", "Candidates:"]
    for entity, claims in candidates(state):
        lines.append(f"- {name_of(entity)} ({entity['type']}), {len(claims)} claim(s)")
        lines.extend(f"    · {claim['claim_text']}" for claim in claims[:3])

    lines += ["", "Sources:"]
    for source in list(state.get("sources", {}).values())[:_MAX_SOURCES]:
        excerpt = (source.get("content") or "")[:400]
        lines.append(f"- [{source.get('publisher') or '?'}] {source.get('title')}: {excerpt}")
    return "\n".join(lines)


async def llm_leads(model: BaseChatModel, state: InvestigationState, limit: int) -> list[Record]:
    by_name = {
        name_key(name_of(entity), entity["type"]): (entity, claims)
        for entity, claims in candidates(state)
    }
    if not by_name:
        return []

    chooser = model.with_structured_output(LeadChoices)
    choices = await chooser.ainvoke(
        [
            ("system", SYSTEM_PROMPT),
            ("human", f"{briefing(state)}\n\nPick at most {limit} leads."),
        ]
    )

    leads = []
    for choice in choices.leads:
        # The model may only pick from what the scrapers actually found.
        match = next(
            (by_name[key] for kind in _LEAD_TYPES if (key := name_key(choice.query, kind)) in by_name),
            None,
        )
        if match:
            entity, claims = match
            leads.append(_lead(entity, choice.reason, len(claims), "llm"))
    return leads[:limit]
