import { useMemo } from "react";
import { CopyLink } from "../../../utils/CopyLink";
import type { RunState } from "../../../providers/investigation/store";
import type { Source } from "../../../providers/investigation/types";
import { Empty } from "../ui";

export default function Files({ run }: { run: RunState }) {
    const groups = useMemo(() => {
        const byPublisher = new Map<string, Source[]>();
        for (const source of Object.values(run.sources)) {
            const publisher = source.publisher ?? "Unknown";
            byPublisher.set(publisher, [
                ...(byPublisher.get(publisher) ?? []),
                source,
            ]);
        }
        for (const list of byPublisher.values())
            list.sort((a, b) =>
                (b.published_at ?? "").localeCompare(a.published_at ?? ""),
            );
        return [...byPublisher.entries()];
    }, [run.sources]);

    if (groups.length === 0) return <Empty>No documents yet.</Empty>;

    return (
        <div className="flex flex-col gap-4">
            {groups.map(([publisher, sources]) => (
                <div key={publisher}>
                    <div className="mb-1 flex justify-between border-b border-[#333] pb-1 uppercase tracking-[1px] text-[#888]">
                        <span>{publisher}</span>
                        <span>{sources.length}</span>
                    </div>
                    {sources.map((source) => (
                        <div
                            key={source.id}
                            className="border-b border-[#2a2a2a] py-2"
                        >
                            <div className="text-white">{source.title}</div>
                            {source.content &&
                                !source.content.startsWith("{") &&
                                !source.content.startsWith("[") && (
                                    <div className="mt-0.5 line-clamp-2 text-[#aaa]">
                                        {source.content}
                                    </div>
                                )}
                            <div className="mt-1 flex items-center justify-between gap-3 text-[#888]">
                                <span className="shrink-0">
                                    {source.published_at ?? "no date"}
                                </span>
                                <CopyLink
                                    url={source.url}
                                    className="min-w-0"
                                />
                            </div>
                        </div>
                    ))}
                </div>
            ))}
        </div>
    );
}
