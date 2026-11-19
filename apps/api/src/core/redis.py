from arq.connections import RedisSettings
from redis.asyncio import Redis

from core.config import get_settings

PREFIX = "synapse"


# Sorted set of run ids by creation time: what "recent searches" lists.
RUNS_INDEX = f"{PREFIX}:runs"


def run_key(run_id: str) -> str:
    return f"{PREFIX}:run:{run_id}"


def run_events_key(run_id: str) -> str:
    return f"{PREFIX}:run:{run_id}:events"


def run_secret_key(run_id: str) -> str:
    return f"{PREFIX}:run:{run_id}:secret"


def run_heartbeat_key(run_id: str) -> str:
    return f"{PREFIX}:run:{run_id}:heartbeat"


def create_redis() -> Redis:
    """Client for app data (runs, event streams). Values come back as str."""
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def arq_redis_settings() -> RedisSettings:
    """Connection settings for the arq job queue, on the same Redis."""
    return RedisSettings.from_dsn(get_settings().redis_url)
