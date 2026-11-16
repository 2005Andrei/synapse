import pytest

from connectors.common.text import (
    clean_text,
    fold,
    guess_entity_type,
    normalize_date,
    query_matches,
)
from models.types import EntityType


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024-03-12T09:30:00+02:00", "2024-03-12 09:30"),
        ("2024-03-12", "2024-03-12"),
        ("Publicat: 12.03.2024, 9:05", "2024-03-12 09:05"),
        ("12/3/2024", "2024-03-12"),
        ("12 martie 2024, 14:05", "2024-03-12 14:05"),
        ("Actualizat: 5 Dec 2023", "2023-12-05"),
        ("Tue, 12 Mar 2024 09:30:00 GMT", "2024-03-12 09:30"),
        ("ieri", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_date(raw: str | None, expected: str | None) -> None:
    assert normalize_date(raw) == expected


def test_clean_text_collapses_whitespace_and_entities() -> None:
    assert clean_text("  A&amp;B \n are   here .") == "A&B are here."


def test_fold_strips_diacritics() -> None:
    assert fold("Științifică  ȚĂRĂ") == "stiintifica tara"


def test_query_matches_ignores_diacritics_and_word_order() -> None:
    assert query_matches("Firma lui Popescu, condusă de Ion", "ion popescu")
    assert query_matches("Știri despre Brașov", "brasov")
    assert not query_matches("Firma lui Popescu", "ion popescu")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("SC DEDEMAN SRL", EntityType.ORGANIZATION),
        ("S.C. ROMBET S.A.", EntityType.ORGANIZATION),
        ("PRIMĂRIA MUNICIPIULUI BACĂU", EntityType.ORGANIZATION),
        ("POPESCU ION", EntityType.PERSON),
        ("Sara Ionescu", EntityType.PERSON),
    ],
)
def test_guess_entity_type(name: str, expected: EntityType) -> None:
    assert guess_entity_type(name) == expected
