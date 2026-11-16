import pytest

from connectors.anaf.parties import Party, split_party

CASES = {
    "MUNICIPIUL BRAŞOV, PRIN PRIMAR GEORGE SCRIPCARU": Party(
        "MUNICIPIUL BRAŞOV", None, "GEORGE SCRIPCARU", "primar"
    ),
    "SCRIPCARU GEORGE CU DOM.PROCESUAL ALES LA AVOCAT VLADIMIR CIOLACU": Party(
        "SCRIPCARU GEORGE", None, "VLADIMIR CIOLACU", "avocat"
    ),
    "SCRIPCARU GEORGE prin Av. Ciolacu Vladimir": Party(
        "SCRIPCARU GEORGE", None, "Ciolacu Vladimir", "av"
    ),
    "SC ASP AGREGATE SRL, J08/3239/2008, CUI 24906002 PRIN REPREZENTANT LEGAL POP CĂLIN SILVIU": Party(
        "SC ASP AGREGATE SRL", "24906002", "POP CĂLIN SILVIU", "reprezentant legal"
    ),
    "S.C. ROMBET S.A.PRIN LICHID. JUD. SIEERA QUADRANT SPRL": Party(
        "S.C. ROMBET S.A.", None, "SIEERA QUADRANT SPRL", "lichid. jud"
    ),
    "SC ASP TRANSPORT SRL, PRIN CII BARBU TUDORIŢA": Party(
        "SC ASP TRANSPORT SRL", None, "BARBU TUDORIŢA", "cii"
    ),
    # A liquidator that is itself represented: keep the liquidator.
    "SC CET BRAŞOV SA PRIN LICHIDATOR JUDICAR INFO DIP INSOLVENCY SPRL PRIN REPREZENTANT LEGAL": Party(
        "SC CET BRAŞOV SA", None, "INFO DIP INSOLVENCY SPRL", "lichidator judicar"
    ),
    'SC SOPMET SA, PRIN REPREZENTANT CONVENŢIONAL "LETITIA & PERETIANU SPARL", J40/5156/1991': Party(
        "SC SOPMET SA", None, "LETITIA & PERETIANU SPARL", "reprezentant convenţional"
    ),
    # Nothing to split: untouched.
    "SCRIPCARU GEORGE DANIEL": Party("SCRIPCARU GEORGE DANIEL"),
    "S.C. DEDEMAN S.R.L.": Party("S.C. DEDEMAN S.R.L."),
    "PRINCIPAL CONSTRUCT SRL": Party("PRINCIPAL CONSTRUCT SRL"),  # "prin" inside a word
}


@pytest.mark.parametrize("raw", CASES)
def test_split_party(raw: str) -> None:
    assert split_party(raw) == CASES[raw]
