import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from core.config import get_settings
from core.events import EventBus
from core.redis import arq_redis_settings, create_redis
from core.runs import RunStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis = create_redis()
    queue = await create_pool(arq_redis_settings())

    app.state.redis = redis
    app.state.queue = queue  # job queue (arq)
    app.state.runs = RunStore(redis)
    app.state.bus = EventBus(redis)

    yield

    await queue.aclose()
    await redis.aclose()


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = FastAPI(title="Synapse API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=get_settings().cors_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
