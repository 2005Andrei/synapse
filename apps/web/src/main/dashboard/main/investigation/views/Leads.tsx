import { useShallow } from "zustand/react/shallow";
import {
    isLive,
    useInvestigation,
    type RunState,
} from "../../../providers/investigation/store";
import { runProgress } from "../../../providers/investigation/progress";
import { Empty, Section, TypeBadge } from "../ui";

export default function Leads({ run }: { run: RunState }) {
    // Searches that already went further from an entity of this graph.
    const further = useInvestigation(
        useShallow((s) =>
            Object.values(s.runs).filter((r) => r.parentKey === run.key),
        ),
    );
    const expand = useInvestigation((s) => s.expand);

    return (
        <div className="flex flex-col gap-3">
            <div className="text-[#aaa]">
                People and companies worth a search of their own. The people who
                run a searched company come first, and the most senior of them
                is searched automatically. Results join this graph; you can
                also right-click any person or company in the graph.
            </div>

            {run.leads.length === 0 ? (
                <Empty>
                    {run.phase === "completed" || run.phase === "failed"
                        ? "No leads for this search."
                        : "Leads appear once the sources have answered."}
                </Empty>
            ) : (
                run.leads.map((lead) => {
                    const entity = run.entities[lead.entity_id];
                    const child = further.find(
                        (r) => r.entityId === lead.entity_id && r.phase !== "failed",
                    );
                    const waiting = lead.follow && !child && isLive(run.phase);
                    return (
                        <div
                            key={lead.entity_id}
                            className="flex items-start justify-between gap-3 border-b border-[#2a2a2a] pb-2"
                        >
                            <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className="break-words text-white">
                                        {lead.query}
                                    </span>
                                    <TypeBadge type={lead.entity_type} />
                                    {lead.role && (
                                        <span className="text-[10px] uppercase tracking-[1px] text-[#69ff94]">
                                            {lead.role}
                                        </span>
                                    )}
                                </div>
                                <div className="mt-0.5 text-[#888]">
                                    {lead.reason}
                                </div>
                            </div>
                            <button
                                type="button"
                                disabled={Boolean(child) || waiting || !entity}
                                onClick={() => entity && expand(run.key, entity)}
                                className="no-drag shrink-0 cursor-pointer rounded border border-[#ffd166]/60 px-2 py-1 text-[#ffd166] hover:bg-[#ffd166]/10 disabled:cursor-default disabled:border-[#444] disabled:text-[#666] disabled:hover:bg-transparent"
                            >
                                {child
                                    ? isLive(child.phase)
                                        ? `Searching ${runProgress(child).percent}%`
                                        : child.origin === "auto"
                                          ? "Searched (auto)"
                                          : "Searched"
                                    : waiting
                                      ? "Queued (auto)"
                                      : "Search further"}
                            </button>
                        </div>
                    );
                })
            )}

            {run.notes.length > 0 && (
                <Section title="Agent log">
                    {run.notes.map((note) => (
                        <div key={note} className="text-[#aaa]">
                            {note}
                        </div>
                    ))}
                </Section>
            )}
        </div>
    );
}
