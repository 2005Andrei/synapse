import { CopyLink } from "../../../utils/CopyLink";

type Props = {
    label: string;
    color?: string;
    sourceLabel: string;
    targetLabel: string;
    confidence?: number;
    status?: string;
    text?: string;
    /** The passage of the source the claim was read from, word for word. */
    quote?: string;
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
    quote,
    sources = [],
}: Props) {
    return (
        <div className="w-80 max-h-[80vh] overflow-y-auto [scrollbar-color:#444_transparent] [scrollbar-width:thin] p-5 text-left font-mono text-[12px] text-[#ececec]">
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

            {quote && (
                <blockquote className="mb-[15px] border-l-2 border-[#555] pl-3 text-[#aaa]">
                    <div className="mb-1 text-[10px] uppercase tracking-[1px] text-[#888]">
                        Read by AI from
                    </div>
                    <span className="break-words italic">“{quote}”</span>
                </blockquote>
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
