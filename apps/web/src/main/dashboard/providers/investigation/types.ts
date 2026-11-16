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
};

export type GraphPatch = {
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
    by: "heuristic" | "llm";
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
          { query: string; scrapers?: string[] }
      >
    | EventOf<
          "run.completed",
          { entities: number; claims: number; sources: number }
      >
    | EventOf<"run.failed", { error: string }>
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
