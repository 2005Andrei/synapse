import json
import logging
from datetime import date
from typing import Any

import httpx

from connectors.common.cui import DEMOANAF_API, CuiLookupUnavailable, resolve_cui
from connectors.common.http import ScraperCancelled, describe_error
from connectors.common.text import fold
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from models.ids import company_id, mention_id
from models.types import EntityType, Predicate, SourceType

log = logging.getLogger(__name__)

# Balance-sheet lines we report, by (folded) name. The indicator *codes* differ
# between balance-sheet types, the names do not.
REVENUE, NET_PROFIT, NET_LOSS, EMPLOYEES = "revenue", "net_profit", "net_loss", "employees"
_INDICATOR_NAMES = {
    "cifra de afaceri neta": REVENUE,
    "profit net": NET_PROFIT,
    "pierdere neta": NET_LOSS,
    "numar mediu de salariati": EMPLOYEES,
}


class AnafScraper(BaseScraper):
    """Company record and yearly financials for a CUI or a company name.

    Upstreams:
      - ANAF's public web services (official, free, by CUI only): the VAT
        registry record and the published balance sheets.
      - demoanaf.ro (third party, paid since 2026): company-name -> CUI search
        and the list of administrators. Optional: when it refuses, the scraper
        still returns the ANAF data and says what is missing.
    """

    name = "anaf"
    label = "ANAF"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.OFFICIAL_REGISTRY
    description = "Company registry record and balance sheets (ANAF), administrators (demoanaf.ro)"
    confidence = 0.9
    timeout = 30
    accepts_cui = True

    ANAF_URL = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
    BALANCE_URL = "https://webservicesp.anaf.ro/bilant"

    # How many past years of balance sheets to ask for.
    financial_years = 5

    def __init__(self) -> None:
        super().__init__()
        # ANAF's own endpoint serves an incomplete certificate chain. It also
        # asks callers to stay around one request per second.
        self.anaf_http = self.new_client(verify=False, timeout=15, retries=1, delay=1.0)
        self.demoanaf_error: str | None = None

    # --- raw API calls -----------------------------------------------------
    def get_anaf_data(self, cui: str) -> dict:
        payload = [{"cui": int(cui), "data": str(date.today())}]
        return self._json(self.anaf_http.post, self.ANAF_URL, json=payload)

    def company_name(self, cui: str) -> str | None:
        """The registered name behind a CUI, or None if ANAF does not know it."""
        record = (self.get_anaf_data(cui).get("found") or [{}])[0]
        return (record.get("date_generale") or {}).get("denumire") or None

    def get_balance_sheet(self, cui: str, year: int) -> dict:
        """One year of published financial statements; {} when not filed."""
        data = self._json(
            self.anaf_http.get, self.BALANCE_URL, params={"an": year, "cui": cui}
        )
        return data if data.get("i") else {}

    def get_company(self, cui: str) -> dict:
        """demoanaf.ro company card (administrators). Optional upstream."""
        if self.demoanaf_error:
            return {}
        try:
            data = self.http.get(f"{DEMOANAF_API}/company/{cui}").json()
            return data if isinstance(data, dict) else {}
        except ScraperCancelled:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            self.demoanaf_error = describe_error(exc)
            return {}

    def _json(self, call: Any, url: str, **kwargs: Any) -> dict:
        """Each upstream is optional: a failed one just contributes nothing."""
        try:
            data = call(url, **kwargs).json()
            return data if isinstance(data, dict) else {}
        except ScraperCancelled:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            log.info("[anaf] %s failed: %s", url, describe_error(exc))
            return {}

    def get_financials(self, cui: str) -> list[dict]:
        """The last `financial_years` balance sheets, oldest first, as
        {"year": 2023, "revenue": ..., "net_profit": ..., ...}."""
        last = date.today().year - 1
        years = []
        for year in range(last, last - self.financial_years, -1):
            sheet = self.get_balance_sheet(cui, year)
            if not sheet:
                # Last year's statements are published around mid-year; a gap
                # further back means the company did not file / did not exist.
                if year == last:
                    continue
                break
            years.append({"year": year, **_indicators(sheet)})
        return sorted(years, key=lambda entry: entry["year"])

    # --- scrape ------------------------------------------------------------
    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        try:
            cui = resolve_cui(self.http, query)
        except CuiLookupUnavailable as exc:
            out.note(str(exc))
            return
        if not cui:
            return
        out.metadata["cui"] = cui

        anaf = self.get_anaf_data(cui)
        company = self.get_company(cui).get("data") or {}
        if self.demoanaf_error:
            out.note(f"administrators unavailable: demoanaf.ro answered {self.demoanaf_error}")

        record = (anaf.get("found") or [{}])[0]
        general = record.get("date_generale") or {}
        address = record.get("adresa_sediu_social") or {}

        name = general.get("denumire") or company.get("name") or company.get("denumire")
        if not name:
            return

        status = general.get("stare_inregistrare") or ""
        place = ", ".join(
            part
            for part in (
                address.get("sdenumire_Judet"),
                address.get("sdenumire_Localitate"),
            )
            if part
        )
        years = self.get_financials(cui)
        latest = years[-1] if years else {}

        registry = out.source(
            url=f"https://www.anaf.ro/anaf/internet/RO/cautare-dupa-cui?cui={cui}",
            title=f"ANAF — {name} (CUI {cui})",
            content=json.dumps(
                {"anaf": record, "company": company}, ensure_ascii=False, default=str
            ),
        )
        org = out.entity(
            company_id(cui),
            EntityType.ORGANIZATION,
            name,
            description=" — ".join(part for part in (status, place) if part),
            cui=cui,
            registration_number=general.get("nrRegCom"),
            jurisdiction="RO",
            status=status,
            address=general.get("adresa"),
            caen_code=general.get("cod_CAEN"),
            vat_registered=(record.get("inregistrare_scop_Tva") or {}).get("scpTVA"),
            inactive=(record.get("stare_inactiv") or {}).get("statusInactivi"),
            revenue=latest.get(REVENUE),
            currency="RON" if latest.get(REVENUE) is not None else None,
            employees=latest.get(EMPLOYEES),
            financial_year=latest.get("year"),
            # The whole series, oldest first: the company window charts it.
            financials=[
                {
                    "year": year["year"],
                    "revenue": year.get(REVENUE),
                    "net_result": _net_result(year),
                    "employees": year.get(EMPLOYEES),
                }
                for year in years
            ],
        )

        for admin in company.get("administrators") or []:
            admin_name = (admin.get("name") or "").strip()
            if not admin_name:
                continue
            role = admin.get("role") or "Administrator"
            person = out.entity(
                mention_id(self.name, EntityType.PERSON, f"{cui}:{admin_name}"),
                EntityType.PERSON,
                admin_name,
                description=f"{role} la {name}",
                public_roles=[f"{role} — {name}"],
            )
            out.claim(
                person,
                Predicate.DIRECTOR_OF,
                f"{admin_name} este {role} la {name}.",
                org,
                sources=[registry],
            )

        if years:
            statements = out.source(
                url=f"{self.BALANCE_URL}?an={years[-1]['year']}&cui={cui}",
                title=f"Situații financiare — {name}",
                content=json.dumps(years, ensure_ascii=False, default=str),
                type=SourceType.GOVERNMENT_DOCUMENT,
            )
            for year in years:
                revenue = year.get(REVENUE) or 0
                net = _net_result(year) or 0
                employees = year.get(EMPLOYEES) or 0
                out.claim(
                    org,
                    "Revenue",
                    f"{name}, {year['year']}: cifră de afaceri {int(revenue):,} RON, "
                    f"rezultat net {int(net):,} RON, {int(employees)} angajați.",
                    sources=[statements],
                    key=year["year"],
                )


def _net_result(year: dict) -> float | None:
    """Profit as a positive number, loss as a negative one; None if neither was filed."""
    if year.get(NET_PROFIT):
        return year[NET_PROFIT]
    if year.get(NET_LOSS):
        return -year[NET_LOSS]
    return 0 if NET_PROFIT in year or NET_LOSS in year else None


def _indicators(sheet: dict) -> dict[str, float]:
    """{"revenue": ..., "net_profit": ...} from one ANAF balance sheet."""
    values: dict[str, float] = {}
    for item in sheet.get("i") or []:
        if not isinstance(item, dict):
            continue
        key = _INDICATOR_NAMES.get(fold(item.get("val_den_indicator")))
        if key and isinstance(item.get("val_indicator"), (int, float)):
            values[key] = item["val_indicator"]
    return values
