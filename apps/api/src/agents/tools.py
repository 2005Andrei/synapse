"""Scrapers as LangChain tools, for the discovery agent to call."""

import asyncio

from langchain_core.tools import StructuredTool

from connectors.registry import SCRAPERS, get_scraper
from connectors.scraper import BaseScraper


def scraper_tool(scraper_cls: type[BaseScraper]) -> StructuredTool:
    def search(query: str) -> dict:
        """Returns the scraper's standard ScrapeResult as JSON."""
        with get_scraper(scraper_cls.name) as scraper:
            return scraper.search(query).model_dump(mode="json")

    async def asearch(query: str) -> dict:
        return await asyncio.to_thread(search, query)

    return StructuredTool.from_function(
        func=search,
        coroutine=asearch,
        name=f"search_{scraper_cls.name}",
        description=f"{scraper_cls.label}: {scraper_cls.description}. "
        "Input: a person name, a company name or a CUI.",
    )


def scraper_tools() -> list[StructuredTool]:
    return [scraper_tool(scraper_cls) for scraper_cls in SCRAPERS.values()]
