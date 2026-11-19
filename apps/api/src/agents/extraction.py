"""Reading sources with a chat model: who an article names and what it says.

The scrapers know that an article mentions the subject; they do not know what
it says. Here the model reads the article and answers in a fixed shape
(`Reading`), and code decides what of that enters the graph:

  - a claim is kept only if its quote really is in the article,
  - a name the scrapers already found is linked to that entity, not duplicated,
  - a claim the registries already hold gains the article as one more source,
  - a new entity is kept only if a kept claim is about it.

So the model proposes and never writes to the graph directly.
"""

import asyncio
import time
import logging
import re
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from agents.llm import Limits, ask, limits_for
from agents.prompts import EXTRACTION_SYSTEM
from agents.resolution import name_key
from agents.state import InvestigationState, Record
from connectors.common.text import fold
from core.config import Settings
from models.ids import claim_id, mention_id
from models.schemas import Claim, Entity
from models.types import ClaimStatus, ClaimType, EntityType, Predicate, SourceType

log = logging.getLogger(__name__)

ORIGIN = "discover"  # the `origin` of the graph patches made here
RELATED, STATED = "Related_To", "Stated"  # when no predicate of the enum fits
REPORTED_CONFIDENCE, ALLEGED_CONFIDENCE = 0.6, 0.4

_READABLE = {SourceType.NEWS_ARTICLE.value, SourceType.INVESTIGATIVE_ARTICLE.value}
_NAMED = (EntityType.PERSON.value, EntityType.ORGANIZATION.value)
# Relations a person (or company) has over a company; the object is never a person.
_OVER_A_COMPANY = {
    Predicate.FOUNDED.value, Predicate.DIRECTOR_OF.value, Predicate.OWNS.value,
    Predicate.CONTROLS.value, Predicate.SHAREHOLDER_IN.value,
}  # fmt: skip
_MIN_TEXT = 300
_WORTH_STARTING = 20  # seconds: with less than this left, a call is not started  # shorter than this is a teaser, not an article
_MIN_QUOTE = 12


class Mention(BaseModel):
    name: str = Field(description="Full name, as the article writes it")
    type: EntityType = Field(description="Person or Organization")
    role: str = Field(description="Who they are according to the article, in a few words; empty if it does not say")


class Statement(BaseModel):
    subject: str = Field(description="Name of a listed entity")
    predicate: Predicate | None = Field(description="The closest relation; null if none fits")
    object: str | None = Field(description="Name of another listed entity; null for a fact about the subject alone")
    text: str = Field(description="The statement in one sentence, in the language of the article")
    quote: str = Field(description="The passage of the article that supports it, copied word for word")
    alleged: bool = Field(description="True for an accusation, suspicion or someone's claim; false for what the article presents as established")


class Reading(BaseModel):
    """What one article says."""

    entities: list[Mention]
    claims: list[Statement]


@dataclass
class Extraction:
    entities: dict[str, Record] = field(default_factory=dict)  # new ones only
    claims: dict[str, Record] = field(default_factory=dict)  # new, or existing with a source added
    read: list[str] = field(default_factory=list)  # ids of the sources the model answered for
    eligible: int = 0  # readable sources not read before
    failed: int = 0
    discarded: int = 0  # statements the model made that did not pass the checks
    truncated: int = 0  # sources longer than `llm_max_source_chars`
    out_of_time: int = 0  # sources not started: the model had used up its time


class OutOfTime(Exception):
    """The model's time for this search ran out before this call could start."""


def readable_sources(state: InvestigationState) -> list[Record]:
    """Article texts not read yet, newest first."""
    done = set(state.get("sources_read", []))
    sources = [
        source
        for source in state.get("sources", {}).values()
        if source["id"] not in done
        and source.get("type") in _READABLE
        and len(source.get("content") or "") >= _MIN_TEXT
    ]
    sources.sort(key=lambda source: (source.get("published_at") or "", source["id"]), reverse=True)
    return sources


async def extract(
    model: BaseChatModel,
    state: InvestigationState,
    settings: Settings,
    limits: Limits | None = None,
    deadline: float | None = None,
) -> Extraction:
    """Read up to `llm_max_sources` articles and return what holds up.

    One failed call costs that article only. If every call fails the error is
    raised, so the stage can say the model is down instead of "found nothing".
    `deadline` (on `time.monotonic()`) is when a slow local model has to stop:
    articles not started by then are left unread, to be read by a later search.
    """
    limits = limits or limits_for(settings.llm_model)
    sources = readable_sources(state)
    chosen = sources[: min(settings.llm_max_sources, limits.max_sources)]
    result = Extraction(eligible=len(sources))
    if not chosen:
        return result

    subject = _subject(state)
    max_chars = min(limits.max_source_chars, settings.llm_max_source_chars)
    slots = asyncio.Semaphore(min(limits.concurrency, settings.llm_concurrency))

    async def read(source: Record) -> Reading:
        text = source["content"][:max_chars]
        async with slots:
            left = None if deadline is None else deadline - time.monotonic()
            if left is not None and left < _WORTH_STARTING:
                raise OutOfTime
            return await ask(
                model,
                Reading,
                [("system", EXTRACTION_SYSTEM), ("human", _article(source, text, subject))],
                limits.timeout if left is None else min(limits.timeout, left),
            )

    readings = await asyncio.gather(*(read(source) for source in chosen), return_exceptions=True)
    result.out_of_time = sum(isinstance(reading, OutOfTime) for reading in readings)
    errors = [r for r in readings if isinstance(r, BaseException) and not isinstance(r, OutOfTime)]
    if errors and len(errors) + result.out_of_time == len(chosen):
        raise errors[0]

    known = _index(state.get("entities", {}))
    claims = state.get("claims", {})
    # (subject, predicate, object) -> claim id. Looked up by content because a
    # claim's id stops saying who it is about once resolution merges entities.
    relations = {
        (claim["subject_ids"][0], str(claim["predicate"]), claim["reference_ids"][0]): id
        for id, claim in claims.items()
        if claim.get("subject_ids") and claim.get("reference_ids")
    }
    for source, reading in zip(chosen, readings):
        if isinstance(reading, OutOfTime):
            continue
        if isinstance(reading, BaseException):
            log.warning("the model could not read %s: %r", source.get("url"), reading)
            result.failed += 1
            continue
        result.read.append(source["id"])
        result.truncated += len(source["content"]) > max_chars
        text = source["content"][:max_chars]
        _keep(reading, source, text, known, claims, relations, result)
    return result


def _keep(
    reading: Reading,
    source: Record,
    text: str,
    known: dict[tuple[str, str], str],
    existing_claims: dict[str, Record],
    relations: dict[tuple[str, str, str], str],
    result: Extraction,
) -> None:
    """Apply the checks to one reading and add what passes to `result`."""
    haystack = _squash(text)
    mentioned: dict[str, Record] = {}  # entity id -> entity record, new entities only
    ids: dict[tuple[str, str], str] = {}  # (name key, type) -> entity id, for this article

    for mention in reading.entities:
        kind = mention.type.value
        key = name_key(mention.name, kind)
        if kind not in _NAMED or not key:
            continue
        if (key, kind) in known:  # the scrapers (or an earlier article) have it
            ids[key, kind] = known[key, kind]
            continue
        entity = Entity(
            id=mention_id(ORIGIN, kind, key),
            type=mention.type,
            description=mention.role.strip() or "Menționat în presă",
            aliases=[mention.name.strip()],
            attributes={"extracted_by": "llm", "source_id": source["id"]},
        ).model_dump(mode="json")
        ids[key, kind] = entity["id"]
        mentioned[entity["id"]] = entity

    kinds: dict[str, str] = {}  # entity id -> type, for the entities statements name

    def entity_id(name: str | None) -> str | None:
        for kind in _NAMED:
            found = ids.get((name_key(name or "", kind), kind)) or known.get((name_key(name or "", kind), kind))
            if found:
                kinds[found] = kind
                return found
        return None

    for statement in reading.claims:
        subject_id, object_id = entity_id(statement.subject), entity_id(statement.object)
        quote = _squash(statement.quote)
        grounded = len(quote) >= _MIN_QUOTE and quote in haystack
        if (
            not grounded
            or not subject_id
            or (statement.object and not object_id)  # never downgrade a relation to a fact
            or subject_id == object_id
            or not statement.text.strip()
        ):
            result.discarded += 1
            continue

        predicate = statement.predicate.value if statement.predicate else (RELATED if object_id else STATED)
        # "ACME founded Maria": small models get the direction wrong, and for
        # these relations only one direction is possible.
        if predicate in _OVER_A_COMPANY and object_id and kinds.get(object_id) == _NAMED[0] != kinds.get(subject_id):
            subject_id, object_id = object_id, subject_id
        id = str(claim_id(subject_id, predicate, object_id or f"{source['id']}:{quote[:80]}"))
        if object_id:
            id = relations.setdefault((subject_id, predicate, object_id), id)
        before = result.claims.get(id) or existing_claims.get(id)
        if before:  # same relation, one more source: corroboration, not a new claim
            if source["id"] not in before["source_ids"]:
                result.claims[id] = {**before, "source_ids": [*before["source_ids"], source["id"]]}
            continue

        result.claims[id] = Claim(
            id=id,
            type=ClaimType.RELATIONSHIP if object_id else ClaimType.FACT,
            subject_ids=[subject_id],
            predicate=predicate,
            claim_text=statement.text.strip(),
            reference_ids=[object_id] if object_id else [],
            source_ids=[source["id"]],
            quote=statement.quote.strip(),
            claim_status=ClaimStatus.ALLEGED if statement.alleged else ClaimStatus.REPORTED,
            confidence=ALLEGED_CONFIDENCE if statement.alleged else REPORTED_CONFIDENCE,
        ).model_dump(mode="json")
        for used in filter(None, (subject_id, object_id)):
            if used in mentioned:
                result.entities.setdefault(used, mentioned[used])

    # Later articles link to the entities this one introduced.
    for (key, kind), found in ids.items():
        if found in result.entities:
            known[key, kind] = found


def _index(entities: dict[str, Record]) -> dict[tuple[str, str], str]:
    """(name key, type) -> entity id, for every name the graph already has."""
    index: dict[tuple[str, str], str] = {}
    for entity in entities.values():
        if entity["type"] not in _NAMED:
            continue
        for alias in entity.get("aliases") or []:
            if key := name_key(alias, entity["type"]):
                index.setdefault((key, entity["type"]), entity["id"])
    return index


def _subject(state: InvestigationState) -> str:
    seed = state.get("entities", {}).get(state.get("seed_id", ""))
    return ((seed or {}).get("aliases") or [state.get("name_query") or state["query"]])[0]


def _article(source: Record, text: str, subject: str) -> str:
    published = f", {source['published_at']}" if source.get("published_at") else ""
    return (
        f"The investigation is about: {subject}\n\n"
        f"Article: {source.get('title')} ({source.get('publisher') or 'unknown publisher'}{published})\n\n"
        f"<article>\n{text}\n</article>"
    )


def _squash(text: str) -> str:
    """For checking a quote against a text: case, diacritics, quote marks and
    spacing are the things a faithful copy still gets wrong."""
    return re.sub(r"\s+", " ", re.sub(r"[\"'„”“«»‘’`]", "", fold(text))).strip()
