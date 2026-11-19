from typing import Any

from langgraph.runtime import Runtime

from agents.matching import EXACT, best_match
from agents.resolution import remap_claims, resolve_entities
from agents.stages import graph_patch, stage
from agents.state import InvestigationState, PipelineContext, Record
from core.events import EventType
from models.ids import claim_id
from models.schemas import Claim
from models.types import ClaimStatus, ClaimType, EntityType, Predicate


@stage("resolve")
async def resolve(
    state: InvestigationState, runtime: Runtime[PipelineContext]
) -> dict[str, Any]:
    """Merge duplicate entities, tie search hits to the seed, and tell the
    subject of the search apart from people / companies that only share part
    of its name."""
    entities = state.get("entities", {})
    # For a CUI search the name to compare with is the company's, not the number.
    name = state.get("name_query") or state["query"]
    resolution = resolve_entities(entities, state["seed_id"], name)
    seed_id = resolution.seed_id

    claims = remap_claims(state.get("claims", {}), resolution.merged)
    survivors = [
        resolution.entities.get(entity_id, entity)
        for entity_id, entity in entities.items()
        if entity_id not in resolution.merged
    ]
    claims.update(_link_articles(survivors, seed_id, state["query"]))

    flagged, name_claims = flag_name_matches(survivors, seed_id, name)
    resolution.entities.update(flagged)
    claims.update(name_claims)

    await runtime.context.emit(
        EventType.GRAPH_PATCH,
        graph_patch(
            "resolve",
            entities=resolution.entities.values(),
            claims=claims.values(),
            removed_entity_ids=list(resolution.merged),
            merged=resolution.merged,
            seed_id=seed_id,
        ),
    )
    return {
        "seed_id": seed_id,
        "entities": {**dict.fromkeys(resolution.merged), **resolution.entities},
        "claims": claims,
    }


def _link_articles(entities: list[Record], seed_id: str, query: str) -> dict[str, Record]:
    """An article that came back from a search for the query presumably
    mentions it. Recorded as a weak, unverified claim until the discovery
    agent actually reads the article and replaces it with real ones."""
    claims = {}
    for entity in entities:
        attributes = entity.get("attributes") or {}
        if entity["type"] != EntityType.DOCUMENT.value:
            continue
        if attributes.get("document_type") != "article":
            continue
        title = (entity.get("aliases") or ["?"])[0]
        claim = Claim(
            id=claim_id(entity["id"], Predicate.MENTIONS, seed_id),
            type=ClaimType.RELATIONSHIP,
            subject_ids=[entity["id"]],
            predicate=Predicate.MENTIONS,
            claim_text=f"„{title}” came up in a search for “{query}”.",
            reference_ids=[seed_id],
            source_ids=[attributes["source_id"]] if attributes.get("source_id") else [],
            claim_status=ClaimStatus.UNVERIFIED,
            confidence=0.3,
        ).model_dump(mode="json")
        claims[claim["id"]] = claim
    return claims


# Entities that can be "the one that was searched for".
_NAMED = {EntityType.PERSON.value, EntityType.ORGANIZATION.value}
SAME_NAME, SIMILAR_NAME = "Same_Name", "Similar_Name"


def flag_name_matches(
    entities: list[Record], seed_id: str, name: str
) -> tuple[dict[str, Record], dict[str, Record]]:
    """Label every person / company by how its name compares with the search
    (`attributes.match`: "exact" | "similar", plus `match_note`), and link the
    ones that are not the seed to it.

    The link is a hypothesis ("may be the same"), not a fact: a longer or
    differently spelled name is, as far as anyone can tell from the name, a
    different person. Keeping them apart but visibly related is what lets the
    frontend divide the results by identity.
    """
    flagged: dict[str, Record] = {}
    claims: dict[str, Record] = {}

    for entity in entities:
        if entity["type"] not in _NAMED:
            continue
        aliases = entity.get("aliases") or []
        match = best_match(aliases, name, entity["type"])
        if match is None:
            continue

        # `match_of`: a flag only means something relative to the search it
        # was made for (graphs can hold the results of several searches).
        attributes = {**(entity.get("attributes") or {}), "match": match.kind, "match_of": seed_id}
        attributes.pop("match_note", None)
        if match.note:
            attributes["match_note"] = match.note
        flagged[entity["id"]] = {**entity, "attributes": attributes}
        if entity["id"] == seed_id:
            continue

        exact = match.kind == EXACT
        label = aliases[0] if aliases else "?"
        claim = Claim(
            id=claim_id(entity["id"], SAME_NAME if exact else SIMILAR_NAME, seed_id),
            type=ClaimType.HYPOTHESIS,
            subject_ids=[entity["id"]],
            predicate=SAME_NAME if exact else SIMILAR_NAME,
            claim_text=(
                f"„{label}” has the same name as the search “{name}” but is a separate record."
                if exact
                else f"„{label}” resembles the search “{name}” ({match.note}). "
                "Kept separate: it may be someone else."
            ),
            reference_ids=[seed_id],
            source_ids=[],
            claim_status=ClaimStatus.INFERRED,
            confidence=0.5 if exact else 0.25,
        ).model_dump(mode="json")
        claims[claim["id"]] = claim

    return flagged, claims
