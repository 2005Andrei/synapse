import type { ComponentType } from "react";
import { cn } from "../../utils/util";
import { useSidebar } from "../../providers/DashboardContext";
import {
    useActiveRun,
    type RunState,
} from "../../providers/investigation/store";
import { VIEWS, type ViewId } from "../../providers/views";
import { PHASE_STYLE } from "./ui";
import Connections from "./views/Connections";
import DataBySource from "./views/DataBySource";
import Files from "./views/Files";
import Leads from "./views/Leads";
import Overview from "./views/Overview";

const BODY: Record<ViewId, ComponentType<{ run: RunState }>> = {
    about: Overview,
    index: DataBySource,
    files: Files,
    map: Connections,
    submit: Leads,
};

export default function InvestigationPanel() {
    const { activeView, setActiveView } = useSidebar();
    const run = useActiveRun();

    const view = VIEWS.find((v) => v.id === activeView) ?? VIEWS[3];
    const Body = BODY[view.id];

    return (
        <div className="@container flex h-full flex-col text-left font-mono text-[12px] text-[#ececec]">
            <div className="shrink-0 px-5 pt-4">
                <div className="flex items-baseline justify-between gap-3">
                    <h3 className="m-0 truncate text-[14px]" title={run?.query}>
                        {run?.query ?? "No search yet"}
                    </h3>
                    {run && (
                        <span
                            className={cn(
                                "shrink-0 uppercase tracking-[1px]",
                                PHASE_STYLE[run.phase],
                            )}
                        >
                            {run.phase}
                        </span>
                    )}
                </div>

                <div className="no-drag mt-3 flex gap-4 border-b border-[#333] text-[11px] tracking-[1px]">
                    {VIEWS.map((v) => (
                        <button
                            key={v.id}
                            type="button"
                            title={v.hint}
                            onClick={() => setActiveView(v.id)}
                            className={cn(
                                "-mb-px cursor-pointer border-b pb-1.5",
                                v.id === view.id
                                    ? "border-white text-white"
                                    : "border-transparent text-[#888] hover:text-white",
                            )}
                        >
                            {v.label}
                        </button>
                    ))}
                </div>
                <div className="mt-2 text-[10px] uppercase tracking-[1px] text-[#666]">
                    {view.hint}
                </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col overflow-auto px-5 pb-5 pt-2 [scrollbar-color:#444_transparent] [scrollbar-width:thin]">
                {run ? (
                    <Body run={run} />
                ) : (
                    <div className="text-[#888]">
                        Type a company, a person or a CUI in the search bar and
                        press Enter to start an investigation.
                    </div>
                )}
            </div>
        </div>
    );
}
