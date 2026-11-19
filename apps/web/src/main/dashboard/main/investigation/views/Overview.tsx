import { cn } from "../../../utils/util";
import type { RunState } from "../../../providers/investigation/store";
import { useMemo } from "react";
import { divide } from "../../../providers/investigation/identities";
import { runProgress } from "../../../providers/investigation/progress";
import type { ScraperReport } from "../../../providers/investigation/types";
import { ProgressBar, Section, seconds } from "../ui";

function ScraperRow({ report }: { report: ScraperReport }) {
    const running = report.status === undefined;
    const found = report.counts
        ? report.counts.entities + report.counts.sources
        : 0;
    const remarks = [report.error, ...(report.metadata?.notes ?? [])].filter(
        Boolean,
    );

    return (
        <div className="mb-1">
            <div className="flex items-baseline justify-between gap-3">
                <span className="truncate">{report.label}</span>
                <span
                    className={cn(
                        "shrink-0",
                        running && "animate-pulse text-[#00d2ff]",
                        report.status === "ok" && "text-[#69ff94]",
                        report.status === "empty" && "text-[#888]",
                        report.status === "error" && "text-[#f16035]",
                    )}
                >
                    {running
                        ? "running"
                        : report.status === "ok"
                          ? `${found} found · ${seconds(report.duration_ms ?? 0)}`
                          : report.status}
                </span>
            </div>
            {remarks.map((remark) => (
                <div key={remark} className="pl-3 text-[11px] text-[#888]">
                    {remark}
                </div>
            ))}
        </div>
    );
}

export default function Overview({ run }: { run: RunState }) {
    const { text } = runProgress(run);
    const reports = Object.values(run.scrapers);
    const similar = useMemo(
        () =>
            divide(run).identities.filter(
                (identity) => identity.kind === "similar",
            ),
        [run],
    );

    return (
        <div className="flex flex-col gap-3">
            <div>
                <ProgressBar run={run} />
                <div
                    className={cn(
                        "mt-1 text-[#aaa]",
                        run.phase === "failed" && "text-[#f16035]",
                    )}
                >
                    {text}
                </div>
            </div>
            <div className="text-[#aaa]">
                {Object.keys(run.entities).length} entities ·{" "}
                {Object.keys(run.claims).length} claims ·{" "}
                {Object.keys(run.sources).length} sources
            </div>
            {run.llm && (
                <div className="text-[#aaa]" title={run.llm.problem ?? undefined}>
                    AI:{" "}
                    {run.llm.ready ? (
                        <span className="text-white">{run.llm.model}</span>
                    ) : run.llm.model ? (
                        <span className="text-[#f16035]">
                            {run.llm.model} could not be loaded; running without it
                        </span>
                    ) : (
                        "off (rule-based; set LLM_MODEL on the worker to read articles)"
                    )}
                </div>
            )}
            {similar.length > 0 && (
                <div className="rounded border border-[#ffd166]/40 bg-[#ffd166]/5 px-3 py-2 text-[#ffd166]">
                    {similar.length} similar name{similar.length > 1 ? "s" : ""}{" "}
                    found (
                    {similar
                        .slice(0, 3)
                        .map((identity) => identity.name)
                        .join(", ")}
                    {similar.length > 3 && "…"}). They are kept apart from the
                    search’s own results: see MAP.
                </div>
            )}

            {run.stages.length > 0 && (
                <Section title="Pipeline">
                    {run.stages.map((stage) => (
                        <div
                            key={stage.key}
                            className="flex justify-between gap-3"
                        >
                            <span>
                                {stage.stage}
                                {stage.iteration > 0 &&
                                    ` #${stage.iteration + 1}`}
                            </span>
                            <span
                                className={
                                    stage.durationMs === null
                                        ? "animate-pulse text-[#00d2ff]"
                                        : "text-[#888]"
                                }
                            >
                                {stage.durationMs === null
                                    ? "running"
                                    : seconds(stage.durationMs)}
                            </span>
                        </div>
                    ))}
                </Section>
            )}

            {reports.length > 0 && (
                <Section title="Scrapers">
                    {reports.map((report) => (
                        <ScraperRow key={report.scraper} report={report} />
                    ))}
                </Section>
            )}
        </div>
    );
}
