from connectors.anaf import anaf as anaf_module
from connectors.anaf.anaf import AnafScraper
from models.ids import company_id


def test_company_carries_its_yearly_financials(monkeypatch) -> None:
    scraper = AnafScraper()
    monkeypatch.setattr(anaf_module, "resolve_cui", lambda http, query: "123")
    monkeypatch.setattr(scraper, "get_anaf_data", lambda cui: {"found": [{"date_generale": {"denumire": "ACME SRL"}}]})
    monkeypatch.setattr(scraper, "get_company", lambda cui: {})
    monkeypatch.setattr(
        scraper,
        "get_financials",
        lambda cui: [
            {"year": 2022, "revenue": 1000.0, "net_profit": 0, "net_loss": 250.0, "employees": 4},
            {"year": 2023, "revenue": 1500.0, "net_profit": 300.0, "net_loss": 0, "employees": 5},
        ],
    )

    with scraper:
        result = scraper.search("123")

    company = next(entity for entity in result.entities if entity.id == company_id("123"))
    assert company.attributes["financials"] == [
        {"year": 2022, "revenue": 1000.0, "net_result": -250.0, "employees": 4.0},
        {"year": 2023, "revenue": 1500.0, "net_result": 300.0, "employees": 5.0},
    ]
    assert (company.attributes["revenue"], company.attributes["financial_year"]) == (1500.0, 2023)
    assert len([claim for claim in result.claims if claim.predicate == "Revenue"]) == 2
