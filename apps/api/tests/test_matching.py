import pytest
from test_pipeline import run_pipeline

from agents.matching import EXACT, SIMILAR, match_name, name_words
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from models.ids import document_id, mention_id
from models.types import EntityType, Predicate, SourceType


def kind(name: str, query: str, type: str = "Person") -> str | None:
    match = match_name(name, query, type)
    return match.kind if match else None


def test_name_words_ignore_order_case_diacritics_and_legal_form() -> None:
    assert name_words("Popescu Ion-Marian", "Person") == {"popescu", "ion", "marian"}
    assert name_words("S.C. Dedeman S.R.L.", "Organization") == {"dedeman"}
    assert name_words("Ștefan A. Țiriac", "Person") == {"stefan", "tiriac"}


def test_only_the_same_words_are_an_exact_match() -> None:
    assert kind("SCRIPCARU GEORGE", "George Scripcaru") == EXACT
    assert kind("S.C. DEDEMAN S.R.L.", "Dedeman", "Organization") == EXACT

    # One more name, one fewer, or another spelling: similar, never exact.
    assert match_name("SCRIPCARU GEORGE DANIEL", "George Scripcaru", "Person").note == "extra: DANIEL"
    assert match_name("Scripcaru George", "George Daniel Scripcaru", "Person").note == "missing: DANIEL"
    assert match_name("Scripcaru Gheorghe", "George Scripcaru", "Person").note == "spelling: george ≈ gheorghe"
    assert kind("SC DEDEMAN AUTOMOBILE SRL", "Dedeman", "Organization") == SIMILAR


def test_unrelated_names_do_not_match() -> None:
    assert kind("Maria Ionescu", "George Scripcaru") is None
    assert kind("George Enescu", "George Scripcaru") is None  # a shared first name is not enough
    assert kind("Scripcaru", "George Scripcaru") is None  # nor is the family name alone
    assert kind("", "George Scripcaru") is None


class Court(BaseScraper):
    """Three people in three cases: the one searched for, and two near misses."""

    name = "court"
    label = "Court"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.COURT_DOCUMENT

    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        for number, party in enumerate(("POPESCU ION", "POPESCU ION MARIAN", "Popescu Ioan"), 1):
            case = out.entity(document_id(f"case:{number}"), EntityType.DOCUMENT, f"Case {number}")
            person = out.entity(mention_id(self.name, EntityType.PERSON, party), EntityType.PERSON, party)
            out.claim(person, Predicate.DEFENDANT_IN, f"{party} in case {number}", case)


async def test_similar_names_stay_separate_and_are_linked_as_hypotheses(
    fake_scrapers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(fake_scrapers, "court", Court)
    final, events = await run_pipeline("Ion Popescu", ["court"])
    entities, claims = final["entities"], final["claims"]

    people = {e["aliases"][0]: e for e in entities.values() if e["type"] == "Person"}
    assert set(people) == {"POPESCU ION", "POPESCU ION MARIAN", "Popescu Ioan"}  # nobody merged

    # The exact match became the subject of the search...
    subject = entities[final["seed_id"]]
    assert subject is people["POPESCU ION"] and subject["attributes"]["match"] == "exact"
    # ...the others are flagged, with what differs.
    assert people["POPESCU ION MARIAN"]["attributes"] == {
        "match": "similar", "match_note": "extra: MARIAN", "match_of": final["seed_id"]
    }
    assert people["Popescu Ioan"]["attributes"]["match_note"] == "spelling: ion ≈ ioan"

    links = [c for c in claims.values() if c["predicate"] == "Similar_Name"]
    assert len(links) == 2
    assert all(c["type"] == "Hypothesis" and c["reference_ids"] == [final["seed_id"]] for c in links)

    # Each person keeps their own case: nothing was re-attributed.
    cases = {c["subject_ids"][0]: c["reference_ids"][0] for c in claims.values() if c["predicate"] == "Defendant_In"}
    assert len(set(cases.values())) == 3

    # The frontend got the flags, and resemblance does not make anyone a lead twice over.
    (patch,) = [d for t, d in events if t == "graph.patch" and d["origin"] == "resolve"]
    assert sum("match" in e["attributes"] for e in patch["entities"]) == 3
    assert all(lead["score"] == 1 for lead in final["leads"])
