import { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "../../utils/util";
import { isLive, useInvestigation } from "../../providers/investigation/store";
import { runProgress } from "../../providers/investigation/progress";
import { openInvestigationWindow } from "../investigation/open";
import { ProgressBar } from "../investigation/ui";

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
        </div>
    );
}

export default function RunCards() {
    const order = useInvestigation((s) => s.order);
    const busy = useInvestigation((s) =>
        s.order.some((key) => isLive(s.runs[key].phase)),
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
