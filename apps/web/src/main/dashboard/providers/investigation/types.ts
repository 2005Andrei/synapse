// follows apps/api: models/schemas.py, core/events.py, core/runs.py.

export type Entity = {
    id: string;
    type: string;
    description: string;
    aliases: string[] | null;
    attributes: Record<string, unknown>;
};

export type Claim = {
    id: string;
    type: string;
    subject_ids: string[];
    predicate: string;
    claim_text: string;
    reference_ids: string[];
    source_ids: string[];
    /** The passage of the source that supports the claim (model-read claims). */
    quote?: string | null;
    claim_status: string;
    confidence: number | null;
};

export type Source = {
    id: string;
    type: string;
    title: string;
    url: string;
    publisher: string | null;
    published_at: string | null;
    content: string;
    content_length?: number;
    language: string;
};

export type RunStatus = "queued" | "running" | "completed" | "failed";

export type Run = {
    id: string;
    query: string;
    scrapers: string[];
    status: RunStatus;
    error: string | null;
    created_at: string;
    /** Set when the run searches an entity of another run's graph further. */
    parent_id: string | null;
    seed: Entity | null;
    origin: "user" | "auto";
    reason: string | null;
};

/** A model the user chose for their searches (kept in this browser). */
export type LlmChoice = { model: string; api_key?: string; base_url?: string };

/** Which chat model a run has, if any (apps/api: agents/llm.py). */
export type LlmStatus = {
    model: string | null;
    ready: boolean;
    problem: string | null;
    local?: boolean;
    chosen_by?: "server" | "user";
};

export type GraphPatch = {
    /** A scraper's name, or a stage: "resolve", "discover" (read by the model). */
    origin: string;
    entities: Entity[];
    claims: Claim[];
    sources: Source[];
    removed_entity_ids?: string[];
    merged?: Record<string, string>;
    seed_id?: string;
};

export type ScraperReport = {
    scraper: string;
    label: string;
    status?: "ok" | "empty" | "error";
    error?: string | null;
    duration_ms?: number;
    counts?: { entities: number; claims: number; sources: number };
    metadata?: { notes?: string[] } & Record<string, unknown>;
};

export type Lead = {
    query: string;
    entity_id: string;
    entity_type: string;
    reason: string;
    score: number;
    by: "heuristic" | "llm" | "role";
    /** "officer": holds a role in the searched company. */
    kind?: "officer";
    role?: string;
    /** The pipeline searches this one further by itself. */
    follow?: boolean;
};

type EventOf<T extends string, D> = {
    id: string;
    type: T;
    run_id: string;
    ts: string;
    data: D;
};

export type RunEvent =
    | EventOf<
          "run.queued" | "run.started",
          { query: string; scrapers?: string[]; llm?: LlmStatus }
      >
    | EventOf<
          "run.completed",
          { entities: number; claims: number; sources: number }
      >
    | EventOf<"run.failed", { error: string }>
    | EventOf<"run.spawned", { run: Run; reason: string }>
    | EventOf<"stage.started", { stage: string; iteration: number }>
    | EventOf<
          "stage.completed",
          { stage: string; iteration: number; duration_ms: number }
      >
    | EventOf<"scraper.started" | "scraper.completed", ScraperReport>
    | EventOf<"graph.patch", GraphPatch>
    | EventOf<"agent.skipped", { agent: string; reason: string }>
    | EventOf<"agent.message", { agent: string; text: string }>
    | EventOf<"agent.leads", { agent: string; by: Lead["by"]; leads: Lead[] }>;
