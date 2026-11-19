from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"

    # Any localhost port is allowed by default: vite moves to 5174+ when 5173 is busy.
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

    # How long a run (metadata + event stream) stays in Redis after its last write.
    run_ttl_seconds: int = 24 * 60 * 60
    run_events_maxlen: int = 5000

    # Worker
    worker_max_jobs: int = 4
    job_timeout_seconds: int = 15 * 60
    # A worker renews a run's heartbeat every `interval`; a running run whose
    # heartbeat has been gone for `ttl` belongs to a dead worker.
    heartbeat_interval_seconds: float = 5
    heartbeat_ttl_seconds: int = 20

    # Scraping stage
    scraper_timeout_seconds: float = 90
    scraper_concurrency: int = 6

    # Agent loop. `llm_model` is a langchain `init_chat_model` string such as
    # "anthropic:claude-opus-5-5"; while it is unset every stage falls back to
    # its rule-based version and no model is ever called.
    llm_model: str | None = None
    # Passed to `with_structured_output(method=...)` when set, for providers
    # whose default method a model rejects (e.g. "json_schema").
    llm_structured_method: str | None = None
    # Where the model is served, for providers that are not a fixed cloud API
    # (Ollama: http://localhost:11434 when unset).
    llm_base_url: str | None = None
    # Context window requested from a local model (Ollama `num_ctx`). Ollama
    # silently drops what does not fit, so articles are cut to fit this.
    llm_context_tokens: int = 8192
    llm_timeout_seconds: float = 120
    llm_concurrency: int = 3
    # A search may name its own model and API key (sent by the browser, kept
    # only until the worker picks the job up). A user-chosen server address is
    # a way to make this server call arbitrary hosts, so that is opt-in.
    allow_user_llm: bool = True
    allow_user_llm_base_url: bool = False
    # Cost ceiling of the reading step: how many source texts one run sends to
    # the model, and how much of each.
    llm_max_sources: int = 8
    # The same ceiling for a local model, which takes about a minute per
    # article on a CPU: more than a few and the search outlives its job timeout.
    llm_local_max_sources: int = 4
    # Seconds a local model may spend on one search in all. What is not read
    # by then is left for the next search; the job timeout is never reached.
    llm_local_budget_seconds: float = 480
    llm_max_source_chars: int = 20_000
    max_agent_iterations: int = 3
    # How many follow-up searches the discovery stage proposes per run.
    max_leads: int = 6

    # The local trade-register index (see connectors/onrc). Built on demand with
    # `just onrc-import`; while the file is missing the ONRC scraper says so.
    onrc_db: str = "data/onrc.sqlite"

    # After a company search, also search its top officer (one level deep).
    auto_follow_officer: bool = True

    # Optional sicap.ai key for the SEAP scraper.
    sicap_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
