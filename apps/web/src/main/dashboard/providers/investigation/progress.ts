import type { RunState } from "./store";

// share of the bar each pipeline stage ends at - scraping is nearly all of the
// wall-clock time, so it gets nearly all of the bar.
const STAGE_END: Record<string, number> = {
    plan: 5,
    scrape: 85,
    resolve: 90,
    discover: 95,
    evaluate: 98,
};
const STAGE_TEXT: Record<string, string> = {
    plan: "Planning…",
    resolve: "Resolving entities…",
    discover: "Looking for leads…",
    evaluate: "Evaluating…",
};

export type Progress = { percent: number; text: string };

export function runProgress(run: RunState): Progress {
    const reports = Object.values(run.scrapers);
    const total = run.scraperNames.length || reports.length;
    const finished = reports.filter((r) => r.status !== undefined);

    switch (run.phase) {
        case "starting":
            return { percent: 1, text: "Sending…" };
        case "queued":
            return { percent: 2, text: "Queued, waiting for a worker…" };
        case "failed":
            return { percent: 100, text: run.error ?? "Failed" };
        case "completed": {
            const failed = finished.filter((r) => r.status === "error").length;
            const found = `${Object.keys(run.entities).length} entities`;
            return {
                percent: 100,
                text: failed
                    ? `Done · ${found} · ${failed} source(s) failed`
                    : `Done · ${found}`,
            };
        }
    }

    const stage = run.stages[run.stages.length - 1];
    if (!stage) return { percent: 3, text: "Starting…" };

    if (stage.stage === "scrape" && stage.durationMs === null) {
        const share = total ? finished.length / total : 0;
        const waiting = reports
            .filter((r) => r.status === undefined)
            .map((r) => r.label);
        return {
            percent: Math.round(
                STAGE_END.plan + (STAGE_END.scrape - STAGE_END.plan) * share,
            ),
            text:
                `Scraping ${finished.length}/${total}` +
                (waiting.length
                    ? ` · ${waiting.slice(0, 2).join(", ")}${waiting.length > 2 ? "…" : ""}`
                    : ""),
        };
    }

    const end = STAGE_END[stage.stage] ?? 50;
    return {
        percent: stage.durationMs === null ? end - 3 : end,
        text: STAGE_TEXT[stage.stage] ?? `${stage.stage}…`,
    };
}
