from agents import leads as leads_module
from agents.nodes import discover as discover_node
from test_pipeline import run_pipeline


async def test_discovery_proposes_the_connected_entities_as_leads(fake_scrapers: dict) -> None:
    final, events = await run_pipeline("Acme", list(fake_scrapers))

    (lead,) = final["leads"]  # the director; the company itself is the subject
    director = final["entities"][lead["entity_id"]]
    assert {"POPESCU ION", "Ion Popescu"} == set(director["aliases"])  # registry + court, merged
    assert lead["query"] == director["aliases"][0]
    # Acme is a company and he runs it: an officer, senior enough to be searched right away.
    assert (lead["kind"], lead["role"], lead["by"], lead.get("follow")) == ("officer", "director", "role", True)

    (payload,) = [data for type, data in events if type == "agent.leads"]
    assert payload["leads"] == final["leads"]


class FakeModel:
    """Stands in for a chat model: picks one real candidate and one invented name."""

    def with_structured_output(self, schema: type) -> "FakeModel":
        self.schema = schema
        return self

    async def ainvoke(self, messages: list) -> object:
        self.prompt = messages[-1][1]
        return self.schema(
            leads=[
                {"query": "popescu, ion", "reason": "Director of the subject."},
                {"query": "Somebody Invented", "reason": "Not in the data."},
            ]
        )


async def test_model_picked_leads_are_limited_to_found_entities(
    fake_scrapers: dict, monkeypatch
) -> None:
    model = FakeModel()
    monkeypatch.setattr(discover_node, "get_chat_model", lambda: model)
    final, _ = await run_pipeline("Acme", list(fake_scrapers))

    (lead,) = await leads_module.llm_leads(model, final, 5)
    assert lead["by"] == "llm" and lead["reason"] == "Director of the subject."
    assert [lead["kind"] for lead in final["leads"]] == ["officer"]  # the same man, listed once
    # Matched to the found entity despite the model's spelling; the invented one is dropped.
    assert lead["query"] == final["entities"][lead["entity_id"]]["aliases"][0]
    assert lead["query"] in model.prompt and "Subject of the investigation: Acme" in model.prompt


async def test_model_failure_falls_back_to_the_heuristic(fake_scrapers: dict, monkeypatch) -> None:
    class Down:
        def with_structured_output(self, schema: type) -> "Down":
            raise RuntimeError("no credits")

    monkeypatch.setattr(discover_node, "get_chat_model", lambda: Down())
    final, events = await run_pipeline("Acme", list(fake_scrapers))

    assert [lead["by"] for lead in final["leads"]] == ["role"]
    assert any("Model call failed" in data.get("text", "") for _, data in events)
    assert leads_module.heuristic_leads({"entities": {}, "claims": {}}, 5) == []


def test_briefing_fits_a_small_context() -> None:
    """A local model gets the best-connected candidates and what room is left for the sources."""
    people = {f"p{n}": {"id": f"p{n}", "type": "Person", "aliases": [f"Person Number {n}"]} for n in range(12)}
    claims = {
        f"c{n}-{k}": {"id": f"c{n}-{k}", "type": "Relation", "subject_ids": [f"p{n}"], "reference_ids": ["seed"],
                      "claim_text": f"Person Number {n} did thing {k} " + "x" * 80}
        for n in range(12) for k in range(12 - n)  # p0 is the most connected
    }  # fmt: skip
    state = {
        "query": "ACME", "seed_id": "seed", "claims": claims,
        "entities": {"seed": {"id": "seed", "type": "Organization", "aliases": ["ACME"]}, **people},
        "sources": {"s": {"id": "s", "publisher": "Ziar", "title": "Titlu", "content": "y" * 400}},
    }  # fmt: skip

    whole = leads_module.briefing(state)
    cut = leads_module.briefing(state, max_chars=len(whole) // 2)

    assert "Person Number 11" in whole
    assert len(cut) <= len(whole) // 2
    assert "Person Number 0" in cut and "Person Number 11" not in cut  # the tail is what goes
    assert "[Ziar] Titlu" in cut  # and the sources keep some room
