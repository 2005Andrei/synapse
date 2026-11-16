import { useMemo, useState } from "react";
import { CopyLink } from "../../../utils/CopyLink";
import { cn, isUrl } from "../../../utils/util";
import type { RunState } from "../../../providers/investigation/store";
import {
    OTHER,
    divide,
    identityLabel,
    type Division,
} from "../../../providers/investigation/identities";
import { Empty, TypeBadge, entityName } from "../ui";

type Row = {
    id: string;
    type: string;
    label: string;
    summary: string;
    url: string | null;
    group: string;
};

function rowsOf(run: RunState, scraper: string, { groupOf }: Division): Row[] {
    const from = (id: string) => run.origins[id]?.includes(scraper);
    const rows: Row[] = [];

    const evidence = new Map<string, string>(); // entity id -> url of a source about it
    for (const claim of Object.values(run.claims)) {
        const url = run.sources[claim.source_ids[0]]?.url;
        if (!url || !from(claim.id)) continue;
        for (const id of [...claim.subject_ids, ...claim.reference_ids])
            if (!evidence.has(id)) evidence.set(id, url);
    }

    for (const entity of Object.values(run.entities)) {
        if (!from(entity.id)) continue;
        const { url, source_id } = entity.attributes as {
            url?: unknown;
            source_id?: string;
        };
        rows.push({
            id: entity.id,
            type: entity.type,
            label: entityName(entity),
            summary: [entity.attributes.match_note, entity.description]
                .filter(Boolean)
                .join(" · "),
            group: groupOf[entity.id] ?? OTHER,
            url: isUrl(url)
                ? url
                : (run.sources[source_id ?? ""]?.url ??
                  evidence.get(entity.id) ??
                  null),
        });
    }
    for (const claim of Object.values(run.claims)) {
        if (!from(claim.id) || claim.reference_ids.length > 0) continue;
        rows.push({
            id: claim.id,
            type: "Fact",
            label: claim.claim_text,
            summary: claim.predicate.replace(/_/g, " "),
            group: groupOf[claim.subject_ids[0]] ?? OTHER,
            url: run.sources[claim.source_ids[0]]?.url ?? null,
        });
    }
    return rows;
}

export default function DataBySource({ run }: { run: RunState }) {
    const division = useMemo(() => divide(run), [run]);
    const sources = useMemo(() => {
        const names = run.scraperNames.length
            ? run.scraperNames
            : Object.keys(run.scrapers);
        return names.map((name) => ({
            name,
            report: run.scrapers[name],
            rows: rowsOf(run, name, division),
        }));
    }, [run, division]);

    const [picked, setPicked] = useState<string | null>(null);
    const current =
        sources.find((s) => s.name === picked) ??
        sources.find((s) => s.rows.length) ??
        sources[0];

    if (!current) return <Empty>No sources yet.</Empty>;

    const blocks = division.identities
        .map((identity) => ({
            identity,
            rows: current.rows.filter((row) => row.group === identity.id),
        }))
        .filter((block) => block.rows.length > 0);

    return (
        <div className="flex min-h-0 flex-1 flex-col gap-3 @2xl:flex-row">
            <div className="flex shrink-0 flex-wrap gap-1 @2xl:w-44 @2xl:flex-col @2xl:flex-nowrap @2xl:overflow-y-auto">
                {sources.map(({ name, report, rows }) => {
                    const pending = report?.status === undefined;
                    return (
                        <button
                            key={name}
                            type="button"
                            onClick={() => setPicked(name)}
                            title={report?.error ?? undefined}
                            className={cn(
                                "no-drag flex cursor-pointer items-center justify-between gap-2 rounded border px-2 py-1 text-left",
                                name === current.name
                                    ? "border-[#ffd166]/60 bg-[#ffd166]/10 text-white"
                                    : "border-transparent text-[#aaa] hover:bg-white/5",
                                rows.length === 0 &&
                                    name !== current.name &&
                                    "text-[#666]",
                            )}
                        >
                            <span className="truncate">
                                {report?.label ?? name}
                            </span>
                            <span
                                className={cn(
                                    "shrink-0 tabular-nums",
                                    pending && "animate-pulse text-[#00d2ff]",
                                    report?.status === "error" &&
                                        "text-[#f16035]",
                                )}
                            >
                                {pending
                                    ? "…"
                                    : report?.status === "error"
                                      ? "!"
                                      : rows.length}
                            </span>
                        </button>
                    );
                })}
            </div>

            <div className="min-h-0 min-w-0 flex-1 overflow-auto [scrollbar-color:#444_transparent] [scrollbar-width:thin]">
                {current.rows.length === 0 ? (
                    <Empty>
                        {current.report?.status === undefined
                            ? "Still running…"
                            : (current.report.error ??
                              current.report.metadata?.notes?.[0] ??
                              "Nothing found in this source.")}
                    </Empty>
                ) : (
                    blocks.map(({ identity, rows }) => (
                        <div key={identity.id} className="mb-3">
                            <div className="flex items-baseline gap-2 border-y border-[#333] bg-white/[0.04] px-2 py-1.5">
                                <span
                                    className={cn(
                                        "shrink-0 text-[10px] uppercase tracking-[1px]",
                                        identity.kind === "subject" &&
                                            "text-[#69ff94]",
                                        identity.kind === "similar" &&
                                            "text-[#ffd166]",
                                        identity.kind === "other" &&
                                            "text-[#888]",
                                    )}
                                >
                                    {identityLabel(identity)}
                                </span>
                                <span className="min-w-0 flex-1 break-words text-white">
                                    {identity.name}
                                    {identity.note && (
                                        <span className="ml-2 text-[#888]">
                                            ({identity.note})
                                        </span>
                                    )}
                                </span>
                                <span className="shrink-0 tabular-nums text-[#888]">
                                    {rows.length}
                                </span>
                            </div>
                            <table className="w-full table-fixed border-collapse text-left">
                                <tbody>
                                    {rows.map((row) => (
                                        <tr
                                            key={row.id}
                                            className="border-b border-[#2a2a2a] align-top"
                                        >
                                            <td className="w-28 py-2 pr-2">
                                                <TypeBadge type={row.type} />
                                            </td>
                                            <td className="break-words py-2 pr-2 text-white">
                                                {row.label}
                                                <div className="text-[#888] @lg:hidden">
                                                    {row.summary}
                                                </div>
                                            </td>
                                            <td className="hidden w-2/5 break-words py-2 pr-2 text-[#aaa] @lg:table-cell">
                                                {row.summary}
                                            </td>
                                            <td className="w-12 py-2 text-right">
                                                {row.url && (
                                                    <CopyLink
                                                        url={row.url}
                                                        compact
                                                    />
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
