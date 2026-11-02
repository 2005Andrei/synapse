set export := true
source .env.example

dev:
    docker compose -f compose.dev.yaml up --build

down:
    docker compose -f compose.dev.yaml down

shell-api:
    docker compose -f compose.dev.yaml exec api /bin/bash

shell-web:
    docker compose -f compose.dev.yaml exec web /bin/sh
