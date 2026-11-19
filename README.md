# Synapse

This is a continuation of a previous project, still very much workin in progress, hopefully I'll be able to host a viable product in a week or two from now (28.11.26)

Current dev in on prototype branch, slowly working on it.

![demo 1](https://github.com/2005Andrei/synapse/blob/prototype/demo/demo-1.png)


![demo 2](https://github.com/2005Andrei/synapse/blob/prototype/demo/demo-2.png)


![demo 3](https://github.com/2005Andrei/synapse/blob/prototype/demo/demo-3.png)


## To do

What works today: a search (person, company or CUI) runs the scrapers in a
background worker, streams progress to the dashboard over SSE, merges
same-name records, keeps similar names apart, proposes follow-up searches and
shows everything as a graph plus tables by source. Details in
[apps/api/README.md](apps/api/README.md).

### Next big thing: company valuations

- [ ] A valuation connector in `apps/api/src/connectors`: given a company, find
      what it is worth according to public sources. Candidates: market
      capitalisation for listed companies (BVB), deal and valuation figures
      reported in the business press (ZF, Profit.ro), published transaction
      announcements.
- [ ] A `valuations` attribute on companies, next to `financials`:
      `{date, amount, currency, method, source_id}` with `method` one of
      market cap / transaction / reported / estimate, so a number never shows
      up without saying where it comes from.
- [ ] Let the model read amounts out of articles ("evaluată la 200 de milioane
      de euro"): extend `Statement` in `agents/extraction.py` with value,
      currency and date. The quote check already there applies as is.
- [ ] An own estimate from the ANAF statements (revenue / profit multiples per
      CAEN code), always labelled as an estimate.
- [ ] Run it for every company in a result, not only the one searched for.
- [ ] Chart valuation over time in the company window, under the financial charts.
- [x] Yearly revenue, net result and employees from ANAF, charted in the company window.

### Searching further

- [x] Right-click a person or company in the graph → "Search further"; results join the same graph.
- [x] After a company search, the people who run it are listed first and the top one is searched automatically.
- [ ] A further search only merges into the graph what shares an id with it;
      the same company found once by name and once by CUI can show up twice.
- [ ] Show on the node itself that it is being / has been searched further.
- [ ] Let the user choose how deep the automatic search goes (now: one person, one level).
- [ ] Search further from documents and other node types.

### LLM and the agent loop

- [x] Provider-neutral model seam (`LLM_MODEL`), prompts in one file, tests that never call a real model.
- [x] The model reads article texts and adds people, companies and claims, each
      with the quote that supports it; anything whose quote is not in the article is dropped.
- [x] Model-picked follow-up leads.
- [x] Local models through Ollama (`LLM_MODEL=ollama:qwen2.5`), with their own limits.
- [x] A user can bring their own model and API key (Settings); the key is not stored with the search.
- [ ] Ollama here runs on the CPU (the installed build has no GPU support):
      one to five minutes per article, and long articles time out. Install the GPU build.
- [ ] A 7B local model mislabels relations. Try a larger local model, and run
      the same articles through a cloud model to compare.
- [ ] Settings: let the user test the model and key before searching, and show
      which searches used which model.
- [ ] A small eval set (articles + the claims a careful reader would extract)
      before tuning the prompts, so changes can be measured.
- [ ] `evaluate` stage (stub today): grade claims against their sources, mark
      contradictions, set status / confidence, decide whether another round is worth it.
- [ ] Let the agent run follow-up scrapers itself (`agents/tools.py` has the
      scrapers as tools; nothing calls them yet).
- [ ] Summary per source and per entity.
- [ ] Token and cost accounting per search, shown in the overview.
- [ ] Long articles: split instead of cutting at `LLM_MAX_SOURCE_CHARS`.
- [ ] LangGraph checkpoints in Redis, so a search survives a worker restart.

### Entities

- [x] Exact name vs similar name: only exact names merge; similar ones are
      separate identities the user can fold in ("Same as search").
- [x] Same name, different date of birth (known from ONRC): kept apart.
- [ ] Same name and no date of birth on either side is still merged. Needs
      another signal: county, institution, who they appear with.
- [ ] "Same as search" is saved in the browser only; store it with the search.
- [ ] Company name variants: a court string like "SC DEDEMAN SRL BACĂU" is
      flagged as a similar name of "DEDEMAN SRL" although it is the same company.
- [ ] Attributes: fill in the typed attributes per entity type
      (`models/attributes.py`) and give each type a proper window, as companies now have.

### Sources

- [x] Company name → CUI and administrators, from ONRC's open data on
      data.gov.ro (`just onrc-import`): the same source demoanaf.ro uses.
- [ ] Build the full ONRC index (about 1 GB; only a two-company sample was
      built so far, for lack of disk space) and refresh it when ONRC publishes a new release.
- [ ] Shareholders are not in the open data. Candidates: Monitorul Oficial
      part IV, the beneficial-owners register, press.
- [ ] Company status (active, dissolved, insolvent) and CAEN codes from the
      other ONRC files (`od_stare_firma.csv`, `od_caen_autorizat.csv`).
- [ ] SEAP direct acquisitions: e-licitatie.ro answers 403; contracts only come with a `SICAP_API_KEY`.
- [ ] PDF reader and parser (ANI wealth and interest declarations, court decisions).
- [ ] Read the content of court files, not only the party lists.
- [ ] More press sources; recognise the same agency story republished by several sites.
- [ ] Cache scraper answers in Redis and rate-limit per upstream.

### Platform

- [ ] Storage: searches live in Redis for 24 hours. Needs a database for
      entities, claims and sources, and saved investigations.
- [ ] Accounts: the list of recent searches is shared by everyone who opens the app.
- [ ] Projects, Notes and Settings in the sidebar are placeholders.
- [ ] Cancel a running search.
- [ ] Export an investigation (PDF / CSV).
- [ ] The Docker stack (`just dev`) has not been run end to end; then hosting.

### Frontend

- [ ] The graph shows mock data until the first search; replace with an empty state.
- [ ] Windows are see-through, which makes overlapping ones hard to read.
- [ ] `bun run build` fails on type errors in the untyped graph files, and
      eslint does not support TypeScript 7 yet. `vite build` passes.
- [ ] Phone layout.
