import { useEffect } from "react";
import { useShallow } from "zustand/react/shallow";
import { X } from "lucide-react";
import { cn } from "../../utils/util";
import { isLive, useInvestigation } from "../../providers/investigation/store";
import { runProgress } from "../../providers/investigation/progress";
import { openInvestigationWindow } from "../investigation/open";
import { ProgressBar } from "../investigation/ui";

function FurtherSearches({ parentKey }: { parentKey: string }) {
    const children = useInvestigation(
        useShallow((s) =>
            Object.values(s.runs).filter((run) => run.parentKey === parentKey),
        ),
    );
    if (children.length === 0) return null;

    return (
        <div className="mt-3 flex flex-col gap-2 border-t border-white/10 pt-2">
            {children.map((child) => {
                const { percent, text } = runProgress(child);
                return (
                    <div key={child.key} title={child.reason ?? text}>
                        <div className="flex items-baseline justify-between gap-2 text-xs">
                            <span className="min-w-0 truncate text-neutral-300">
                                ↳ {child.query}
                                {child.origin === "auto" && (
                                    <span className="ml-1.5 text-[10px] uppercase tracking-[1px] text-neutral-500">
                                        auto
                                    </span>
                                )}
                            </span>
                            <span
                                className={cn(
                                    "shrink-0 tabular-nums",
                                    child.phase === "failed"
                                        ? "text-[#f16035]"
                                        : "text-neutral-500",
                                )}
                            >
                                {child.phase === "failed"
                                    ? "failed"
                                    : `${percent}%`}
                            </span>
                        </div>
                        <ProgressBar run={child} className="mt-1" compact />
                    </div>
                );
            })}
        </div>
    );
}

function RunCard({ runKey }: { runKey: string }) {
    const run = useInvestigation((s) => s.runs[runKey]);
    const active = useInvestigation((s) => s.activeKey === runKey);
    const { select, dismiss } = useInvestigation.getState();
    if (!run) return null;

    const { text } = runProgress(run);
    const show = () => {
        select(runKey);
        openInvestigationWindow();
    };

    return (
        <div
            role="button"
            tabIndex={0}
            onClick={show}
            onKeyDown={(e) => e.key === "Enter" && show()}
            title="Show this search in the graph"
            className={cn(
                "group cursor-pointer rounded-xl border px-4 py-3 text-left transition-colors",
                active
                    ? "border-white/50 bg-white/5"
                    : "border-white/15 hover:border-white/30",
            )}
        >
            <div className="flex items-start justify-between gap-2">
                <span className="truncate text-sm font-semibold">
                    {run.query}
                </span>
                <button
                    type="button"
                    onClick={(e) => {
                        e.stopPropagation();
                        dismiss(runKey);
                    }}
                    title={
                        isLive(run.phase)
                            ? "Stop following this search"
                            : "Dismiss"
                    }
                    aria-label="Dismiss"
                    className="shrink-0 cursor-pointer rounded p-0.5 text-neutral-500 opacity-0 hover:text-white group-hover:opacity-100 focus:opacity-100"
                >
                    <X size={12} />
                </button>
            </div>
            <div
                className={cn(
                    "mt-1 truncate text-xs",
                    run.phase === "failed"
                        ? "text-[#f16035]"
                        : "text-neutral-400",
                )}
                title={text}
            >
                {text}
            </div>
            <ProgressBar run={run} className="mt-3" />
            <FurtherSearches parentKey={runKey} />
        </div>
    );
}

export default function RunCards() {
    const order = useInvestigation((s) => s.order);
    const busy = useInvestigation((s) =>
        Object.values(s.runs).some((run) => isLive(run.phase)),
    );

    useEffect(() => void useInvestigation.getState().restore(), []);

    return (
        <div className="mt-4 flex min-h-0 flex-1 flex-col border-t border-white/15 pt-4">
            <div className="mb-3 flex items-center gap-2 px-2 text-[11px] font-semibold uppercase tracking-[1px]">
                Searches
                <span
                    className={cn(
                        "size-2 rounded-full",
                        busy ? "animate-pulse bg-[#69ff94]" : "bg-neutral-600",
                    )}
                    title={busy ? "Workers are running" : "Idle"}
                />
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1 [scrollbar-color:#444_transparent] [scrollbar-width:thin]">
                {order.length === 0 && (
                    <div className="px-2 text-xs text-neutral-500">
                        Searches you start show up here with their progress.
                    </div>
                )}
                {order.map((key) => (
                    <RunCard key={key} runKey={key} />
                ))}
            </div>
        </div>
    );
}
