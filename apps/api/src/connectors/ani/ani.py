import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from connectors.common.text import fold
from connectors.scraper import BaseScraper, ScrapeBatch, ScraperCategory
from models.ids import document_id, mention_id
from models.types import EntityType, Predicate, SourceType

log = logging.getLogger(__name__)

_DOWNLOAD_LINK = re.compile(r"DownloadServlet")


@dataclass
class DeclarationPDF:
    title: str
    year: str
    type: str
    url: str
    unique_id: str
    date_str: str = ""
    raw_doc_type: str = ""


@dataclass
class PersonResult:
    name: str
    institution: str
    position: str = ""
    county: str = ""
    locality: str = ""
    pdfs: list[DeclarationPDF] = field(default_factory=list)


class AniScraper(BaseScraper):
    """Wealth and interest declarations of public officials (ANI legacy portal)."""

    name = "ani"
    label = "ANI"
    category = ScraperCategory.REGISTRY
    source_type = SourceType.GOVERNMENT_DOCUMENT
    description = "Declarations of assets and interests, by official's name"
    confidence = 0.9
    timeout = 30
    retries = 1
    default_limit = 10  # officials

    BASE_URL = "https://old-declaratii.integritate.eu"
    SEARCH_ENDPOINT = f"{BASE_URL}/index.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": BASE_URL,
    }

    max_declarations_per_person = 8

    # --- raw portal access -------------------------------------------------
    def fetch_results(self, name: str) -> list[PersonResult]:
        # The portal is a JSF app: load the form first to get its ViewState
        # (and session cookie), then post the search.
        form = BeautifulSoup(self.http.get(self.SEARCH_ENDPOINT).text, "lxml")
        view_state = form.find("input", {"name": "javax.faces.ViewState"})
        if view_state is None:
            raise RuntimeError("ANI search form not found (portal layout changed?)")

        response = self.http.post(
            self.SEARCH_ENDPOINT,
            data={
                "form": "form",
                "form:searchKey_input": name,
                "form:searchField_input": "numePrenume",
                "form:submitButtonSS": "Caută",
                "javax.faces.ViewState": view_state["value"],
            },
        )
        return self.parse_results(response.text)

    def parse_results(self, html: str) -> list[PersonResult]:
        soup = BeautifulSoup(html, "lxml")
        people: dict[tuple[str, str], PersonResult] = {}
        seen_uids: set[str] = set()

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 8:
                continue
            link = cells[7].find("a", href=_DOWNLOAD_LINK)
            if not link:
                continue

            href = link.get("href", "")
            if href.startswith("/"):
                href = self.BASE_URL + href

            uid = self._get_uid(href)
            if uid in seen_uids:
                continue
            seen_uids.add(uid)

            name, institution, position, county, locality, date_str, doc_type_raw = (
                cell.get_text(strip=True) for cell in cells[:7]
            )
            person = people.setdefault(
                (name, institution),
                PersonResult(name, institution, position, county, locality),
            )
            person.pdfs.append(
                DeclarationPDF(
                    title=f"{doc_type_raw} ({date_str})",
                    year=date_str.split(".")[-1] if "." in date_str else "",
                    type="avere" if "avere" in doc_type_raw.lower() else "interese",
                    url=href,
                    unique_id=uid,
                    date_str=date_str,
                    raw_doc_type=doc_type_raw,
                )
            )

        return list(people.values())

    @staticmethod
    def _get_uid(url: str) -> str:
        for param in ("uniqueIdentifier=", "fileName="):
            if param in url:
                return url.split(param)[1].split("&")[0]
        return url.split("/")[-1]

    # --- scrape ------------------------------------------------------------
    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        people = self.fetch_results(query)
        out.metadata.update(
            officials=len(people),
            declarations=sum(len(person.pdfs) for person in people),
        )

        for person in people[:limit]:
            role = " at ".join(p for p in (person.position, person.institution) if p)
            official = out.entity(
                mention_id(
                    self.name,
                    EntityType.PERSON,
                    f"{fold(person.name)}:{fold(person.institution)}",
                ),
                EntityType.PERSON,
                person.name,
                description=role or "Public official",
                public_roles=[role] if role else None,
                institution=person.institution,
                position=person.position,
                county=person.county,
                locality=person.locality,
                declarations=len(person.pdfs),
            )

            for pdf in person.pdfs[: self.max_declarations_per_person]:
                title = f"Declarație de {pdf.type} ({pdf.year or '?'}) — {person.name}"
                source = out.source(
                    url=pdf.url,
                    title=title,
                    # The PDF itself is not downloaded yet; record what the index says.
                    content=f"{pdf.raw_doc_type}, depusă la {pdf.date_str} de {person.name} ({role}).",
                )
                declaration = out.entity(
                    document_id(f"ani:{pdf.unique_id}"),
                    EntityType.DOCUMENT,
                    f"Declarație de {pdf.type} ({pdf.year or '?'})",
                    description=f"{pdf.raw_doc_type} — {person.name}",
                    document_type=f"declarație de {pdf.type}",
                    year=pdf.year,
                    submission_date=pdf.date_str,
                    issuing_authority="ANI",
                    url=pdf.url,
                    source_id=str(source.id),
                )
                out.claim(
                    official,
                    Predicate.PUBLISHED,
                    f"{person.name} a depus o declarație de {pdf.type} la {pdf.date_str}.",
                    declaration,
                    sources=[source],
                )
