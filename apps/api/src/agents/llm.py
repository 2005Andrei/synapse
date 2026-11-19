"""The chat model behind the agent stages.

One place decides whether there is a model and how it is called, so the stages
only ever ask for `get_chat_model()` (None = work without one) and `ask()`
(one structured answer). The model is whatever a langchain "provider:model"
string names: a local one served by Ollama ("ollama:qwen2.5"), or a cloud API
("anthropic:claude-opus-5-5"). The server has a default (`LLM_MODEL`); a
search may bring its own (`resolve`).
"""

import asyncio
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from core.config import get_settings

log = logging.getLogger(__name__)

Message = tuple[str, str]  # ("system" | "human", text)
LOCAL = "ollama"


def provider_of(name: str | None) -> str:
    return (name or "").partition(":")[0].lower() if ":" in (name or "") else ""


@dataclass(frozen=True)
class Limits:
    """How hard a model may be driven."""

    concurrency: int
    max_sources: int
    max_source_chars: int
    timeout: float
    budget: float | None = None  # seconds for all the calls of one search; None = no ceiling


def limits_for(name: str | None) -> Limits:
    settings = get_settings()
    if provider_of(name) != LOCAL:
        return Limits(
            settings.llm_concurrency, settings.llm_max_sources, settings.llm_max_source_chars, settings.llm_timeout_seconds
        )
    # One GPU answers one request at a time, slowly, and Ollama drops whatever
    # does not fit the context window without saying so. So: one call at a
    # time, more patience, and texts cut to what fits beside the instructions
    # (about 2.5 characters per token of Romanian, 1,500 tokens kept free).
    fits = max(2_000, int((settings.llm_context_tokens - 1_500) * 2.5))
    return Limits(
        1,
        min(settings.llm_max_sources, settings.llm_local_max_sources),
        min(settings.llm_max_source_chars, fits),
        max(settings.llm_timeout_seconds, 300),
        settings.llm_local_budget_seconds,
    )


def build_model(name: str, *, api_key: str | None = None, base_url: str | None = None) -> BaseChatModel:
    """Load a model by name. Raises when the provider package is missing or
    the name is not one langchain knows."""
    from langchain.chat_models import init_chat_model

    settings = get_settings()
    options: dict[str, Any] = {}
    if provider_of(name) == LOCAL:
        options = {"num_ctx": settings.llm_context_tokens, "temperature": 0}
    elif api_key:
        options["api_key"] = api_key
    if base_url:
        options["base_url"] = base_url
    return init_chat_model(name, **options)


def _try(name: str, **options: Any) -> tuple[BaseChatModel | None, str | None]:
    """(model, problem). A model that cannot be loaded is something to report,
    not a reason to fail a search that works fine without it."""
    try:
        return build_model(name, **options), None
    except Exception as exc:  # missing provider package, bad name
        log.warning("model %s could not be loaded", name, exc_info=True)
        return None, f"{type(exc).__name__}: {exc}"


@lru_cache
def _load() -> tuple[BaseChatModel | None, str | None]:
    settings = get_settings()
    if not settings.llm_model:
        return None, None
    return _try(settings.llm_model, base_url=settings.llm_base_url or None)


def get_chat_model() -> BaseChatModel | None:
    """The server's default model, or None while none is usable.

    Set LLM_MODEL and install that provider's package
    (`uv sync --extra ollama`, see pyproject.toml).
    """
    return _load()[0]


def llm_status() -> dict[str, Any]:
    """What a run should tell the user about its model: sent with `run.started`."""
    model, problem = _load()
    return _status(get_settings().llm_model or None, model, problem, "server")


def resolve(choice: dict[str, str] | None) -> tuple[BaseChatModel | None, dict[str, Any]]:
    """The model of one search: the user's own (`choice`: model, api_key,
    base_url) when they sent one, else the server's default."""
    if not choice or not choice.get("model"):
        return get_chat_model(), llm_status()
    name = choice["model"]
    base_url = choice.get("base_url") or (get_settings().llm_base_url if provider_of(name) == LOCAL else None)
    model, problem = _try(name, api_key=choice.get("api_key") or None, base_url=base_url or None)
    return model, _status(name, model, problem, "user")


def _status(name: str | None, model: object, problem: str | None, chosen_by: str) -> dict[str, Any]:
    return {
        "model": name,
        "ready": model is not None,
        "problem": problem,
        "local": provider_of(name) == LOCAL,
        "chosen_by": chosen_by,
    }


async def ask[Answer: BaseModel](
    model: BaseChatModel, schema: type[Answer], messages: list[Message], timeout: float | None = None
) -> Answer:
    """One call, answered as `schema`. Raises on timeout or provider error:
    the caller decides what the stage does without the answer."""
    settings = get_settings()
    options = {"method": settings.llm_structured_method} if settings.llm_structured_method else {}
    structured = model.with_structured_output(schema, **options)
    return await asyncio.wait_for(structured.ainvoke(messages), timeout or settings.llm_timeout_seconds)
