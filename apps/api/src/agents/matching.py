"""How closely a name matches what the user searched for.

Sources match loosely: a search for "George Scripcaru" also returns
"SCRIPCARU GEORGE DANIEL" and "Scripcaru Gheorghe". Those may be the same
person or three different ones, and nothing in a name can settle that. So:

  - only an *exact* match (same words, any order) is treated as the subject
    of the search and merged with it;
  - a *similar* name stays a separate entity, flagged, with a note saying what
    differs, and is linked to the subject as a hypothesis, never as a fact;
  - everything else is simply another entity in the results.

Entity resolution (`agents.resolution`) merges on exact names only; this
module is what labels the near misses so the results can be divided by
identity instead of being read as one person.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from connectors.common.text import fold
from models.types import EntityType

EXACT = "exact"
SIMILAR = "similar"

LEGAL_FORMS = frozenset({"sc", "srl", "sa", "sca", "snc", "scs", "pfa", "ra", "srl-d", "srld"})
# Two words this alike count as spelling variants: george/gheorghe, ion/ioan.
_SPELLING_RATIO = 0.84


@dataclass(frozen=True)
class NameMatch:
    kind: str  # EXACT | SIMILAR
    note: str = ""  # what differs, for a similar name


def name_words(name: str, entity_type: str) -> frozenset[str]:
    """The words that identify a name: no diacritics, case, punctuation,
    initials or (for companies) legal form. "Popescu Ion-Marian" and
    "POPESCU ION MARIAN" give the same set."""
    words = re.split(r"[^a-z0-9]+", fold(name).replace(".", ""))
    if entity_type == EntityType.ORGANIZATION.value:
        words = [word for word in words if word not in LEGAL_FORMS]
    return frozenset(word for word in words if len(word) > 1)


def match_name(name: str, query: str, entity_type: str) -> NameMatch | None:
    """Compare an entity's name with the searched one. None: unrelated."""
    found, wanted = name_words(name, entity_type), name_words(query, entity_type)
    if not found or not wanted:
        return None
    if found == wanted:
        return NameMatch(EXACT)

    extra, missing = found - wanted, wanted - found
    if not missing:
        return NameMatch(SIMILAR, f"extra: {_join(extra)}")
    if not extra and len(found) > 1:
        return NameMatch(SIMILAR, f"missing: {_join(missing)}")

    # Same words but for spelling? Every searched word must have a counterpart.
    variants = []
    for word in sorted(missing):
        twin = max(extra, key=lambda other: _ratio(word, other), default=None)
        if twin is None or _ratio(word, twin) < _SPELLING_RATIO:
            return None
        variants.append(f"{word} ≈ {twin}")
        extra = extra - {twin}
    note = f"spelling: {', '.join(variants)}"
    return NameMatch(SIMILAR, f"{note}; extra: {_join(extra)}" if extra else note)


def best_match(names: list[str], query: str, entity_type: str) -> NameMatch | None:
    """An entity can carry several aliases; the closest one counts."""
    matches = [m for name in names if (m := match_name(name, query, entity_type))]
    return min(matches, key=lambda m: m.kind != EXACT, default=None)


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _join(words: frozenset[str] | set[str]) -> str:
    return " ".join(sorted(word.upper() for word in words))
