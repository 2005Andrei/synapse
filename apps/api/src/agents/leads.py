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

import re
from collections import Counter

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from agents.llm import ask
from agents.prompts import LEADS_SYSTEM
from agents.resolution import name_key
from agents.state import InvestigationState, Record
from connectors.common.text import fold
from models.types import ClaimType, EntityType, Predicate

_LEAD_TYPES = {EntityType.PERSON.value, EntityType.ORGANIZATION.value}
_MAX_CANDIDATES = 40
_MAX_SOURCES = 15


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


def _lead(entity: Record, reason: str, score: int, by: str, **extra: object) -> Record:
    return {
        "query": name_of(entity),
        "entity_id": entity["id"],
        "entity_type": entity["type"],
        "reason": reason,
        "score": score,
        "by": by,
        **extra,
    }


# Role named in a claim (folded) -> how much that person runs the company.
# First match wins, so the specific titles come before the generic ones.
_ROLES = (
    ("director general", 100), ("ceo", 100), ("administrator unic", 95), ("presedinte", 95),
    ("administrator special", 30), ("administrator judiciar", 20),
    ("administrator", 90), ("director", 80), ("fondator", 70), ("actionar", 70), ("asociat", 70),
    ("membru", 60), ("reprezentant legal", 50), ("imputernicit", 40),
    ("lichidator", 10), ("avocat", 5),
)  # fmt: skip
_BY_PREDICATE = {
    Predicate.DIRECTOR_OF.value: ("director", 85),
    Predicate.CONTROLS.value: ("controls it", 75),
    Predicate.OWNS.value: ("owner", 70),
    Predicate.SHAREHOLDER_IN.value: ("shareholder", 70),
    Predicate.FOUNDED.value: ("founder", 70),
    Predicate.REPRESENTS.value: ("representative", 30),
}
# From this weight up, someone is close enough to the top to be searched without asking.
FOLLOW_FROM = 80


def officers(state: InvestigationState) -> list[Record]:
    """The people tied to the searched company by a role in it, most senior
    first, as leads. Empty when the search is not about a company."""
    entities = state.get("entities", {})
    seed = entities.get(state.get("seed_id", ""))
    if not seed or seed["type"] != EntityType.ORGANIZATION.value:
        return []

    best: dict[str, tuple[int, str, Record]] = {}  # person id -> (weight, role, claim)
    for claim in state.get("claims", {}).values():
        predicate = str(claim["predicate"])
        if predicate not in _BY_PREDICATE or seed["id"] not in claim.get("reference_ids", []):
            continue
        text = fold(claim.get("claim_text"))
        role, weight = next(
            ((title, weight) for title, weight in _ROLES if re.search(rf"\b{title}\b", text)),
            _BY_PREDICATE[predicate],
        )
        for person_id in claim["subject_ids"]:
            person = entities.get(person_id)
            if person and person["type"] == EntityType.PERSON.value and weight > best.get(person_id, (0,))[0]:
                best[person_id] = (weight, role, claim)

    # Same title: whoever the sources talk about more comes first.
    mentions = Counter(
        entity_id
        for claim in state.get("claims", {}).values()
        for entity_id in (*claim.get("subject_ids", []), *claim.get("reference_ids", []))
    )
    ranked = sorted(best.items(), key=lambda item: (-item[1][0], -mentions[item[0]], name_of(entities[item[0]])))
    return [
        _lead(entities[person_id], claim["claim_text"], weight, "role", kind="officer", role=role)
        for person_id, (weight, role, claim) in ranked
    ]


def with_officers(state: InvestigationState, others: list[Record], limit: int) -> list[Record]:
    """Officers first, then the other leads; the top officer is marked to be
    searched right away when the role is senior enough."""
    people = officers(state)[:limit]
    if people and people[0]["score"] >= FOLLOW_FROM:
        people[0] = {**people[0], "follow": True}
    taken = {lead["entity_id"] for lead in people}
    rest = [lead for lead in others if lead["entity_id"] not in taken]
    return [*people, *rest][: max(limit, len(people))]


def heuristic_leads(state: InvestigationState, limit: int) -> list[Record]:
    leads = []
    for entity, claims in candidates(state):
        if not claims:
            break  # sorted by claim count: nothing connected from here on
        kinds = Counter(str(claim["predicate"]).replace("_", " ").lower() for claim in claims)
        summary = ", ".join(f"{count}× {kind}" for kind, count in kinds.most_common(3))
        leads.append(_lead(entity, f"Appears in {len(claims)} claim(s): {summary}", len(claims), "heuristic"))
    return leads[:limit]


def briefing(state: InvestigationState, max_chars: int | None = None) -> str:
    """What the model gets to read: subject, candidates, source excerpts.

    `max_chars` is for models with a small context window: candidates come
    best first, so what is left out is the least connected, and the source
    excerpts only get the room the candidates leave.
    """
    lines = [f"Subject of the investigation: {state['query']}", "", "Candidates:"]
    room = max_chars if max_chars is not None else float("inf")
    room -= sum(len(line) + 1 for line in lines)

    def add(block: list[str]) -> bool:
        nonlocal room
        size = sum(len(line) + 1 for line in block)
        if size > room:
            return False
        lines.extend(block)
        room -= size
        return True

    for entity, claims in candidates(state):
        block = [f"- {name_of(entity)} ({entity['type']}), {len(claims)} claim(s)"]
        block.extend(f"    · {claim['claim_text'][:300]}" for claim in claims[:3])
        # Three quarters at most: the model should also see some of the sources.
        if max_chars is not None and room - sum(len(line) + 1 for line in block) < max_chars / 4:
            break
        add(block)

    if add(["", "Sources:"]):
        for source in list(state.get("sources", {}).values())[:_MAX_SOURCES]:
            excerpt = (source.get("content") or "")[:400]
            if not add([f"- [{source.get('publisher') or '?'}] {source.get('title')}: {excerpt}"]):
                break
    return "\n".join(lines)


async def llm_leads(
    model: BaseChatModel,
    state: InvestigationState,
    limit: int,
    max_chars: int | None = None,
    timeout: float | None = None,
) -> list[Record]:
    by_name = {
        name_key(name_of(entity), entity["type"]): (entity, claims)
        for entity, claims in candidates(state)
    }
    if not by_name:
        return []

    choices = await ask(
        model,
        LeadChoices,
        [
            ("system", LEADS_SYSTEM),
            ("human", f"{briefing(state, max_chars)}\n\nPick at most {limit} leads."),
        ],
        timeout,
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
