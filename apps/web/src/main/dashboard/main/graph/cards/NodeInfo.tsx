import { CopyLink } from "../../../utils/CopyLink";
import { isUrl } from "../../../utils/util";

type Props = {
    label: string;
    type?: string;
    color?: string;
    description?: string;
    attributes?: Record<string, unknown>;
};

const HIDDEN = new Set(["source_id"]);

export default function NodeInfo({
    label,
    type,
    color,
    description,
    attributes = {},
}: Props) {
    const url = isUrl(attributes.url) ? attributes.url : null;
    const rest = Object.entries(attributes).filter(
        ([key]) => key !== "url" && !HIDDEN.has(key),
    );

    return (
        <div className="w-80 p-5 text-[#ececec] font-mono">
            <div className="mb-[15px] text-center">
                <h3 className="m-0 break-words" style={{ color }}>
                    {label}
                </h3>
                {type && (
                    <div className="mt-1 text-[10px] uppercase tracking-[1px] text-[#888]">
                        {type}
                    </div>
                )}
            </div>

            <div className="text-[12px] text-[#aaa] mb-[15px] border-b border-[#333] pb-[15px]">
                {description}
                {url && (
                    <div className="mt-2">
                        <CopyLink url={url} />
                    </div>
                )}
            </div>

            <div className="text-[12px]">
                <div
                    className="mb-2 uppercase tracking-[1px]"
                    style={{ color }}
                >
                    Attributes
                </div>
                {rest.map(([key, value]) => (
                    <div key={key} className="mb-[6px] flex flex-col">
                        <span className="text-[#888]">
                            {key.replace(/_/g, " ")}:
                        </span>
                        {isUrl(value) ? (
                            <CopyLink url={value} />
                        ) : (
                            <span className="break-words text-white">
                                {Array.isArray(value)
                                    ? value.join(", ")
                                    : String(value)}
                            </span>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
