"""Build the ONRC index from data.gov.ro:  python -m connectors.onrc.build

Streams the two CSV files (about 1 GB together) straight into SQLite, so no
raw copy is kept on disk. `--only CUI,CUI` keeps just those companies: a
sample index for a machine without the space for the full one.
"""

import argparse
import sqlite3
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx

from connectors.common.text import clean_text
from connectors.onrc.index import INDEXES, SCHEMA, firm_fold, person_key
from core.config import get_settings

CATALOGUE = "https://data.gov.ro/api/3/action/package_search"
PUBLISHER = "Oficiul Național al Registrului Comerțului"
FIRMS, REPRESENTATIVES = "od_firme.csv", "od_reprezentanti_legali.csv"
_BATCH = 20_000


def latest_dataset(http: httpx.Client) -> dict:
    """The newest "Firme înregistrate la Registrul Comerțului" release."""
    found = http.get(
        CATALOGUE,
        params={"q": "firme inregistrate registrul comertului", "rows": 10, "sort": "metadata_modified desc"},
    ).json()["result"]["results"]
    for dataset in found:
        files = {resource["url"].rsplit("/", 1)[-1].lower(): resource["url"] for resource in dataset["resources"]}
        if (dataset.get("organization") or {}).get("title") == PUBLISHER and {FIRMS, REPRESENTATIVES} <= set(files):
            return {"name": dataset["name"], "title": dataset["title"], "files": files}
    raise SystemExit("no ONRC release with both files found on data.gov.ro")


def rows(http: httpx.Client, url: str) -> Iterator[dict[str, str]]:
    """The file's records. Fields are separated by "^" and never quoted (a
    company name may itself contain quotation marks), so the csv module is not used."""
    with http.stream("GET", url) as response:
        response.raise_for_status()
        lines = response.iter_lines()
        header = next(lines).lstrip("﻿").split("^")
        for line in lines:
            values = line.split("^")
            if len(values) == len(header):
                yield dict(zip(header, values))


def iso_date(value: str) -> str | None:
    """"13/02/1991" -> "1991-02-13"."""
    day, _, rest = value.strip().partition("/")
    month, _, year = rest.partition("/")
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}" if year.isdigit() and month.isdigit() and day.isdigit() else None


def _place(*parts: str) -> str | None:
    return ", ".join(clean_text(part) for part in parts if clean_text(part)) or None


def firm_row(row: dict[str, str]) -> tuple:
    cui = row["CUI"].strip()
    name = clean_text(row["DENUMIRE"])
    street = " ".join(part for part in (row["ADR_DEN_STRADA"].strip(), row["ADR_NR_STRADA"].strip()) if part)
    return (
        row["COD_INMATRICULARE"].strip(),
        cui if cui.isdigit() and cui != "0" else None,
        name,
        firm_fold(name),
        row["FORMA_JURIDICA"].strip() or None,
        row["ADR_JUDET"].strip() or None,
        row["ADR_LOCALITATE"].strip() or None,
        _place(street, row["ADR_LOCALITATE"], row["ADR_JUDET"]),
        iso_date(row["DATA_INMATRICULARE"]),
    )


def rep_row(row: dict[str, str]) -> tuple:
    name = clean_text(row["PERSOANA_IMPUTERNICITA"])
    return (
        row["COD_INMATRICULARE"].strip(),
        name,
        person_key(name),
        row["CALITATE"].strip() or None,
        iso_date(row["DATA_NASTERE"]),
        _place(row["LOCALITATE_NASTERE"], row["JUDET_NASTERE"], row["TARA_NASTERE"]),
        _place(row["LOCALITATE"], row["JUDET"], row["TARA"]),
    )


def build(target: Path, only: set[str] | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".partial")
    partial.unlink(missing_ok=True)
    db = sqlite3.connect(partial)
    db.executescript("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF;" + SCHEMA)

    def load(http: httpx.Client, url: str, sql: str, convert, keep) -> int:
        kept, batch, started = 0, [], time.monotonic()
        for seen, row in enumerate(rows(http, url), start=1):
            if keep(row):
                batch.append(convert(row))
            if len(batch) >= _BATCH or (only and batch):
                db.executemany(sql, batch)
                kept += len(batch)
                batch.clear()
            if seen % 500_000 == 0:
                print(f"  {seen:>10,} rows read, {kept:,} kept, {time.monotonic() - started:.0f}s", file=sys.stderr)
        db.executemany(sql, batch)
        db.commit()
        return kept + len(batch)

    with httpx.Client(timeout=httpx.Timeout(60, read=120), follow_redirects=True) as http:
        dataset = latest_dataset(http)
        print(f"{dataset['title']}", file=sys.stderr)

        firms = load(
            http, dataset["files"][FIRMS], "INSERT OR IGNORE INTO firms VALUES (?,?,?,?,?,?,?,?,?)", firm_row,
            (lambda row: row["CUI"].strip() in only) if only else (lambda row: True),
        )
        wanted = {reg for (reg,) in db.execute("SELECT reg FROM firms")} if only else None
        reps = load(
            http, dataset["files"][REPRESENTATIVES], "INSERT INTO reps VALUES (?,?,?,?,?,?,?)", rep_row,
            (lambda row: row["COD_INMATRICULARE"].strip() in wanted) if wanted is not None else (lambda row: True),
        )

    db.executescript(INDEXES)
    db.executemany(
        "INSERT INTO meta VALUES (?, ?)",
        {
            "dataset": dataset["name"],
            "title": dataset["title"],
            "url": f"https://data.gov.ro/dataset/{dataset['name']}",
            "sample": ",".join(sorted(only)) if only else "",
        }.items(),
    )
    db.commit()
    db.close()
    partial.replace(target)
    print(f"{firms:,} companies, {reps:,} representatives -> {target} ({target.stat().st_size / 1e6:.0f} MB)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", type=Path, default=Path(get_settings().onrc_db))
    parser.add_argument("--only", help="comma-separated CUIs: build a sample index with just these companies")
    args = parser.parse_args()
    build(args.db, {cui.strip() for cui in args.only.split(",") if cui.strip()} if args.only else None)


if __name__ == "__main__":
    main()
