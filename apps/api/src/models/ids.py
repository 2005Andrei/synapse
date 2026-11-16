"""Deterministic ids.

The same real-world record must get the same id on every run and from every
scraper that can identify it, otherwise the graph fills up with duplicates.
Ids are uuid5 hashes of a natural key.
"""

from uuid import UUID, uuid5

NAMESPACE = UUID("6f1c1d2e-5b0a-4c57-9d57-73796e617073")


def stable_id(*parts: object) -> UUID:
    return uuid5(NAMESPACE, "|".join(str(part).strip().lower() for part in parts))


def source_id(url: str) -> UUID:
    return stable_id("source", url)


def company_id(cui: str) -> UUID:
    """Companies are keyed by fiscal code, so every scraper agrees on the id."""
    return stable_id("entity", "cui", cui)


def document_id(key: str) -> UUID:
    """Documents are keyed by url / case number / registry id."""
    return stable_id("entity", "document", key)


def mention_id(scraper: str, entity_type: str, key: str) -> UUID:
    """An entity known only by name, as seen by one scraper.

    Scoped to the scraper on purpose: deciding that two same-named mentions are
    the same real person is entity resolution's job, not the scraper's.
    """
    return stable_id("entity", "mention", scraper, entity_type, key)


def claim_id(subject: object, predicate: object, reference: object = "") -> UUID:
    return stable_id("claim", subject, predicate, reference)
