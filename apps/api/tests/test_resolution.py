from agents.resolution import name_key, remap_claims, resolve_entities


def entity(id: str, type: str, *aliases: str, **attributes: object) -> dict:
    return {"id": id, "type": type, "description": "", "aliases": list(aliases), "attributes": attributes}


def test_name_key_ignores_order_diacritics_and_legal_form() -> None:
    assert name_key("POPESCU ION", "Person") == name_key("Ion Popescu", "Person")
    assert name_key("S.C. Dedeman S.R.L.", "Organization") == name_key("DEDEMAN SRL", "Organization")
    assert name_key("Ștefan", "Person") == "stefan"


def test_same_named_mentions_merge_into_the_richest_record() -> None:
    entities = {
        e["id"]: e
        for e in [
            entity("seed", "Unknown", "acme"),
            entity("org-cui", "Organization", "ACME SRL", cui="123"),
            entity("org-name", "Organization", "S.C. Acme S.R.L.", court="Bacau"),
            entity("p1", "Person", "POPESCU ION"),
            entity("p2", "Person", "Ion Popescu", role="director"),
            entity("p3", "Person", "Maria Popescu"),
            entity("doc", "Document", "Acme"),  # documents are never merged by name
        ]
    }

    result = resolve_entities(entities, "seed", "Acme")

    # The record with a CUI survives; the placeholder seed folds into it.
    assert result.merged == {"org-name": "org-cui", "p1": "p2", "seed": "org-cui"}
    assert result.seed_id == "org-cui"
    org = result.entities["org-cui"]
    assert org["aliases"] == ["ACME SRL", "S.C. Acme S.R.L.", "acme"]
    assert org["attributes"] == {"cui": "123", "court": "Bacau"}
    assert set(result.entities) == {"org-cui", "p2"}


def test_seed_stays_when_nothing_matches() -> None:
    entities = {"seed": entity("seed", "Unknown", "nobody"), "p": entity("p", "Person", "Ion Popescu")}
    result = resolve_entities(entities, "seed", "nobody")
    assert result.merged == {} and result.seed_id == "seed"


def test_remap_claims_follows_merges() -> None:
    claims = {
        "c1": {"id": "c1", "subject_ids": ["p1"], "reference_ids": ["org-name"]},
        "c2": {"id": "c2", "subject_ids": ["p3"], "reference_ids": []},
    }
    changed = remap_claims(claims, {"p1": "p2", "org-name": "org-cui"})
    assert changed == {"c1": {"id": "c1", "subject_ids": ["p2"], "reference_ids": ["org-cui"]}}
