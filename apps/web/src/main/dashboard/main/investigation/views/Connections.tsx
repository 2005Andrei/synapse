import { useMemo } from "react";
import { cn } from "../../../utils/util";
import {
    useInvestigation,
    type RunState,
} from "../../../providers/investigation/store";
import {
    NAME_LINKS,
    divide,
    identityLabel,
} from "../../../providers/investigation/identities";
import { ENTITY_COLORS } from "../../graph/config";
import { Empty, Section, entityName } from "../ui";

const colorOf = (type?: string) =>
    (ENTITY_COLORS as Record<string, string>)[type ?? ""] ??
    ENTITY_COLORS.Default;

export default function Connections({ run }: { run: RunState }) {
    const setFocus = useInvestigation((s) => s.setFocus);
    const toggleJoined = useInvestigation((s) => s.toggleJoined);
    const { identities, groupOf } = useMemo(() => divide(run), [run]);

    const types = useMemo(() => {
        const counts = new Map<string, number>();
        for (const entity of Object.values(run.entities))
            counts.set(entity.type, (counts.get(entity.type) ?? 0) + 1);
        return [...counts.entries()].sort((a, b) => b[1] - a[1]);
    }, [run.entities]);

    const edges = useMemo(
        () =>
            Object.values(run.claims)
                .filter(
                    (claim) =>
                        claim.reference_ids.length > 0 &&
                        !NAME_LINKS.has(claim.predicate),
                )
                .filter(
                    (claim) =>
                        !run.focus ||
                        groupOf[claim.subject_ids[0]] === run.focus,
                )
                .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0)),
        [run.claims, run.focus, groupOf],
    );

    if (types.length === 0) return <Empty>Nothing on the map yet.</Empty>;

    const node = (id: string) => {
        const entity = run.entities[id];
        return (
            <span
                style={{ color: colorOf(entity?.type) }}
                title={entity?.description}
            >
                {entityName(entity)}
            </span>
        );
    };

    return (
        <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-x-4 gap-y-1">
                {types.map(([type, count]) => (
                    <span key={type} className="flex items-center gap-1.5">
                        <span
                            className="size-2 rounded-full"
                            style={{ backgroundColor: colorOf(type) }}
                        />
                        {type} <span className="text-[#888]">{count}</span>
                    </span>
                ))}
            </div>

            <Section title="Who is who">
                <div className="mb-2 text-[#888]">
                    Only an exact name counts as the subject of the search.
                    Similar names are kept apart, each with its own records,
                    until you say they are the same. “Only this” shows one of
                    them alone in the graph.
                </div>
                {identities.map((identity) => {
                    const focused = run.focus === identity.id;
                    return (
                        <div
                            key={identity.id}
                            className="flex items-center justify-between gap-3 border-b border-[#2a2a2a] py-1.5"
                        >
                            <div className="min-w-0">
                                <div
                                    className={cn(
                                        "text-[10px] uppercase tracking-[1px]",
                                        identity.kind === "subject" &&
                                            "text-[#69ff94]",
                                        identity.kind === "similar" &&
                                            "text-[#ffd166]",
                                        identity.kind === "other" &&
                                            "text-[#888]",
                                    )}
                                >
                                    {identityLabel(identity)}
                                    {identity.note && (
                                        <span className="ml-2 normal-case tracking-normal text-[#888]">
                                            {identity.note}
                                        </span>
                                    )}
                                </div>
                                <div className="break-words text-white">
                                    {identity.name}
                                </div>
                                {identity.joined.map((same) => (
                                    <button
                                        key={same.id}
                                        type="button"
                                        onClick={() =>
                                            toggleJoined(run.key, same.id)
                                        }
                                        title="Separate again"
                                        className="no-drag mr-2 mt-1 cursor-pointer rounded border border-[#69ff94]/40 px-1.5 text-[#69ff94] hover:border-[#f16035] hover:text-[#f16035]"
                                    >
                                        + {same.name} ✕
                                    </button>
                                ))}
                            </div>
                            <div className="flex shrink-0 items-center gap-3">
                                <span className="tabular-nums text-[#888]">
                                    {identity.entityIds.length} record
                                    {identity.entityIds.length === 1 ? "" : "s"}
                                </span>
                                {identity.kind === "similar" && (
                                    <button
                                        type="button"
                                        onClick={() =>
                                            toggleJoined(run.key, identity.id)
                                        }
                                        title="Count this name's records as the subject's"
                                        className="no-drag cursor-pointer rounded border border-[#555] px-2 py-0.5 text-[#aaa] hover:border-[#69ff94] hover:text-[#69ff94]"
                                    >
                                        Same as search
                                    </button>
                                )}
                                <button
                                    type="button"
                                    onClick={() =>
                                        setFocus(
                                            run.key,
                                            focused ? null : identity.id,
                                        )
                                    }
                                    className={cn(
                                        "no-drag w-20 cursor-pointer rounded border px-2 py-0.5",
                                        focused
                                            ? "border-white bg-white text-black"
                                            : "border-[#555] text-[#aaa] hover:border-white hover:text-white",
                                    )}
                                >
                                    {focused ? "Show all" : "Only this"}
                                </button>
                            </div>
                        </div>
                    );
                })}
            </Section>

            <Section title={`Connections (${edges.length})`}>
                {edges.length === 0 && <Empty>No connections yet.</Empty>}
                {edges.map((claim) => (
                    <div
                        key={claim.id}
                        className="flex items-baseline gap-2 border-b border-[#2a2a2a] py-1.5"
                        title={claim.claim_text}
                    >
                        <div className="min-w-0 flex-1 break-words">
                            {node(claim.subject_ids[0])}
                            <span className="mx-1.5 text-[10px] uppercase text-[#888]">
                                {claim.predicate.replace(/_/g, " ")} →
                            </span>
                            {node(claim.reference_ids[0])}
                        </div>
                        <span className="shrink-0 text-[10px] text-[#888]">
                            {claim.claim_status}
                            {claim.confidence !== null &&
                                ` · ${Math.round(claim.confidence * 100)}%`}
                        </span>
                    </div>
                ))}
            </Section>
        </div>
    );
}
