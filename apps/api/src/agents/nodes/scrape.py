import asyncio
import logging
from typing import Any

from langgraph.runtime import Runtime

from agents.stages import graph_patch, stage
from agents.state import InvestigationState, PipelineContext, Record
from connectors.registry import get_scraper
from connectors.scraper import BaseScraper, ScrapeResult, ScrapeStatus
from core.events import EventType

log = logging.getLogger(__name__)


@stage("scrape")
async def scrape(
    state: InvestigationState, runtime: Runtime[PipelineContext]
) -> dict[str, Any]:
    """Run the selected scrapers side by side.

    Each scraper is blocking code, so it gets its own thread; its results are
    pushed to the frontend the moment it finishes instead of waiting for the
    slowest one.
    """
    ctx = runtime.context
    query = state["query"]
    name_query = state.get("name_query") or query
    slots = asyncio.Semaphore(ctx.settings.scraper_concurrency)

    async def run(name: str) -> ScrapeResult:
        async with slots:
            scraper = get_scraper(name)
            await ctx.emit(
                EventType.SCRAPER_STARTED, {"scraper": name, "label": scraper.label}
            )
            asked = query if scraper.accepts_cui else name_query
            result = await _search(scraper, asked, ctx.settings.scraper_timeout_seconds)
            dumped = result.model_dump(mode="json")

            await ctx.emit(
                EventType.SCRAPER_COMPLETED,
                {
                    "scraper": name,
                    "label": scraper.label,
                    "status": result.status,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                    "counts": {
                        kind: len(dumped[kind])
                        for kind in ("entities", "claims", "sources")
                    },
                    "metadata": result.metadata,
                },
            )
            if dumped["entities"] or dumped["claims"] or dumped["sources"]:
                await ctx.emit(
                    EventType.GRAPH_PATCH,
                    graph_patch(
                        name,
                        entities=dumped["entities"],
                        claims=dumped["claims"],
                        sources=dumped["sources"],
                    ),
                )
            return result

    results = await asyncio.gather(*(run(name) for name in state["scrapers"]))

    update: dict[str, dict[str, Record]] = {"entities": {}, "claims": {}, "sources": {}}
    reports = []
    for result in results:
        dumped = result.model_dump(mode="json")
        for kind, records in update.items():
            records.update({record["id"]: record for record in dumped[kind]})
        reports.append(
            {
                "scraper": result.scraper,
                "status": result.status.value,
                "error": result.error,
                "duration_ms": result.duration_ms,
            }
        )

    return {**update, "scrape_reports": reports}


async def _search(scraper: BaseScraper, query: str, timeout: float) -> ScrapeResult:
    def blocking() -> ScrapeResult:
        with scraper:
            return scraper.search(query)

    try:
        return await asyncio.wait_for(asyncio.to_thread(blocking), timeout)
    except TimeoutError:
        scraper.cancel()  # the thread stops at its next HTTP request
        return ScrapeResult(
            scraper=scraper.name,
            query=query,
            status=ScrapeStatus.ERROR,
            error=f"timed out after {timeout:.0f}s",
            duration_ms=int(timeout * 1000),
        )
    except asyncio.CancelledError:
        scraper.cancel()
        raise
