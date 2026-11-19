"""A local index of the trade register (ONRC), built from its open data.

ONRC publishes the whole register on data.gov.ro every few weeks (CC BY 4.0):
every company with its fiscal code, and every legal representative with their
role and date of birth. That is where third-party lookup services get company
search and administrators from. Built once with `just onrc-import`, the index
answers what ANAF's own services cannot: company name -> CUI, who runs a
company, and which companies a person runs.

It is a single SQLite file, read-only at run time. No file, no index: callers
check `available` and say so instead of failing.
"""

import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from connectors.common.text import fold
from core.config import get_settings

SCHEMA = """
CREATE TABLE firms (
    reg TEXT PRIMARY KEY,   -- J40/1116/1991: the key of every other ONRC file
    cui TEXT,               -- NULL when the register has none
    name TEXT NOT NULL,
    name_fold TEXT NOT NULL,-- folded, legal form removed: "dedeman"
    form TEXT, county TEXT, locality TEXT, address TEXT, registered TEXT
) WITHOUT ROWID;
CREATE TABLE reps (
    reg TEXT NOT NULL,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL, -- folded words, sorted: "ion popescu"
    role TEXT, born TEXT, birth_place TEXT, residence TEXT
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""
# Created after the bulk load: much faster than maintaining them row by row.
INDEXES = """
CREATE INDEX firms_cui ON firms(cui);
CREATE INDEX firms_name ON firms(name_fold);
CREATE INDEX reps_reg ON reps(reg);
CREATE INDEX reps_name ON reps(name_key);
"""

_LEGAL_FORMS = {"sc", "srl", "sa", "sca", "snc", "scs", "pfa", "ra", "srl-d", "srld", "ii", "if", "pf"}


def firm_fold(name: str) -> str:
    words = re.split(r"[^a-z0-9]+", fold(name).replace(".", ""))
    return " ".join(word for word in words if word and word not in _LEGAL_FORMS)


def person_key(name: str) -> str:
    """Order-free key of a person's name; hyphenated given names count as two words."""
    return " ".join(sorted(word for word in re.split(r"[^a-z0-9]+", fold(name).replace(".", "")) if len(word) > 1))


@dataclass(frozen=True)
class Firm:
    reg: str
    cui: str | None
    name: str
    form: str | None
    county: str | None
    locality: str | None
    address: str | None
    registered: str | None


@dataclass(frozen=True)
class Representative:
    reg: str
    name: str
    role: str
    born: str | None  # YYYY-MM-DD
    birth_place: str | None
    residence: str | None


_FIRM_COLUMNS = "reg, cui, name, form, county, locality, address, registered"
_REP_COLUMNS = "reg, name, role, born, birth_place, residence"


class OnrcIndex:
    def __init__(self, path: Path):
        self.path = path
        # Read-only and immutable: safe to share between scraper threads.
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)

    def meta(self) -> dict[str, str]:
        return dict(self.db.execute("SELECT key, value FROM meta"))

    def by_cui(self, cui: str) -> Firm | None:
        row = self.db.execute(f"SELECT {_FIRM_COLUMNS} FROM firms WHERE cui = ? LIMIT 1", (cui,)).fetchone()
        return Firm(*row) if row else None

    def by_reg(self, reg: str) -> Firm | None:
        row = self.db.execute(f"SELECT {_FIRM_COLUMNS} FROM firms WHERE reg = ?", (reg,)).fetchone()
        return Firm(*row) if row else None

    def search_firms(self, name: str, limit: int = 5) -> list[Firm]:
        """Companies called exactly `name` (legal form aside); if there are
        none, the ones whose name starts with it."""
        key = firm_fold(name)
        if not key:
            return []
        rows = self.db.execute(
            f"SELECT {_FIRM_COLUMNS} FROM firms WHERE name_fold = ? ORDER BY cui IS NULL, registered LIMIT ?",
            (key, limit),
        ).fetchall()
        if not rows:
            rows = self.db.execute(
                f"SELECT {_FIRM_COLUMNS} FROM firms WHERE name_fold >= ? AND name_fold < ? "
                "ORDER BY cui IS NULL, length(name_fold) LIMIT ?",
                (key + " ", key + " ￿", limit),
            ).fetchall()
        return [Firm(*row) for row in rows]

    def representatives(self, reg: str) -> list[Representative]:
        rows = self.db.execute(f"SELECT {_REP_COLUMNS} FROM reps WHERE reg = ?", (reg,))
        return [Representative(*row) for row in rows]

    def roles_of(self, person: str, limit: int = 25) -> list[Representative]:
        """Every register entry of people called `person`, any word order."""
        key = person_key(person)
        if len(key.split()) < 2:  # a single word is not a person's name
            return []
        rows = self.db.execute(
            f"SELECT {_REP_COLUMNS} FROM reps WHERE name_key = ? ORDER BY born LIMIT ?", (key, limit)
        )
        return [Representative(*row) for row in rows]


@lru_cache
def get_index() -> OnrcIndex | None:
    """The index, or None while it has not been built (see `connectors.onrc.build`)."""
    path = Path(get_settings().onrc_db)
    return OnrcIndex(path) if path.is_file() else None
