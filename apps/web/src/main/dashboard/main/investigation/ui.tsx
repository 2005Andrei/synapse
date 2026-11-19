import type { ReactNode } from "react";
import { cn } from "../../utils/util";
import { ENTITY_COLORS } from "../graph/config";
import type { Phase, RunState } from "../../providers/investigation/store";
import { runProgress } from "../../providers/investigation/progress";

export const PHASE_STYLE: Record<Phase, string> = {
    starting: "text-[#ffd166]",
    queued: "text-[#ffd166]",
    running: "text-[#00d2ff]",
    completed: "text-[#69ff94]",
    failed: "text-[#f16035]",
};

const BAR_STYLE: Record<Phase, string> = {
    starting: "bg-[#ffd166]",
    queued: "bg-[#ffd166]",
    running: "bg-[#00d2ff]",
    completed: "bg-[#69ff94]",
    failed: "bg-[#f16035]",
};

export const seconds = (ms: number) => `${(ms / 1000).toFixed(1)}s`;

export const entityName = (entity?: {
    aliases: string[] | null;
    type: string;
}) => (entity ? (entity.aliases?.[0] ?? `Unnamed ${entity.type}`) : "?");

export function Section({
    title,
    children,
}: {
    title: string;
    children: ReactNode;
}) {
    return (
        <div className="border-t border-[#333] pt-3">
            <div className="mb-2 uppercase tracking-[1px] text-[#888]">
                {title}
            </div>
            {children}
        </div>
    );
}

export function Empty({ children }: { children: ReactNode }) {
    return <div className="py-6 text-center text-[#888]">{children}</div>;
}

export function ProgressBar({
    run,
    className,
    compact = false,
}: {
    run: RunState;
    className?: string;
    /** Bar only: the caller shows the percentage itself. */
    compact?: boolean;
}) {
    const { percent } = runProgress(run);
    return (
        <div className={cn("flex items-center gap-3", className)}>
            <div
                className="h-1 flex-1 overflow-hidden rounded-full bg-white/10"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percent}
            >
                <div
                    className={cn(
                        "h-full rounded-full transition-[width] duration-500 ease-out",
                        BAR_STYLE[run.phase],
                    )}
                    style={{ width: `${percent}%` }}
                />
            </div>
            {!compact && (
                <span className="w-8 shrink-0 text-right text-[10px] tabular-nums text-[#aaa]">
                    {percent}%
                </span>
            )}
        </div>
    );
}

export function TypeBadge({ type }: { type: string }) {
    const color =
        (ENTITY_COLORS as Record<string, string>)[type] ??
        (type === "Fact" || type === "Relation"
            ? "#9aa0a6"
            : ENTITY_COLORS.Default);
    return (
        <span
            className="inline-block whitespace-nowrap rounded-full border px-2 py-px text-[10px]"
            style={{
                color,
                borderColor: `${color}66`,
                backgroundColor: `${color}14`,
            }}
        >
            {type}
        </span>
    );
}
