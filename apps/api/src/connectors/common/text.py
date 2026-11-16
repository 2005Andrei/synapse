"""Text helpers shared by every scraper (previously copy-pasted into each one)."""

import re
import unicodedata
from email.utils import parsedate_to_datetime
from html import unescape

from models.types import EntityType

MONTHS = {
    "ianuarie": "01", "ian": "01", "january": "01", "jan": "01",
    "februarie": "02", "feb": "02", "february": "02",
    "martie": "03", "mar": "03", "march": "03",
    "aprilie": "04", "apr": "04", "april": "04",
    "mai": "05", "may": "05",
    "iunie": "06", "iun": "06", "june": "06", "jun": "06",
    "iulie": "07", "iul": "07", "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "septembrie": "09", "sep": "09", "sept": "09", "september": "09",
    "octombrie": "10", "oct": "10", "october": "10",
    "noiembrie": "11", "nov": "11", "november": "11",
    "decembrie": "12", "dec": "12", "december": "12",
}  # fmt: skip

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2})?")
_NUMERIC_DATE = re.compile(
    r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?:\D+(\d{1,2}):(\d{2}))?"
)
_NAMED_MONTH_DATE = re.compile(
    r"(\d{1,2})\s+([A-Za-zĂÂÎȘȚăâîșț]+)\s+(\d{4})(?:\D+(\d{1,2}):(\d{2}))?",
    flags=re.IGNORECASE,
)


def clean_text(text: str | None) -> str:
    text = " ".join(unescape(text or "").split())
    return re.sub(r"\s+([.,!?;:])", r"\1", text).strip()


def fold(text: str | None) -> str:
    """Lowercase, no diacritics, single spaces: for comparing, never for display."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return clean_text(text).lower()


def query_matches(text: str, query: str) -> bool:
    """True if `text` contains the query, or every significant word of it."""
    folded_text = fold(text)
    folded_query = fold(query)

    if folded_query in folded_text:
        return True

    words = [word for word in re.split(r"\W+", folded_query) if len(word) > 2]
    return bool(words) and all(word in folded_text for word in words)


def normalize_date(value: str | None) -> str | None:
    """Best-effort parse of the date formats seen on Romanian sites.

    Returns "YYYY-MM-DD" or "YYYY-MM-DD HH:MM", or None when nothing parses.
    """
    value = clean_text(value)
    value = value.replace("Publicat:", "").replace("Actualizat:", "").strip()

    if not value:
        return None

    iso_match = _ISO_DATE.search(value)
    if iso_match:
        return iso_match.group(0).replace("T", " ")[:16]

    numeric_match = _NUMERIC_DATE.search(value)
    if numeric_match:
        day, month, year, hour, minute = numeric_match.groups()
        return _format_date(year, f"{int(month):02d}", day, hour, minute)

    named_match = _NAMED_MONTH_DATE.search(value)
    if named_match:
        day, month_name, year, hour, minute = named_match.groups()
        month = MONTHS.get(month_name.lower())
        if month:
            return _format_date(year, month, day, hour, minute)

    try:
        return parsedate_to_datetime(value).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def _format_date(
    year: str, month: str, day: str, hour: str | None, minute: str | None
) -> str:
    date = f"{year}-{month}-{int(day):02d}"
    if hour and minute:
        return f"{date} {int(hour):02d}:{minute}"
    return date


# Words that give away an organisation in Romanian registry / court party names.
_ORG_WORDS = frozenset(
    """
    srl sa sca snc scs srl-d pfa ra sc ong
    primaria consiliul ministerul directia asociatia fundatia banca compania
    societatea universitatea spitalul inspectoratul agentia tribunalul parchetul
    judecatoria curtea statul orasul municipiul comuna judetul casa regia oficiul
    administratia serviciul cabinet cabinetul institutul autoritatea garda politia
    uniunea federatia sindicatul partidul clubul biroul camera comisia scoala
    liceul colegiul academia institutia unitatea grup group holding company ltd
    gmbh limited inc llc bank leasing asigurari
    sprl sparl ipurl scpa scp sca ifn insolvency insolventa cii
    """.split()
)


def guess_entity_type(name: str) -> EntityType:
    """Person or organisation, judged from the name alone. A hint, not a fact."""
    words = set(re.split(r"[^a-z-]+", fold(name).replace(".", "")))
    return EntityType.ORGANIZATION if words & _ORG_WORDS else EntityType.PERSON
