import { useShallow } from "zustand/react/shallow";
import {
    useInvestigation,
    type RunState,
} from "../../../providers/investigation/store";
import { Empty, Section, TypeBadge } from "../ui";

export default function Leads({ run }: { run: RunState }) {
    const queries = useInvestigation(
        useShallow((s) =>
            s.order.map((key) => s.runs[key].query.toLowerCase()),
        ),
    );
    const start = useInvestigation((s) => s.start);

    return (
        <div className="flex flex-col gap-3">
            <div className="text-[#aaa]">
                People and companies that came up in this search and may deserve
                one of their own. Submitting a lead starts a new search on a
                separate worker.
            </div>

            {run.leads.length === 0 ? (
                <Empty>
                    {run.phase === "completed" || run.phase === "failed"
                        ? "No leads for this search."
                        : "Leads appear once the sources have answered."}
                </Empty>
            ) : (
                run.leads.map((lead) => {
                    const submitted = queries.includes(
                        lead.query.toLowerCase(),
                    );
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
                                </div>
                                <div className="mt-0.5 text-[#888]">
                                    {lead.reason}
                                </div>
                            </div>
                            <button
                                type="button"
                                disabled={submitted}
                                onClick={() => start(lead.query)}
                                className="no-drag shrink-0 cursor-pointer rounded border border-[#ffd166]/60 px-2 py-1 text-[#ffd166] hover:bg-[#ffd166]/10 disabled:cursor-default disabled:border-[#444] disabled:text-[#666] disabled:hover:bg-transparent"
                            >
                                {submitted ? "Submitted" : "Investigate"}
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
