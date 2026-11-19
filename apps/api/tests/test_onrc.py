import sqlite3
from pathlib import Path

import pytest

from connectors.common.cui import resolve_cui
from connectors.onrc import index as index_module
from connectors.onrc.build import firm_row, iso_date, rep_row
from connectors.onrc.index import INDEXES, SCHEMA, OnrcIndex, firm_fold, person_key
from connectors.onrc.onrc import OnrcScraper
from models.ids import company_id

FIRM = dict(zip(
    "DENUMIRE^CUI^COD_INMATRICULARE^DATA_INMATRICULARE^EUID^FORMA_JURIDICA^ADR_TARA^ADR_JUDET^ADR_LOCALITATE^ADR_DEN_STRADA^ADR_NR_STRADA".split("^"),
    'ACME "IMPEX" SRL^123^J40/1/1991^13/02/1991^ROONRC.J40/1/1991^SRL^România^Bucureşti^Bucureşti Sectorul 6^Str. CEAHLAU^16'.split("^"),
))  # fmt: skip
REP_COLUMNS = "COD_INMATRICULARE^PERSOANA_IMPUTERNICITA^CALITATE^DATA_NASTERE^LOCALITATE_NASTERE^JUDET_NASTERE^TARA_NASTERE^LOCALITATE^JUDET^TARA".split("^")
REPS = [
    "J40/1/1991^POPESCU ION^administrator^22/06/1966^Loc. Fălticeni^Suceava^România^^^",
    "J40/1/1991^FOCUS INSOLV IPURL^lichidator^^^^^Bucureşti Sectorul 5^Bucureşti^România",
    "J40/2/1999^Popescu Ion^administrator^01/01/1990^^^România^^^",  # a namesake, at another company
]


@pytest.fixture
def index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> OnrcIndex:
    path = tmp_path / "onrc.sqlite"
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.execute("INSERT INTO firms VALUES (?,?,?,?,?,?,?,?,?)", firm_row(FIRM))
    db.execute("INSERT INTO firms VALUES (?,?,?,?,?,?,?,?,?)", firm_row({**FIRM, "DENUMIRE": "BETA SA", "CUI": "456", "COD_INMATRICULARE": "J40/2/1999"}))
    db.executemany("INSERT INTO reps VALUES (?,?,?,?,?,?,?)", [rep_row(dict(zip(REP_COLUMNS, line.split("^")))) for line in REPS])
    db.executescript(INDEXES)
    db.execute("INSERT INTO meta VALUES ('url', 'https://data.gov.ro/dataset/firme-test')")
    db.commit()
    db.close()
    built = OnrcIndex(path)
    monkeypatch.setattr(index_module, "get_index", lambda: built)
    monkeypatch.setattr("connectors.onrc.onrc.get_index", lambda: built)
    return built


def test_rows_are_normalised() -> None:
    assert iso_date("13/02/1991") == "1991-02-13" and iso_date("") is None
    assert firm_fold('S.C. ACME "IMPEX" S.R.L.') == "acme impex"
    assert person_key("SAVA Catrinel-Ionela") == person_key("catrinel ionela sava") == "catrinel ionela sava"
    assert firm_row({**FIRM, "CUI": "0"})[1] is None  # the register's "no fiscal code"


def test_index_lookups(index: OnrcIndex) -> None:
    assert index.by_cui("123").name == 'ACME "IMPEX" SRL'
    assert [firm.cui for firm in index.search_firms("acme impex")] == ["123"]
    assert [firm.cui for firm in index.search_firms("Acme")] == ["123"]  # no exact match: by prefix
    assert [(role.reg, role.born) for role in index.roles_of("Ion Popescu")] == [
        ("J40/1/1991", "1966-06-22"), ("J40/2/1999", "1990-01-01"),
    ]  # fmt: skip
    assert index.roles_of("Popescu") == []
    assert resolve_cui(None, "ACME IMPEX SRL") == "123"  # company name -> CUI without a third party


def test_company_search_lists_who_runs_it(index: OnrcIndex) -> None:
    with OnrcScraper() as scraper:
        result = scraper.search("123")

    by_name = {entity.aliases[0]: entity for entity in result.entities}
    assert by_name['ACME "IMPEX" SRL'].id == company_id("123")
    man = by_name["POPESCU ION"]
    assert (man.type, man.attributes["date_of_birth"]) == ("Person", "1966-06-22")
    assert by_name["FOCUS INSOLV IPURL"].type == "Organization"
    roles = {(claim.subject_ids[0], str(claim.predicate.value)) for claim in result.claims}
    assert roles == {(man.id, "Director_Of"), (by_name["FOCUS INSOLV IPURL"].id, "Represents")}


def test_person_search_finds_their_companies_and_keeps_namesakes_apart(index: OnrcIndex) -> None:
    with OnrcScraper() as scraper:
        result = scraper.search("Ion Popescu")

    people = [entity for entity in result.entities if entity.type == "Person"]
    assert sorted(person.attributes["date_of_birth"] for person in people) == ["1966-06-22", "1990-01-01"]
    assert {entity.aliases[0] for entity in result.entities if entity.type == "Organization"} == {'ACME "IMPEX" SRL', "BETA SA"}


def test_without_an_index_the_scraper_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("connectors.onrc.onrc.get_index", lambda: None)
    with OnrcScraper() as scraper:
        result = scraper.search("123")
    assert result.entities == [] and "just onrc-import" in result.metadata["notes"][0]
