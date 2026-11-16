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
    # "anthropic:claude-sonnet-5-5"; while it is unset the LLM nodes are skipped.
    llm_model: str | None = None
    max_agent_iterations: int = 3
    # How many follow-up searches the discovery stage proposes per run.
    max_leads: int = 6

    # Optional sicap.ai key for the SEAP scraper.
    sicap_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
