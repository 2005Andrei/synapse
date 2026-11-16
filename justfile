set dotenv-load := true

dev:
    docker compose -f compose.dev.yaml up --build

down:
    docker compose -f compose.dev.yaml down

shell-api:
    docker compose -f compose.dev.yaml exec api /bin/bash

shell-web:
    docker compose -f compose.dev.yaml exec web /bin/sh

redis:
    docker compose -f compose.dev.yaml up -d redis

api: redis
    cd apps/api && uv run uvicorn api.app:app --reload --reload-dir src --port 8000

worker: redis
    cd apps/api && uv run arq workers.settings.WorkerSettings --watch src

web:
    cd apps/web && bun run dev

test:
    cd apps/api && uv run pytest
