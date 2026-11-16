"""The scraper contract.

Every scraper is a `BaseScraper` subclass that implements one method:

    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None

and reports what it found through `out`, in the shared domain model
(`Source`, `Entity`, `Claim`). Callers only ever use `search()`, which never
raises and always returns a `ScrapeResult`.

Scrapers are blocking (they run in a worker thread) and single-use:

    with HotNewsScraper() as scraper:
        result = scraper.search("Dedeman")
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

from connectors.common.http import HttpClient, ScraperCancelled, describe_error
from models.ids import claim_id, source_id
from models.schemas import Claim, Entity, Source
from models.types import ClaimStatus, ClaimType, EntityType, Predicate, SourceType

log = logging.getLogger(__name__)


class ScraperCategory(StrEnum):
    REGISTRY = "registry"
    NEWS = "news"
    JOURNALISM = "journalism"


class ScrapeStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    ERROR = "error"


class ScraperInfo(BaseModel):
    name: str
    label: str
    category: ScraperCategory
    source_type: SourceType
    description: str


class ScrapeResult(BaseModel):
    scraper: str
    query: str
    status: ScrapeStatus
    error: str | None = None
    fetched_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    duration_ms: int = 0
    sources: list[Source] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScrapeBatch:
    """Collects what one scraper run finds. Adding the same id twice is a no-op."""

    def __init__(self, scraper: "BaseScraper"):
        self.scraper = scraper
        self.sources: dict[UUID, Source] = {}
        self.entities: dict[UUID, Entity] = {}
        self.claims: dict[UUID, Claim] = {}
        self.metadata: dict[str, Any] = {}

    def source(
        self,
        *,
        url: str,
        title: str,
        content: str,
        published_at: str | None = None,
        type: SourceType | None = None,
        key: str | None = None,
    ) -> Source:
        """Sources are identified by url; pass `key` when several records
        share one url (e.g. a registry with no per-record page)."""
        source = Source(
            id=source_id(key or url),
            type=type or self.scraper.source_type,
            title=title,
            url=url,
            publisher=self.scraper.label,
            published_at=published_at,
            content=content,
        )
        return self.sources.setdefault(source.id, source)

    def entity(
        self,
        id: UUID,
        type: EntityType,
        name: str,
        description: str = "",
        **attributes: Any,
    ) -> Entity:
        """`name` becomes the first alias, which is what the graph shows as label."""
        if id in self.entities:
            return self.entities[id]
        entity = Entity(
            id=id,
            type=type,
            description=description,
            aliases=[name],
            attributes={k: v for k, v in attributes.items() if v not in (None, "", [])},
        )
        self.entities[id] = entity
        return entity

    def claim(
        self,
        subject: Entity,
        predicate: Predicate | str,
        text: str,
        reference: Entity | None = None,
        *,
        sources: tuple[Source, ...] | list[Source] = (),
        type: ClaimType | None = None,
        status: ClaimStatus | None = None,
        confidence: float | None = None,
        key: object = "",
    ) -> Claim:
        """A relationship (`subject -predicate-> reference`) or, without a
        reference, a fact about the subject. `key` tells apart several facts
        with the same predicate (e.g. revenue per year)."""
        claim = Claim(
            id=claim_id(subject.id, predicate, reference.id if reference else key),
            type=type or (ClaimType.RELATIONSHIP if reference else ClaimType.FACT),
            subject_ids=[subject.id],
            predicate=predicate,
            claim_text=text,
            reference_ids=[reference.id] if reference else [],
            source_ids=[source.id for source in sources],
            claim_status=status or self.scraper.claim_status,
            confidence=self.scraper.confidence if confidence is None else confidence,
        )
        return self.claims.setdefault(claim.id, claim)

    def note(self, text: str) -> None:
        """Something the user should know about this run that is not an error
        (e.g. "one of the two upstreams was down"). Shown next to the scraper."""
        notes = self.metadata.setdefault("notes", [])
        if text not in notes:
            notes.append(text)

    @property
    def empty(self) -> bool:
        return not (self.sources or self.entities or self.claims)


class BaseScraper(ABC):
    # --- identity: every subclass sets these -------------------------------
    name: ClassVar[str]
    label: ClassVar[str]
    category: ClassVar[ScraperCategory]
    source_type: ClassVar[SourceType]
    description: ClassVar[str] = ""

    # --- defaults a subclass may override ----------------------------------
    default_limit: ClassVar[int] = 5
    # True for sources that can be searched by CUI (fiscal code). The others
    # only understand names: for a CUI query they get the company's name.
    accepts_cui: ClassVar[bool] = False
    # How much to trust what this source says, before any evaluation.
    claim_status: ClassVar[ClaimStatus] = ClaimStatus.REPORTED
    confidence: ClassVar[float] = 0.8

    headers: ClassVar[dict[str, str]] = {}
    timeout: ClassVar[float] = 15
    retries: ClassVar[int] = 3
    delay: ClassVar[float] = 0.25

    def __init__(self) -> None:
        self._clients: list[HttpClient] = []
        self.http = self.new_client()

    def new_client(self, **overrides: Any) -> HttpClient:
        options = {
            "headers": self.headers,
            "timeout": self.timeout,
            "retries": self.retries,
            "delay": self.delay,
            **overrides,
        }
        client = HttpClient(**options)
        self._clients.append(client)
        return client

    # --- to implement ------------------------------------------------------
    @abstractmethod
    def scrape(self, query: str, limit: int, out: ScrapeBatch) -> None:
        """Look `query` up and add what is found to `out`. May raise."""

    # --- public API --------------------------------------------------------
    def search(self, query: str, limit: int | None = None) -> ScrapeResult:
        query = (query or "").strip()
        out = ScrapeBatch(self)
        started = time.perf_counter()
        error: str | None = None

        try:
            if not query:
                raise ValueError("empty query")
            self.scrape(query, limit or self.default_limit, out)
        except ScraperCancelled:
            error = "cancelled"
        except httpx.HTTPError as exc:
            # Upstream said no / went away: expected, no traceback needed.
            error = describe_error(exc)
            log.warning("[%s] failed for %r: %s", self.name, query, error)
        except Exception as exc:
            log.exception("[%s] failed for %r", self.name, query)
            error = f"{type(exc).__name__}: {exc}"

        if error:
            status = ScrapeStatus.ERROR
        else:
            status = ScrapeStatus.EMPTY if out.empty else ScrapeStatus.OK

        return ScrapeResult(
            scraper=self.name,
            query=query,
            status=status,
            error=error,
            duration_ms=int((time.perf_counter() - started) * 1000),
            sources=list(out.sources.values()),
            entities=list(out.entities.values()),
            claims=list(out.claims.values()),
            metadata=out.metadata,
        )

    def cancel(self) -> None:
        """Make the running `search()` stop at its next HTTP request."""
        for client in self._clients:
            client.cancel()

    def close(self) -> None:
        for client in self._clients:
            client.close()

    def __enter__(self) -> "BaseScraper":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @classmethod
    def info(cls) -> ScraperInfo:
        return ScraperInfo(
            name=cls.name,
            label=cls.label,
            category=cls.category,
            source_type=cls.source_type,
            description=cls.description,
        )
