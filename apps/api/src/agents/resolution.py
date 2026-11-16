"""Entity resolution, naive first version.

Scrapers report *mentions*: "a person called X appears in this court case".
Resolution decides which mentions are the same real-world entity and rewrites
the graph accordingly.

Right now the rule is just "same kind + same normalised name", which will merge
two different people who share a name. It is a placeholder for a real resolver
(more signals, a confidence score, an LLM for the hard cases); the function
signature is what the rest of the pipeline depends on.

Names that are only *similar* are never merged: `agents.matching` flags them
instead, and the resolve node links them to the subject as a hypothesis.
"""

import re
from dataclasses import dataclass, field

from agents.matching import LEGAL_FORMS
from agents.state import Record
from connectors.common.text import fold
from models.types import EntityType

_MERGEABLE = {EntityType.PERSON.value, EntityType.ORGANIZATION.value}


def name_key(name: str, entity_type: str) -> str:
    """Comparison key for a name. Word order is ignored (registries write
    "POPESCU ION", newspapers "Ion Popescu"), as are company legal forms."""
    words = re.split(r"[^a-z0-9-]+", fold(name).replace(".", ""))
    if entity_type == EntityType.ORGANIZATION.value:
        words = [word for word in words if word not in LEGAL_FORMS]
    return " ".join(sorted(word for word in words if word))


@dataclass
class Resolution:
    entities: dict[str, Record]  # merged entities that changed, by id
    merged: dict[str, str] = field(default_factory=dict)  # old id -> surviving id
    seed_id: str = ""


def resolve_entities(
    entities: dict[str, Record], seed_id: str, query: str
) -> Resolution:
    groups: dict[tuple[str, str], list[Record]] = {}
    for entity in entities.values():
        if entity["type"] not in _MERGEABLE:
            continue
        for alias in entity.get("aliases") or []:
            key = name_key(alias, entity["type"])
            if key:
                groups.setdefault((entity["type"], key), []).append(entity)

    result = Resolution(entities={}, seed_id=seed_id)

    def current(entity_id: str) -> str:
        while entity_id in result.merged:
            entity_id = result.merged[entity_id]
        return entity_id

    def merge(survivor: Record, other: Record) -> Record:
        merged = _merge(survivor, other)
        result.merged[other["id"]] = merged["id"]
        result.entities.pop(other["id"], None)
        result.entities[merged["id"]] = merged
        return merged

    def latest(entity_id: str) -> Record:
        entity_id = current(entity_id)
        return result.entities.get(entity_id) or entities[entity_id]

    # 1. Same kind + same name -> one entity.
    for members in groups.values():
        ids = list(dict.fromkeys(current(member["id"]) for member in members))
        if len(ids) < 2:
            continue
        survivor, *others = sorted((latest(i) for i in ids), key=_rank)
        for other in others:
            survivor = merge(survivor, other)

    # 2. The seed is a placeholder for "whatever the user searched". If a real
    #    record matches the query, that record becomes the seed.
    #    (A CUI query needs none of this: its seed already has the company's id.)
    seed = entities.get(seed_id)
    if seed and seed["type"] == EntityType.UNKNOWN.value:
        match = _find_seed_match(groups, query)
        if match:
            merge(latest(match), seed)
            result.seed_id = current(match)

    return result


def remap_claims(
    claims: dict[str, Record], merged: dict[str, str]
) -> dict[str, Record]:
    """Claims whose subject/reference ids changed because of a merge."""

    def current(entity_id: str) -> str:
        while entity_id in merged:
            entity_id = merged[entity_id]
        return entity_id

    changed = {}
    for claim in claims.values():
        subject_ids = list(dict.fromkeys(current(i) for i in claim["subject_ids"]))
        reference_ids = list(dict.fromkeys(current(i) for i in claim["reference_ids"]))
        if subject_ids != claim["subject_ids"] or reference_ids != claim["reference_ids"]:
            changed[claim["id"]] = {
                **claim,
                "subject_ids": subject_ids,
                "reference_ids": reference_ids,
            }
    return changed


def _rank(entity: Record) -> tuple:
    """Sort key: the entity that should survive a merge comes first."""
    attributes = entity.get("attributes") or {}
    return ("cui" not in attributes, -len(attributes), entity["id"])


def _merge(survivor: Record, other: Record) -> Record:
    aliases = list(
        dict.fromkeys([*(survivor.get("aliases") or []), *(other.get("aliases") or [])])
    )
    return {
        **survivor,
        "description": survivor.get("description") or other.get("description") or "",
        "aliases": aliases,
        "attributes": {**(other.get("attributes") or {}), **(survivor.get("attributes") or {})},
    }


def _find_seed_match(
    groups: dict[tuple[str, str], list[Record]], query: str
) -> str | None:
    candidates = [
        members[0]
        for (entity_type, key), members in groups.items()
        if key == name_key(query, entity_type)
    ]
    return min(candidates, key=_rank)["id"] if candidates else None
