# Synapse API

FastAPI + Redis + arq worker. One investigation = one background job that
streams its progress to the browser over SSE.

```
browser ── POST /api/investigations ──▶ api ── enqueue ──▶ redis (arq queue)
   ▲                                                          │
   │                                                          ▼
   └── GET /api/investigations/{id}/events (SSE) ◀── api ◀── redis stream ◀── worker
                                                                               │
                                              plan → scrape → resolve → discover ⇄ evaluate
```

## Run it

```sh
just redis    # redis in docker
just api      # http://localhost:8000  (docs at /docs)
just worker   # arq worker
just web      # vite
just test
```

or everything in docker: `just dev`.

## Layout (`src/`)

| package      | what                                                                    |
| ------------ | ----------------------------------------------------------------------- |
| `api`        | HTTP routes, SSE endpoint                                               |
| `workers`    | arq settings + the `run_investigation` job (with a heartbeat)           |
| `agents`     | the LangGraph pipeline: stages in `nodes/`, name matching, leads        |
| `connectors` | scrapers: `scraper.py` is the contract, `registry.py` lists them        |
| `core`       | settings, redis, run store, event bus                                   |
| `models`     | `Entity`, `Claim`, `Source` and deterministic ids                       |

## HTTP

| route                                   | what                                                    |
| --------------------------------------- | ------------------------------------------------------- |
| `POST /api/investigations`              | queue a search: `{query, scrapers?}` → 202 + the run    |
| `GET /api/investigations`               | recent runs, newest first (the dashboard restores them) |
| `GET /api/investigations/{id}`          | one run's status                                        |
| `GET /api/investigations/{id}/events`   | SSE stream, replayed from the start or `Last-Event-ID`  |
| `DELETE /api/investigations/{id}`       | take a run off the recent list                          |
| `GET /api/scrapers` · `GET /api/health` |                                                         |

## Pipeline

| stage      | does                                                                                   |
| ---------- | -------------------------------------------------------------------------------------- |
| `plan`     | builds the seed entity; for a CUI, looks the company name up so that name-only sources (courts, press) are asked for the name, not the number |
| `scrape`   | runs the scrapers side by side, streaming each one's results as it finishes            |
| `resolve`  | merges entities with the *same* name, flags *similar* names (see below), links articles to the seed |
| `discover` | proposes follow-up searches (`agents/leads.py`): by claim count, or by a chat model when `LLM_MODEL` is set |
| `evaluate` | stub: the seam for grading claims and deciding on another round                         |

### Exact vs similar names

A search for "George Scripcaru" also returns "SCRIPCARU GEORGE DANIEL" and
"Scripcaru Gheorghe". Only the same words in any order count as the subject
and are merged (`agents/resolution.py`). A longer, shorter or differently
spelled name stays a separate entity with `attributes.match = "similar"` and a
`match_note` ("extra: DANIEL", "spelling: george ≈ gheorghe"), linked to the
subject by a `Similar_Name` claim of type `Hypothesis` (`agents/matching.py`).
The dashboard groups results by these identities and lets the user confirm
"same person" by hand.

Court party strings are split before any of this (`connectors/anaf/parties.py`):
"MUNICIPIUL BRAŞOV, PRIN PRIMAR GEORGE SCRIPCARU" becomes the city as the
party plus a `Represents` claim from George Scripcaru.

### A worker that dies

The worker renews a heartbeat key every few seconds while it runs a job. When
an SSE stream has been quiet and the run is still "running" without a
heartbeat, the API marks it failed and says so on the stream
(`core.runs.fail_if_orphaned`), instead of leaving the browser waiting.

## Events (SSE `data:` is JSON: `{id, type, run_id, ts, data}`)

`run.queued` · `run.started` · `stage.started` · `stage.completed` ·
`scraper.started` · `scraper.completed` · `graph.patch` · `agent.message` ·
`agent.leads` · `agent.skipped` · `run.completed` · `run.failed`

`graph.patch` carries `entities`, `claims`, `sources` to upsert, its `origin`
(scraper or stage name), `removed_entity_ids` for entities merged away by
resolution and `merged` (old id → surviving id). `scraper.completed` carries
`metadata.notes`: things worth telling the user that are not errors.

## Upstreams that are not ours to fix

- **demoanaf.ro** answers `402 Payment Required` (name → CUI search and
  administrators). ANAF's own services work by CUI only: the VAT registry
  record and the balance sheets (`webservicesp.anaf.ro/bilant`).
- **e-licitatie.ro** answers `403` to the direct-acquisitions API. Set
  `SICAP_API_KEY` to get contracts from sicap.ai instead.

## Adding a scraper

Subclass `BaseScraper` (or `ArticleScraper` for a news site), implement
`scrape(query, limit, out)`, report findings through `out.source()`,
`out.entity()`, `out.claim()` (and `out.note()` for caveats), and add the class
to `connectors/registry.py`. Set `accepts_cui = True` if it can be searched by
fiscal code.
