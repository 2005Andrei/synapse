import { create } from "zustand";
import {
    createInvestigation,
    followInvestigation,
    forgetInvestigation,
    listInvestigations,
} from "./api";
import type {
    Claim,
    Entity,
    GraphPatch,
    Lead,
    RunEvent,
    ScraperReport,
    Source,
    LlmStatus,
    Run,
} from "./types";

export type Phase = "starting" | "queued" | "running" | "completed" | "failed";

export type Stage = {
    key: string;
    stage: string;
    iteration: number;
    durationMs: number | null; // null while it is still running
};

/** Everything known about one investigation (one search = one worker job). */
export type RunState = {
    /** Local id: exists before the API has answered with `runId`. */
    key: string;
    runId: string | null;
    query: string;
    phase: Phase;
    error: string | null;
    startedAt: number;

    stages: Stage[];
    /** Scrapers this run will use, in order; known once the API accepts it. */
    scraperNames: string[];
    scrapers: Record<string, ScraperReport>;
    notes: string[];
    leads: Lead[];

    entities: Record<string, Entity>;
    claims: Record<string, Claim>;
    sources: Record<string, Source>;
    seedId: string | null;
    /** Which scrapers reported each record (entity / claim / source id). */
    origins: Record<string, string[]>;
    /** Show only one identity of the results (see identities.ts); null = all. */
    focus: string | null;
    /** Similar-name entities the user confirmed are the subject itself. */
    joined: string[];
    /** The chat model the worker ran this search with; null until it starts. */
    llm: LlmStatus | null;

    /** "Search further": this run extends the graph of the run `parentKey`,
     *  starting from that graph's entity `entityId`. */
    parentKey: string | null;
    entityId: string | null;
    origin: "user" | "auto";
    reason: string | null;
    /** Entity ids this graph merged away -> the entity that replaced them. */
    redirects: Record<string, string>;
};

type State = {
    runs: Record<string, RunState>;
    /** Keys of the searches the user started, newest first. Runs that search
     *  one of their entities further are found through `parentKey`. */
    order: string[];
    /** The run the graph and the investigation window are showing. */
    activeKey: string | null;

    start: (query: string) => string;
    /** Search an entity of a run's graph further; results join that graph. */
    expand: (key: string, entity: Entity) => string | null;
    /** Bring back the recent searches after a page (re)load. */
    restore: () => Promise<void>;
    select: (key: string) => void;
    setFocus: (key: string, identity: string | null) => void;
    /** Confirm (or take back) that a similar name is the subject itself. */
    toggleJoined: (key: string, entityId: string) => void;
    dismiss: (key: string) => void;
};

const newRun = (key: string, query: string): RunState => ({
    key,
    runId: null,
    query,
    phase: "starting",
    error: null,
    startedAt: Date.now(),
    stages: [],
    scraperNames: [],
    scrapers: {},
    notes: [],
    leads: [],
    entities: {},
    claims: {},
    sources: {},
    seedId: null,
    origins: {},
    focus: null,
    joined: [],
    llm: null,
    parentKey: null,
    entityId: null,
    origin: "user",
    reason: null,
    redirects: {},
});

// "same person" decisions are the user's own judgement, not pipeline output: - at the moment at least, AI pipeline should fix that
// they are kept in this browser, per run, until there are accounts to hold them.
const joinedKey = (runId: string) => `synapse:joined:${runId}`;

function loadJoined(runId: string): string[] {
    try {
        const stored = JSON.parse(
            localStorage.getItem(joinedKey(runId)) ?? "[]",
        );
        return Array.isArray(stored)
            ? stored.filter((id) => typeof id === "string")
            : [];
    } catch {
        return [];
    }
}

function saveJoined(runId: string, joined: string[]): void {
    try {
        if (joined.length)
            localStorage.setItem(joinedKey(runId), JSON.stringify(joined));
        else localStorage.removeItem(joinedKey(runId));
    } catch {
        // Storage unavailable (private window): the choice lasts until reload.
    }
}

export const isLive = (phase: Phase) =>
    phase !== "completed" && phase !== "failed";

const connections = new Map<string, () => void>();
let counter = 0;
let restored = false;

export const useInvestigation = create<State>((set, get) => {
    const patch = (key: string, change: (run: RunState) => Partial<RunState>) =>
        set((s) => {
            const run = s.runs[key];
            return run
                ? { runs: { ...s.runs, [key]: { ...run, ...change(run) } } }
                : s;
        });

    /** Start showing a run that extends another one's graph. */
    const adopt = (run: Run): string | null => {
        const { runs } = get();
        const known = Object.values(runs).find((r) => r.runId === run.id);
        if (known) return known.key;
        const parent = Object.values(runs).find((r) => r.runId === run.parent_id);
        if (!parent) return null;

        const key = `run-${++counter}`;
        const child: RunState = {
            ...newRun(key, run.query),
            runId: run.id,
            phase: run.status,
            error: run.error,
            scraperNames: run.scrapers,
            startedAt: Date.parse(run.created_at) || Date.now(),
            parentKey: parent.key,
            entityId: run.seed?.id ?? null,
            origin: run.origin,
            reason: run.reason,
        };
        set((s) => ({ runs: { ...s.runs, [key]: child } }));
        follow(key, run.id);
        return key;
    };

    const follow = (key: string, runId: string) =>
        connections.set(
            key,
            followInvestigation(
                runId,
                (event) => {
                    if (event.type === "run.spawned") adopt(event.data.run);
                    patch(key, (r) => reduce(r, event));
                    // What a further search finds belongs to the graph it started from.
                    const parentKey = get().runs[key]?.parentKey;
                    if (parentKey && event.type === "graph.patch")
                        patch(parentKey, (parent) => absorb(parent, event.data));
                },
                () =>
                    patch(key, (r) =>
                        isLive(r.phase)
                            ? {
                                  phase: "failed",
                                  error: "lost connection to the API",
                              }
                            : {},
                    ),
            ),
        );

    return {
        runs: {},
        order: [],
        activeKey: null,

        restore: async () => {
            if (restored) return;
            restored = true;

            const recent = await listInvestigations().catch(() => []);
            if (recent.length === 0) return;

            // A further search whose parent is gone stands on its own.
            const ids = new Set(recent.map((run) => run.id));
            const further = recent.filter(
                (run) => run.parent_id && ids.has(run.parent_id),
            );
            const found = recent
                .filter((run) => !further.includes(run))
                .map((run) => ({
                    ...newRun(`run-${++counter}`, run.query),
                    runId: run.id,
                    phase: run.status,
                    error: run.error,
                    scraperNames: run.scrapers,
                    joined: loadJoined(run.id),
                    startedAt: Date.parse(run.created_at) || Date.now(),
                }));
            set((s) => ({
                runs: {
                    ...s.runs,
                    ...Object.fromEntries(found.map((run) => [run.key, run])),
                },
                order: [...s.order, ...found.map((run) => run.key)],
                activeKey: s.activeKey ?? found[0].key,
            }));
            for (const run of found) follow(run.key, run.runId);
            // Oldest first, so cards keep the order the searches were made in.
            for (const run of further.reverse()) adopt(run);
        },

        expand: (key, entity) => {
            const parent = get().runs[key];
            const name = entity.aliases?.[0];
            if (!parent?.runId || !name) return null;
            const again = Object.values(get().runs).find(
                (r) =>
                    r.parentKey === key &&
                    r.entityId === entity.id &&
                    r.phase !== "failed",
            );
            if (again) return again.key; // already searched, or being searched

            const childKey = `run-${++counter}`;
            set((s) => ({
                runs: {
                    ...s.runs,
                    [childKey]: {
                        ...newRun(childKey, name),
                        parentKey: key,
                        entityId: entity.id,
                    },
                },
            }));
            createInvestigation(name, { parentId: parent.runId, seed: entity })
                .then((run) => {
                    if (!get().runs[childKey]) return;
                    patch(childKey, () => ({
                        runId: run.id,
                        phase: "queued",
                        scraperNames: run.scrapers,
                    }));
                    follow(childKey, run.id);
                })
                .catch((error: unknown) =>
                    patch(childKey, () => ({
                        phase: "failed",
                        error:
                            error instanceof TypeError
                                ? "API is not reachable"
                                : (error as Error).message,
                    })),
                );
            return childKey;
        },

        start: (query) => {
            const key = `run-${++counter}`;
            set((s) => ({
                runs: { ...s.runs, [key]: newRun(key, query) },
                order: [key, ...s.order],
                activeKey: key,
            }));

            createInvestigation(query)
                .then((run) => {
                    if (!get().runs[key]) return; // dismissed while starting
                    patch(key, () => ({
                        runId: run.id,
                        phase: "queued",
                        scraperNames: run.scrapers,
                    }));
                    follow(key, run.id);
                })
                .catch((error: unknown) =>
                    patch(key, () => ({
                        phase: "failed",
                        error:
                            error instanceof TypeError
                                ? "API is not reachable"
                                : (error as Error).message,
                    })),
                );

            return key;
        },

        select: (key) => set((s) => (s.runs[key] ? { activeKey: key } : s)),

        setFocus: (key, identity) => patch(key, () => ({ focus: identity })),

        toggleJoined: (key, entityId) =>
            patch(key, (run) => {
                const joined = run.joined.includes(entityId)
                    ? run.joined.filter((id) => id !== entityId)
                    : [...run.joined, entityId];
                if (run.runId) saveJoined(run.runId, joined);
                // the identity that was in focus may just have been folded away.
                return {
                    joined,
                    focus: run.focus === entityId ? null : run.focus,
                };
            }),

        dismiss: (key) => {
            const gone = [
                key,
                ...Object.values(get().runs)
                    .filter((r) => r.parentKey === key)
                    .map((r) => r.key),
            ];
            for (const each of gone) {
                connections.get(each)?.();
                connections.delete(each);
                const runId = get().runs[each]?.runId;
                if (runId) forgetInvestigation(runId);
            }
            set((s) => {
                const runs = { ...s.runs };
                for (const each of gone) delete runs[each];
                const order = s.order.filter((k) => k !== key);
                return {
                    runs,
                    order,
                    activeKey:
                        s.activeKey === key ? (order[0] ?? null) : s.activeKey,
                };
            });
        },
    };
});

/** The run currently shown in the graph and the investigation window. */
export const useActiveRun = (): RunState | null =>
    useInvestigation((s) =>
        s.activeKey ? (s.runs[s.activeKey] ?? null) : null,
    );

/**
 * Apply one run event. Every case is an upsert, so replaying events (which
 * happens after a reconnect) is harmless.
 */
function reduce(run: RunState, event: RunEvent): Partial<RunState> {
    switch (event.type) {
        case "run.queued":
            return { phase: "queued" };

        case "run.started":
            return {
                phase: "running",
                scraperNames: event.data.scrapers ?? run.scraperNames,
                llm: event.data.llm ?? run.llm,
            };

        case "run.completed":
            return { phase: "completed" };

        case "run.failed":
            return { phase: "failed", error: event.data.error };

        case "stage.started":
        case "stage.completed": {
            const { stage, iteration } = event.data;
            const entry: Stage = {
                key: `${stage}:${iteration}`,
                stage,
                iteration,
                durationMs:
                    event.type === "stage.completed"
                        ? event.data.duration_ms
                        : null,
            };
            const known = run.stages.some((x) => x.key === entry.key);
            return {
                stages: known
                    ? run.stages.map((x) => (x.key === entry.key ? entry : x))
                    : [...run.stages, entry],
            };
        }

        case "scraper.started":
        case "scraper.completed":
            return {
                scrapers: { ...run.scrapers, [event.data.scraper]: event.data },
            };

        case "graph.patch":
            return applyPatch(run, event.data);

        case "agent.skipped":
            return addNote(
                run,
                `${event.data.agent}: skipped (${event.data.reason})`,
            );

        case "agent.message":
            return addNote(run, `${event.data.agent}: ${event.data.text}`);

        case "agent.leads":
            return { leads: event.data.leads };

        default:
            return {};
    }
}

const addNote = (run: RunState, note: string): Partial<RunState> =>
    run.notes.includes(note) ? {} : { notes: [...run.notes, note] };

const PIPELINE_ORIGINS = new Set(["plan", "resolve"]);

function applyPatch(run: RunState, patch: GraphPatch): Partial<RunState> {
    const entities = { ...run.entities };
    const claims = { ...run.claims };
    const sources = { ...run.sources };
    const origins = { ...run.origins };

    const credit = (id: string, names: string[]) => {
        const known = origins[id] ?? [];
        const added = names.filter((name) => !known.includes(name));
        if (added.length) origins[id] = [...known, ...added];
    };

    for (const id of patch.removed_entity_ids ?? []) delete entities[id];
    for (const entity of patch.entities)
        entities[entity.id] = mergeEntity(entities[entity.id], entity);
    for (const claim of patch.claims) claims[claim.id] = claim;
    for (const source of patch.sources) sources[source.id] = source;

    if (!PIPELINE_ORIGINS.has(patch.origin)) {
        for (const kind of [patch.entities, patch.claims, patch.sources])
            for (const record of kind) credit(record.id, [patch.origin]);
    }
    // a merged entity was found by everyone who found any of its parts.
    for (const [from, into] of Object.entries(patch.merged ?? {}))
        credit(into, origins[from] ?? []);

    return {
        entities,
        claims,
        sources,
        origins,
        seedId: patch.seed_id ?? run.seedId,
        redirects: patch.merged
            ? { ...run.redirects, ...patch.merged }
            : run.redirects,
    };
}

/** Two registries describe one company under one id: keep what both know. */
function mergeEntity(known: Entity | undefined, incoming: Entity): Entity {
    if (!known) return incoming;
    return {
        ...incoming,
        description: incoming.description || known.description,
        aliases: [...new Set([...(known.aliases ?? []), ...(incoming.aliases ?? [])])],
        attributes: { ...known.attributes, ...incoming.attributes },
    };
}

/**
 * Take a patch from a run that searches one of this graph's entities further.
 * This graph may already have merged a record the other run reports again
 * (same scraper, same name, same id), so ids go through `redirects` first.
 * The subject of the graph stays what it was.
 */
function absorb(run: RunState, patch: GraphPatch): Partial<RunState> {
    const now = (id: string) => {
        for (let hops = 0; run.redirects[id] && hops < 8; hops++)
            id = run.redirects[id];
        return id;
    };
    const ids = (list: string[]) => [...new Set(list.map(now))];
    return applyPatch(run, {
        ...patch,
        seed_id: undefined,
        entities: patch.entities.map((entity) => ({ ...entity, id: now(entity.id) })),
        claims: patch.claims.map((claim) => ({
            ...claim,
            subject_ids: ids(claim.subject_ids),
            reference_ids: ids(claim.reference_ids),
        })),
        // Never drop a node this graph merged other records into.
        removed_entity_ids: (patch.removed_entity_ids ?? []).filter(
            (id) => now(id) === id && !Object.values(run.redirects).includes(id),
        ),
    });
}
