import json

from connectors.common.cui import parse_cui
from connectors.common.text import guess_entity_type
from connectors.onrc.index import Firm, OnrcIndex, Representative, get_index, person_key
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from models.ids import company_id, mention_id
from models.schemas import Entity
from models.types import ClaimStatus, EntityType, Predicate, SourceType

# CALITATE (folded) -> predicate. Anything else: "Represents".
_RUNS_IT = ("administrator", "director", "presedinte", "membru", "cenzor", "conducator")


class OnrcScraper(BaseScraper):
    """The trade register: a company's legal representatives, and the
    companies a person represents. Reads the local index of ONRC's open data."""

    name = "onrc"
    label = "ONRC"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.OFFICIAL_REGISTRY
    description = "Trade register open data: companies by name or CUI, their administrators, a person's companies"
    claim_status = ClaimStatus.VERIFIED
    confidence = 0.95
    accepts_cui = True
    max_companies = 5
    max_roles = 25

    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        index = get_index()
        if index is None:
            out.note("the ONRC index is not built on this server (run `just onrc-import`)")
            return
        meta = index.meta()
        out.metadata["dataset"] = meta.get("title")
        if meta.get("sample"):
            out.note(f"sample index: only CUI {meta['sample']} are in it")

        cui = parse_cui(query)
        if cui:
            firm = index.by_cui(cui)
            if firm:
                self._company(firm, index, meta, out)
            return

        for firm in index.search_firms(query, self.max_companies):
            self._company(firm, index, meta, out)

        # The same words may also be a person: every company they represent.
        for role in index.roles_of(query, self.max_roles):
            firm = index.by_reg(role.reg)
            if firm:
                company, source = self._company_entity(firm, meta, out, [role])
                self._representative(role, firm, company, source, out)

    def _company(self, firm: Firm, index: OnrcIndex, meta: dict, out: ScrapeBatch) -> None:
        people = index.representatives(firm.reg)
        company, source = self._company_entity(firm, meta, out, people)
        for person in people:
            self._representative(person, firm, company, source, out)

    def _company_entity(self, firm: Firm, meta: dict, out: ScrapeBatch, people: list[Representative]):
        source = out.source(
            url=meta.get("url") or "https://data.gov.ro/organization/onrc",
            key=f"onrc:{firm.reg}",
            title=f"ONRC — {firm.name} ({firm.reg})",
            content=json.dumps(
                {"firma": firm.__dict__, "reprezentanti": [person.__dict__ for person in people]},
                ensure_ascii=False,
            ),
        )
        company = out.entity(
            company_id(firm.cui) if firm.cui else mention_id(self.name, EntityType.ORGANIZATION, firm.reg),
            EntityType.ORGANIZATION,
            firm.name,
            description=" — ".join(part for part in (firm.form, firm.locality, firm.county) if part),
            cui=firm.cui,
            registration_number=firm.reg,
            legal_form=firm.form,
            incorporation_date=firm.registered,
            address=firm.address,
            jurisdiction="RO",
        )
        return company, source

    def _representative(self, person: Representative, firm: Firm, company: Entity, source, out: ScrapeBatch) -> None:
        role = person.role or "reprezentant"
        # A liquidator is usually a firm; someone with a date of birth is a person.
        kind = EntityType.PERSON if person.born else guess_entity_type(person.name)
        # The date of birth is part of the identity: two people with one name
        # and different birthdays are two entities.
        entity = out.entity(
            mention_id(self.name, kind, f"{person_key(person.name)}|{person.born or ''}"),
            kind,
            person.name,
            description=f"{role} la {firm.name}",
            date_of_birth=person.born,
            birth_place=person.birth_place,
            residence=person.residence,
        )
        runs_it = any(word in role.lower() for word in _RUNS_IT)
        out.claim(
            entity,
            Predicate.DIRECTOR_OF if runs_it else Predicate.REPRESENTS,
            f"{person.name} — {role} la {firm.name} (Registrul Comerțului).",
            company,
            sources=[source],
        )
