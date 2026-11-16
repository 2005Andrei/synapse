from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from core.config import get_settings


@lru_cache
def get_chat_model() -> BaseChatModel | None:
    """The chat model for the agent nodes, or None while none is configured.

    Set LLM_MODEL to a langchain model string ("provider:model") and install
    that provider's package (e.g. `uv add langchain-anthropic`).
    """
    model = get_settings().llm_model
    if not model:
        return None

    from langchain.chat_models import init_chat_model

    return init_chat_model(model)
