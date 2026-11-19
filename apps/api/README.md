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
| `agents`     | the LangGraph pipeline: stages in `nodes/`, name matching, the model    |
| `connectors` | scrapers: `scraper.py` is the contract, `registry.py` lists them        |
| `core`       | settings, redis, run store, event bus                                   |
| `models`     | `Entity`, `Claim`, `Source` and deterministic ids                       |

## HTTP

| route                                   | what                                                    |
| --------------------------------------- | ------------------------------------------------------- |
| `POST /api/investigations`              | queue a search: `{query, scrapers?, parent_id?, seed?, llm?}` → 202 + the run |
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
| `discover` | with a chat model: reads the article texts into entities and claims (`agents/extraction.py`). Always: proposes follow-up searches (`agents/leads.py`), picked by the model or by claim count |
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

### Searching further

A search can extend another one instead of starting a new graph:
`POST /api/investigations {query, parent_id, seed}` where `seed` is an entity
of the parent's graph. The run keeps that entity's id as its subject, so what
it finds attaches to the same node, and the dashboard folds its graph patches
into the parent's graph. Three things start such a run:

- the user right-clicks a person or company in the graph ("Search further"),
- the user picks a lead,
- the pipeline itself: after a company search, the people with a role in the
  company are ranked (`agents/leads.py: officers`) and the most senior one, if
  an administrator / director or above, is searched right away
  (`workers/tasks.py`, event `run.spawned`). One level only: a run that
  extends another never starts runs of its own. `AUTO_FOLLOW_OFFICER=false`
  turns it off.

### The trade register (ONRC)

ANAF only answers by fiscal code, and says nothing about who runs a company.
Both gaps are filled by ONRC's open data on data.gov.ro (CC BY 4.0, refreshed
every few weeks): `od_firme.csv` (4M+ companies: name, CUI, registration
number, address) and `od_reprezentanti_legali.csv` (legal representatives:
name, role, date and place of birth). This is where third-party lookup sites
get the same data.

```sh
just onrc-import                 # streams ~1 GB, builds apps/api/data/onrc.sqlite
just onrc-import 2816464,14399840   # a sample with just these companies
```

`connectors/onrc` then gives: company name → CUI (so ANAF works by name
again), a company's administrators, and the companies a person represents.
A representative's date of birth is part of their identity: two people with
one name and two birthdays stay two entities, and a mention without a
birthday is then merged with neither (`agents/resolution.py`).

Not in the open data: shareholders, and history (only current representatives).

### The chat model (optional)

Nothing calls a model until one is configured. It is a langchain
`provider:model` string, so the provider is a configuration choice.

A local model through Ollama (no key, nothing leaves the machine):

```sh
ollama serve && ollama pull qwen2.5
cd apps/api && uv sync --extra ollama
# .env
LLM_MODEL=ollama:qwen2.5
```

A local model gets its own limits (`agents/llm.py: limits_for`): one call at
a time, a longer timeout, fewer articles per search (`LLM_LOCAL_MAX_SOURCES`),
articles cut to fit `LLM_CONTEXT_TOKENS` (Ollama silently drops what does not
fit), and a time budget per search (`LLM_LOCAL_BUDGET_SECONDS`): what is not
read by then is left unread and the leads fall back to the rules, so a slow
model makes a search thinner, never stuck.

Check `ollama ps`. If it says `100% CPU`, the installed Ollama has no GPU
support (on Arch that is the `ollama` package; `ollama-cuda` is the GPU one).
Measured here on the CPU: about 21 tokens a second, so a short article takes
a minute or two and a full-length one (6,000 tokens) the whole five-minute
timeout. On a GPU the same calls take seconds.

A cloud model:

```sh
cd apps/api && uv sync --extra anthropic        # or: openai
# .env
LLM_MODEL=anthropic:claude-opus-5-5
ANTHROPIC_API_KEY=...
```

A user can also bring their own model and key: Settings in the dashboard
stores the choice in the browser and sends it with each search
(`llm: {model, api_key}` on `POST /api/investigations`). The key is kept in
Redis apart from the run, only until the worker picks the job up, and is never
written to the run or its events. `ALLOW_USER_LLM=false` refuses this; a
user-chosen server address is ignored unless `ALLOW_USER_LLM_BASE_URL=true`.

| file                   | what                                                            |
| ---------------------- | --------------------------------------------------------------- |
| `agents/llm.py`        | the only place that loads and calls the model (`get_chat_model`, `ask`) |
| `agents/prompts.py`    | every prompt                                                    |
| `agents/extraction.py` | article → entities and claims, and the checks on the answer     |
| `agents/leads.py`      | which entities deserve a search of their own                    |
| `agents/tools.py`      | the scrapers as tools, for the agent loop that is not built yet |

The model proposes; code decides what enters the graph. A claim read from an
article is kept only if its `quote` is found in that article, a name the
scrapers already have is linked to the existing entity, a relation the
registries already hold gains the article as a second source, and a new entity
is kept only if a kept claim is about it. Kept claims are `Reported` (0.6) or,
when the article itself reports an accusation, `Alleged` (0.4), and carry
their `quote`. The dashboard lists them under "AI reading".

Cost is bounded per search by `LLM_MAX_SOURCES` (default 8 articles, newest
first) and `LLM_MAX_SOURCE_CHARS`; the stage says in the run log how many it
read and how many statements it threw away. A model that is missing, down or
out of credit costs that step, never the search: the stage reports it and
falls back to the rule-based version. `uv run pytest` never calls a real model.

Status: runs end to end against a local `qwen2.5` (7B). A model that small
gets the main facts but mislabels some relations and drops others, so read
its claims as leads to check, not as findings. Not yet run against a cloud model.

### A worker that dies

The worker renews a heartbeat key every few seconds while it runs a job. When
an SSE stream has been quiet and the run is still "running" without a
heartbeat, the API marks it failed and says so on the stream
(`core.runs.fail_if_orphaned`), instead of leaving the browser waiting.

## Events (SSE `data:` is JSON: `{id, type, run_id, ts, data}`)

`run.queued` · `run.started` · `stage.started` · `stage.completed` ·
`scraper.started` · `scraper.completed` · `graph.patch` · `agent.message` ·
`agent.leads` · `agent.skipped` · `run.completed` · `run.failed`

`run.started` carries `llm: {model, ready, problem}`: which model the search
has, if any. `graph.patch` carries `entities`, `claims`, `sources` to upsert,
its `origin` (a scraper, or a stage: `resolve`, `discover`), `removed_entity_ids` for entities merged away by
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
