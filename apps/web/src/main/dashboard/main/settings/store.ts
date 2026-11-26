import { create } from "zustand";
import { persist } from "zustand/middleware";

// Preview settings: remembered in this browser, not yet sent to the API.
// The defaults mirror apps/api/src/core/config.py where a matching knob exists.
export const DEFAULTS = {
    investigation: {
        depth: 3, // max_agent_iterations
        leadsPerRound: 6, // max_leads
        sourcesPerRound: 8, // llm_max_sources
        autoFollow: true,
        ownershipChains: true,
        stopWhenStale: true,
        timeoutMinutes: 15, // job_timeout_seconds / 60
    },
    sources: {
        enabled: {
            onrc: true,
            anaf: true,
            portal_just: true,
            ani: true,
            seap: true,
            riseproject: true,
            recorder: true,
            zf: true,
            adevarul: true,
            digi24: true,
            g4media: true,
            hotnews: true,
        } as Record<string, boolean>,
        concurrency: 6, // scraper_concurrency
        timeoutSeconds: 90, // scraper_timeout_seconds
    },
    graph: {
        layout: "force" as "force" | "radial" | "tree",
        nodeSize: "connections" as "uniform" | "connections" | "revenue",
        edgeLabels: true,
        clusterByType: false,
        physics: true,
    },
    workspace: {
        openInvestigationOnStart: true,
        notifyOnFinish: true,
        sound: false,
        reducedMotion: false,
    },
    data: {
        cacheDays: 7 as 1 | 7 | 30 | 0,
        keepHistory: true,
    },
};

type Defaults = typeof DEFAULTS;
export type SectionKey = keyof Defaults;

type Store = Defaults & {
    tab: string;
    setTab: (tab: string) => void;
    /** Pages the user has opened, so their "new" dot goes away. */
    seen: string[];
    markSeen: (tab: string) => void;
    set: <K extends SectionKey>(key: K, patch: Partial<Defaults[K]>) => void;
    reset: (key: SectionKey) => void;
};

export const useSettings = create<Store>()(
    persist(
        (set) => ({
            ...DEFAULTS,
            tab: "model",
            setTab: (tab) => set({ tab }),
            seen: [],
            markSeen: (tab) =>
                set((s) => (s.seen.includes(tab) ? s : { seen: [...s.seen, tab] })),
            set: (key, patch) =>
                set((s) => ({ [key]: { ...s[key], ...patch } }) as Partial<Store>),
            reset: (key) => set({ [key]: DEFAULTS[key] } as Partial<Store>),
        }),
        {
            name: "synapse.settings",
            version: 1,
            partialize: ({ setTab, markSeen, set, reset, ...data }) => data,
            // Merge per section, so a setting added later gets its default
            // instead of vanishing behind an older saved copy of its section.
            merge: (saved, current) => {
                const s = (saved ?? {}) as Partial<
                    Defaults & { tab: string; seen: string[] }
                >;
                const out = {
                    ...current,
                    tab: s.tab ?? current.tab,
                    seen: s.seen ?? current.seen,
                };
                for (const k of Object.keys(DEFAULTS) as SectionKey[]) {
                    Object.assign(out, { [k]: { ...current[k], ...s[k] } });
                }
                out.sources.enabled = {
                    ...current.sources.enabled,
                    ...s.sources?.enabled,
                };
                return out;
            },
        },
    ),
);
