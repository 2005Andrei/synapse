import logging
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from connectors.anaf.parties import split_party
from connectors.common.text import fold, guess_entity_type
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from models.ids import company_id, document_id, mention_id
from models.types import EntityType, Predicate, SourceType

log = logging.getLogger(__name__)

SOAP_URL = "http://portalquery.just.ro/query.asmx"
SOAP_HEADERS = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "portalquery.just.ro/CautareDosare",
    "Accept": "text/xml",
}
NS = "portalquery.just.ro"
XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
# The portal has no stable public deep link per case; point at its search page.
PORTAL_SEARCH_URL = "https://portal.just.ro/SitePages/cautare.aspx"

# calitateParte (folded) -> predicate. Anything else becomes "Party_To".
_PARTY_ROLES = {
    Predicate.DEFENDANT_IN: ("parat", "inculpat", "intimat", "debitor", "condamnat"),
    Predicate.PLAINTIFF_IN: ("reclamant", "petent", "creditor", "apelant", "contestator", "recurent"),
}  # fmt: skip


class PortalJustScraper(BaseScraper):
    """Court cases in which the query appears as a party (portal.just.ro)."""

    name = "portal_just"
    label = "Portal Just"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.COURT_DOCUMENT
    description = "Court cases by party name, from the portal.just.ro SOAP API"
    confidence = 0.9
    timeout = 30
    retries = 1
    default_limit = 10  # cases

    # A case can list hundreds of parties (insolvencies); keep the graph readable.
    max_parties_per_case = 6

    # --- raw API -----------------------------------------------------------
    def cauta_dosare(self, nume_parte: str) -> list[dict]:
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CautareDosare xmlns="{NS}">
      <numeParte>{escape(nume_parte)}</numeParte>
      <obiectDosar xsi:nil="true"/>
      <numarul xsi:nil="true"/>
      <dataStart xsi:nil="true"/>
      <dataStop xsi:nil="true"/>
    </CautareDosare>
  </soap:Body>
</soap:Envelope>"""
        response = self.http.post(
            SOAP_URL, content=body.encode("utf-8"), headers=SOAP_HEADERS
        )
        return self.parseaza_raspuns(response.text)

    def parseaza_raspuns(self, xml_text: str) -> list[dict]:
        root = ET.fromstring(xml_text)
        dosare = []

        for dosar in root.findall(f".//{{{NS}}}Dosar"):
            parti = [
                {"nume": nume, "calitate": _text(parte, "calitateParte")}
                for parte in dosar.findall(f".//{{{NS}}}DosarParte")
                if parte.get(XSI_NIL) != "true"
                and (nume := _text(parte, "nume")) != "N/A"
            ]
            sedinte = [
                {
                    "data": _text(sedinta, "data"),
                    "ora": _text(sedinta, "ora"),
                    "complet": _text(sedinta, "complet"),
                    "solutie": _text(sedinta, "solutie"),
                }
                for sedinta in dosar.findall(f".//{{{NS}}}DosarSedinta")
                if sedinta.get(XSI_NIL) != "true"
            ]
            dosare.append(
                {
                    "numar": _text(dosar, "numar"),
                    "data": min((s["data"] for s in sedinte), default="N/A"),
                    "status": _text(dosar, "stadiuProcesualNume"),
                    "instanta": _text(dosar, "institutie"),
                    "sectie": _text(dosar, "sectie"),
                    "obiect": _text(dosar, "obiect"),
                    "parti": parti,
                    "sedinte": sedinte,
                }
            )

        return dosare

    # --- scrape ------------------------------------------------------------
    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        dosare = self.cauta_dosare(query)
        # The API matches loosely; keep cases where a party has every query word.
        terms = fold(query).split()
        relevant = [
            dosar
            for dosar in dosare
            if any(_matches(parte["nume"], terms) for parte in dosar["parti"])
        ]
        out.metadata.update(
            raw_cases=len(dosare),
            relevant_cases=len(relevant),
            returned_cases=min(len(relevant), limit),
        )

        for dosar in relevant[:limit]:
            numar = dosar["numar"]
            court_file = out.source(
                url=PORTAL_SEARCH_URL,
                title=f"Dosar {numar}",
                content=_describe(dosar),
                key=f"portal_just:dosar:{numar}",
            )
            case = out.entity(
                document_id(f"dosar:{numar}"),
                EntityType.DOCUMENT,
                f"Dosar {numar}",
                description=f"{dosar['obiect']} — {dosar['instanta']} | Status: {dosar['status']}",
                document_type="court case",
                case_number=numar,
                court=dosar["instanta"],
                section=dosar["sectie"],
                subject_matter=dosar["obiect"],
                stage=dosar["status"],
                first_hearing=dosar["data"],
                hearings=len(dosar["sedinte"]),
                parties=len(dosar["parti"]),
            )

            # Parties that match the query first, so the cap never drops them.
            parti = sorted(dosar["parti"], key=lambda p: not _matches(p["nume"], terms))
            for parte in parti[: self.max_parties_per_case]:
                calitate = parte["calitate"]
                # "CITY, PRIN PRIMAR X" is two things: a party and who acts for it.
                parsed = split_party(parte["nume"])
                nume = parsed.name
                party_type = (
                    EntityType.ORGANIZATION if parsed.cui else guess_entity_type(nume)
                )
                party = out.entity(
                    company_id(parsed.cui)
                    if parsed.cui
                    else mention_id(self.name, party_type, fold(nume)),
                    party_type,
                    nume,
                    description="Parte în dosare judiciare",
                    cui=parsed.cui,
                )
                out.claim(
                    party,
                    _predicate(calitate),
                    f"{nume} — {calitate} în dosarul {numar} ({dosar['instanta']}).",
                    case,
                    sources=[court_file],
                )

                if parsed.representative:
                    rep_type = guess_entity_type(parsed.representative)
                    representative = out.entity(
                        mention_id(self.name, rep_type, fold(parsed.representative)),
                        rep_type,
                        parsed.representative,
                        description="Reprezentant în dosare judiciare",
                    )
                    out.claim(
                        representative,
                        Predicate.REPRESENTS,
                        f"{parsed.representative} reprezintă {nume} ({parsed.role}) "
                        f"în dosarul {numar}.",
                        party,
                        sources=[court_file],
                    )

def _text(element: ET.Element, tag: str) -> str:
    child = element.find(f"{{{NS}}}{tag}")
    return child.text.strip() if child is not None and child.text else "N/A"


def _matches(name: str, terms: list[str]) -> bool:
    folded = fold(name)
    return all(term in folded for term in terms)


def _predicate(calitate: str) -> Predicate | str:
    role = fold(calitate)
    for predicate, markers in _PARTY_ROLES.items():
        if any(marker in role for marker in markers):
            return predicate
    return "Party_To"


def _describe(dosar: dict) -> str:
    lines = [
        f"Dosar {dosar['numar']} — {dosar['instanta']}, {dosar['sectie']}",
        f"Obiect: {dosar['obiect']}",
        f"Stadiu: {dosar['status']}",
        "Părți: " + "; ".join(f"{p['nume']} ({p['calitate']})" for p in dosar["parti"]),
    ]
    lines += [
        f"Ședință {s['data']} {s['ora']} ({s['complet']}): {s['solutie']}"
        for s in dosar["sedinte"]
    ]
    return "\n".join(lines)
