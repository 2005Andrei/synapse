import { CopyLink } from "../../../utils/CopyLink";

type Props = {
    label: string;
    color?: string;
    sourceLabel: string;
    targetLabel: string;
    confidence?: number;
    status?: string;
    text?: string;
    sources?: { title: string; url: string }[];
};

export default function LinkInfo({
    label,
    color,
    sourceLabel,
    targetLabel,
    confidence,
    status,
    text,
    sources = [],
}: Props) {
    return (
        <div className="w-80 p-5 text-[#ececec] font-mono text-[12px]">
            <div className="mb-[15px] border-b border-[#333] pb-[15px]">
                <div className="break-words text-white">{sourceLabel}</div>
                <div
                    className="my-1 uppercase tracking-[1px]"
                    style={{ color }}
                >
                    {label} →
                </div>
                <div className="break-words text-white">{targetLabel}</div>
            </div>

            {text && (
                <div className="mb-[15px] break-words text-[#aaa]">{text}</div>
            )}

            <div className="mb-[15px] text-[#888]">
                {[
                    status,
                    confidence !== undefined &&
                        `confidence ${Math.round(confidence * 100)}%`,
                ]
                    .filter(Boolean)
                    .join(" · ")}
            </div>

            <div className="mb-2 uppercase tracking-[1px]" style={{ color }}>
                Sources
            </div>
            {sources.length === 0 && (
                <div className="text-[#888]">No source recorded.</div>
            )}
            {sources.map((source) => (
                <div key={source.url} className="mb-2">
                    <div
                        className="line-clamp-2 break-words text-white"
                        title={source.title}
                    >
                        {source.title}
                    </div>
                    <CopyLink url={source.url} />
                </div>
            ))}
        </div>
    );
}
