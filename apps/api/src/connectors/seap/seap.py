import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import httpx

from connectors.common.cui import CuiLookupUnavailable, resolve_cui
from connectors.common.http import ScraperCancelled, describe_error
from connectors.common.text import fold
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from core.config import get_settings
from models.ids import company_id, document_id, mention_id
from models.schemas import Entity
from models.types import EntityType, Predicate, SourceType

log = logging.getLogger(__name__)


@dataclass
class Contract:
    contract_id: str
    title: str
    contracting_authority: str
    supplier: str
    contract_value: float
    currency: str
    contract_date: str
    procedure_type: str
    cpv_code: str
    status: str
    description: str
    source_url: str
    # Which side of the contract the searched CUI is on, when known.
    target_role: str = ""  # "supplier" | "authority" | ""


class ElicitatieScraper(BaseScraper):
    """Public procurement contracts for a company (CUI or name).

    Two upstreams: sicap.ai (needs SICAP_API_KEY; only finds the company as a
    contracting authority) and the public e-licitatie.ro API (direct
    acquisitions, filtered client-side because the API cannot filter by CUI).
    """

    name = "seap"
    label = "SEAP"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.GOVERNMENT_DOCUMENT
    description = "Public procurement contracts (e-licitatie.ro, optionally sicap.ai)"
    confidence = 0.9
    timeout = 30
    accepts_cui = True
    retries = 1
    delay = 2.0
    default_limit = 25  # contracts
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ro-RO,ro;q=0.9",
    }

    BASE_URL = "http://e-licitatie.ro"
    API_BASE = "http://e-licitatie.ro/api-pub"
    SICAP_AI_BASE = "https://api.sicap.ai/v1"

    # The e-licitatie listing cannot be filtered by CUI, so finding a company
    # means paging through every acquisition. Cap it: 100 rows and 2s per page.
    max_pages = 5
    page_size = 100

    def __init__(self) -> None:
        super().__init__()
        self.sicap_api_key = get_settings().sicap_api_key.strip()
        self.elicitatie_error: str | None = None

    # --- sicap.ai ----------------------------------------------------------
    def _sicap(self, path: str) -> Any:
        if not self.sicap_api_key:
            return None
        try:
            return self.http.get(
                f"{self.SICAP_AI_BASE}{path}",
                headers={"Authorization": f"Bearer {self.sicap_api_key}"},
            ).json()
        except ScraperCancelled:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            log.info("[seap] sicap.ai %s failed: %s", path, exc)
            return None

    def _sicap_contracts(self, path: str, role: str = "") -> list[Contract]:
        data = self._sicap(path)
        if isinstance(data, dict):
            data = data.get("items") or data.get("data") or data.get("contracts") or []
        contracts = (self._parse_sicap_ai_contract(item, role) for item in data or [])
        return [contract for contract in contracts if contract]

    def check_cui_exists(self, cif: str) -> bool:
        data = self._sicap(f"/cui/{cif}/exists")
        return bool(isinstance(data, dict) and data.get("exists"))

    def get_ac_contracts(self, cif: str) -> list[Contract]:
        """Contracts where `cif` is the contracting authority."""
        return self._sicap_contracts(f"/ac/{cif}/contracts", role="authority")

    def get_ac_contracts_latest(self, cif: str) -> list[Contract]:
        return self._sicap_contracts(f"/ac/{cif}/contracts/latest", role="authority")

    def get_contracts_by_date(self, target_date: str) -> list[Contract]:
        return self._sicap_contracts(f"/contracts/daily/{target_date}")

    def get_contract_by_id(self, source: str, contract_id: str) -> Contract | None:
        return self._parse_sicap_ai_contract(
            self._sicap(f"/contracts/{source}/{contract_id}")
        )

    def _parse_sicap_ai_contract(self, item: Any, role: str = "") -> Contract | None:
        if not item or not isinstance(item, dict):
            return None

        def first(*keys: str, default: Any = "") -> Any:
            return next((item[key] for key in keys if item.get(key)), default)

        return Contract(
            contract_id=str(first("id", "contractId")),
            title=first("name", "title", "contractTitle"),
            contracting_authority=first("contractingAuthority", "authority", "caName"),
            supplier=first("supplier", "winner", "supplierName"),
            contract_value=self._parse_value(first("value", "closingValue", "amount", default=0)),
            currency=first("currency", default="RON"),
            contract_date=first("date", "contractDate", "publicationDate"),
            procedure_type=first("procedureType", "type"),
            cpv_code=first("cpvCode", "cpv"),
            status=first("status"),
            description=first("description"),
            source_url=first("url", "sourceUrl"),
            target_role=role,
        )

    # --- e-licitatie.ro ----------------------------------------------------
    def search_elicitatie_by_cui(
        self, cui: str, date_start: str = "2022-01-01"
    ) -> list[Contract]:
        url = f"{self.API_BASE}/DirectAcquisitionCommon/GetDirectAcquisitionList/"
        body = {
            "pageSize": self.page_size,
            "pageIndex": 0,
            "showOngoingDa": False,
            "cookieContext": None,
            "sysDirectAcquisitionStateId": None,
            "publicationDateStart": None,
            "publicationDateEnd": None,
            "finalizationDateStart": date_start,
            "finalizationDateEnd": datetime.now().strftime("%Y-%m-%d"),
        }
        contracts: list[Contract] = []

        for page in range(self.max_pages):
            body["pageIndex"] = page
            data = self.http.post(url, json=body).json()
            items = data.get("items") or []

            for item in items:
                supplier_cui = str(item.get("supplierId") or item.get("winnerFiscalNumber") or "")
                authority_cui = str(item.get("contractingAuthorityId") or item.get("cAFiscalNumber") or "")
                role = "supplier" if cui in supplier_cui else "authority" if cui in authority_cui else ""
                if role:
                    contracts.append(self._parse_direct_acquisition(item, role))

            fetched = (page + 1) * self.page_size
            log.info("[seap] page %s: %s rows, %s matches so far", page, len(items), len(contracts))
            if len(items) < self.page_size or fetched >= data.get("total", 0):
                break

        return contracts

    def _parse_direct_acquisition(self, item: dict, role: str = "") -> Contract:
        state = item.get("sysDirectAcquisitionState")
        acquisition_id = item.get("directAcquisitionId", item.get("id", ""))
        return Contract(
            contract_id=str(acquisition_id),
            title=item.get("directAcquisitionName") or item.get("name") or "",
            contracting_authority=item.get("contractingAuthorityName") or "",
            supplier=item.get("supplierName") or item.get("winnerName") or "",
            contract_value=self._parse_value(item.get("closingValue", item.get("totalAmount", 0))),
            currency=item.get("currency") or "RON",
            contract_date=item.get("finalizationDate") or item.get("publicationDate") or "",
            procedure_type="Achizitie directa",
            cpv_code=item.get("cpvCode") or item.get("cpvCodeAndName") or "",
            status=state.get("text", "") if isinstance(state, dict) else "",
            description=item.get("description") or "",
            source_url=f"{self.BASE_URL}/pub/direct-acquisition/view/{acquisition_id}",
            target_role=role,
        )

    @staticmethod
    def _parse_value(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        # "1.234.567,89" -> 1234567.89
        cleaned = re.sub(r"[^\d.,]", "", str(value)).replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def search_by_cui(self, cui: str, date_start: str = "2022-01-01") -> list[Contract]:
        contracts = self.get_ac_contracts(cui)
        seen = {contract.contract_id for contract in contracts}
        try:
            direct = self.search_elicitatie_by_cui(cui, date_start=date_start)
        except httpx.HTTPError as exc:
            # e-licitatie.ro turns automated clients away at times. That only
            # sinks the scraper when sicap.ai had nothing either.
            self.elicitatie_error = describe_error(exc)
            if not contracts:
                raise
            direct = []
        for contract in direct:
            if contract.contract_id not in seen:
                seen.add(contract.contract_id)
                contracts.append(contract)
        return contracts

    # --- scrape ------------------------------------------------------------
    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        try:
            cui = resolve_cui(self.http, query)
        except CuiLookupUnavailable as exc:
            out.note(str(exc))
            return
        if not cui:
            return

        contracts = self.search_by_cui(cui)
        if self.elicitatie_error:
            out.note(f"direct acquisitions unavailable: {self.elicitatie_error}")
        out.metadata.update(
            cui=cui,
            contracts=len(contracts),
            total_value=sum(contract.contract_value for contract in contracts),
            sicap_ai=bool(self.sicap_api_key),
            max_pages=self.max_pages,
        )

        for contract in contracts[:limit]:
            title = contract.title or f"Contract {contract.contract_id}"
            url = contract.source_url or f"{self.BASE_URL}/"
            source = out.source(
                url=url,
                title=title,
                content=json.dumps(asdict(contract), ensure_ascii=False),
                published_at=contract.contract_date or None,
                key=f"seap:{contract.contract_id}",
            )
            document = out.entity(
                document_id(f"seap:{contract.contract_id}"),
                EntityType.DOCUMENT,
                title,
                description=(
                    f"{contract.procedure_type} • {contract.contract_value:,.2f} "
                    f"{contract.currency} • {contract.contract_date}"
                ),
                document_type="procurement contract",
                contract_id=contract.contract_id,
                value=contract.contract_value,
                currency=contract.currency,
                date=contract.contract_date,
                procedure_type=contract.procedure_type,
                cpv_code=contract.cpv_code,
                status=contract.status,
                contracting_authority=contract.contracting_authority,
                supplier=contract.supplier,
                url=url,
                source_id=str(source.id),
            )

            supplier = self._party(out, contract.supplier, cui, contract.target_role == "supplier")
            authority = self._party(
                out, contract.contracting_authority, cui, contract.target_role == "authority"
            )
            amount = f"{contract.contract_value:,.2f} {contract.currency}"
            if supplier:
                out.claim(
                    supplier,
                    Predicate.WON_CONTRACT,
                    f"{contract.supplier} a câștigat contractul „{title}” ({amount}).",
                    document,
                    sources=[source],
                )
            if authority:
                out.claim(
                    authority,
                    "Awarded",
                    f"{contract.contracting_authority} a atribuit contractul „{title}” ({amount}).",
                    document,
                    sources=[source],
                )

    def _party(self, out: ScrapeBatch, name: str, cui: str, is_target: bool) -> Entity | None:
        """The searched company gets its registry-wide id; counterparties are
        only known by name here."""
        if not name and not is_target:
            return None
        if is_target:
            return out.entity(
                company_id(cui), EntityType.ORGANIZATION, name or f"CUI {cui}", cui=cui
            )
        return out.entity(
            mention_id(self.name, EntityType.ORGANIZATION, fold(name)),
            EntityType.ORGANIZATION,
            name,
        )
