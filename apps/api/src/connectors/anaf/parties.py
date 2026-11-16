"""Reading the party names of court files.

The portal records a party the way the court clerk typed it, representation
and all:

    MUNICIPIUL BRAŞOV, PRIN PRIMAR GEORGE SCRIPCARU
    SCRIPCARU GEORGE CU DOM.PROCESUAL ALES LA AVOCAT VLADIMIR CIOLACU
    SC ASP AGREGATE SRL, J08/3239/2008, CUI 24906002 PRIN REPREZENTANT LEGAL POP CĂLIN SILVIU

Taken as one name, the first reads as a person called "Municipiul Braşov prin
primar George Scripcaru". Split, it says two things: the city is the party,
and George Scripcaru represents it as mayor.
"""

import re
from dataclasses import dataclass

from connectors.common.text import clean_text

_FLAGS = re.IGNORECASE | re.DOTALL

# "X prin Y", "X, reprezentat de Y". The dot covers "S.A.PRIN ...".
_REPRESENTED = re.compile(
    r"^(?P<party>.+?)(?:[\s,]+|(?<=\.))(?:prin|reprezentat[ăa]?\s+(?:de|prin))\s+(?P<rep>.+)$",
    _FLAGS,
)
# "X cu domiciliul procesual ales la avocat Y": served at the lawyer's office.
_CHOSEN_ADDRESS = re.compile(
    r"^(?P<party>.+?)[\s,]+cu\s+dom(?:iciliul|\.)?\s*procesual\s+ales\s+(?:la|[iî]n)\s+(?P<rep>.+)$",
    _FLAGS,
)
_SEAT = re.compile(r"[\s,]+cu\s+(?:sediul|domiciliul)\b.*$", _FLAGS)
_NESTED = re.compile(r"[\s,]+(?:prin|reprezentat[ăa]?)\b.*$", _FLAGS)

_TRADE_REGISTER = re.compile(r"\bJ\s?\d{1,2}/\d+/\d{4}\b", re.IGNORECASE)
_CUI = re.compile(r"\b(?:CUI|CIF|C\.U\.I\.?)\s*:?\s*(?:RO)?\s*(\d{2,10})\b", re.IGNORECASE)

# In what capacity someone represents a party, when the clerk said so.
_ROLE = re.compile(
    r"^(?P<role>"
    r"primar(?:ul)?|av(?:ocat)?\.?|cabinet(?:\s+de)?\s+avocat(?:ur[ăa])?|"
    r"lichid(?:ator(?:ul)?)?\.?(?:\s+jud\w*\.?)?|"
    r"administrator(?:ul)?(?:\s+(?:judiciar|special|unic))?|"
    r"reprezentant(?:ul)?(?:\s+(?:legal|conven[țţt]ional))?|"
    r"c\.?i\.?i\.?|director(?:ul)?(?:\s+general)?|pre[sșş]edinte(?:le)?|"
    r"mandatar(?:ul)?|curator(?:ul)?|tutore(?:le)?"
    r")(?:\s+|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Party:
    name: str
    cui: str | None = None
    # Who acts for the party in the file, and in what capacity ("primar").
    representative: str | None = None
    role: str = ""


def split_party(raw: str) -> Party:
    """Separate the party from its identifiers and from whoever represents it.

    Conservative: when nothing is recognised, the name comes back as it was.
    """
    text = clean_text(raw)
    party, rep = text, ""

    for pattern in (_CHOSEN_ADDRESS, _REPRESENTED):
        found = pattern.match(text)
        if found:
            party, rep = found["party"], found["rep"]
            break

    cui = _CUI.search(party)
    party = _tidy(_SEAT.sub("", party))
    if not party:  # e.g. the whole string was "prin ..."
        return Party(name=text)

    role = ""
    rep = _NESTED.sub("", rep)  # "lichidator X prin reprezentant legal Y": keep X
    found = _ROLE.match(rep)
    if found:
        role, rep = found["role"].rstrip(".").lower(), rep[found.end() :]
    rep = _tidy(rep)

    return Party(
        name=party,
        cui=cui.group(1) if cui else None,
        representative=rep if len(rep) > 2 else None,
        role=role or ("reprezentant" if len(rep) > 2 else ""),
    )


def _tidy(name: str) -> str:
    """Drop registry identifiers, quotes and the punctuation they leave behind."""
    name = _CUI.sub("", _TRADE_REGISTER.sub("", name))
    name = re.sub(r"[\"„”“]", "", name)
    name = re.sub(r"(?:\s*,)+\s*$", "", re.sub(r"\s*,(?:\s*,)+", ",", name))
    return clean_text(name).strip(" ,-")
