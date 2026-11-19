import { CopyLink } from "../../../utils/CopyLink";
import { isUrl } from "../../../utils/util";
import Financials, { parseFinancials } from "./Financials";

type Props = {
    label: string;
    type?: string;
    color?: string;
    description?: string;
    attributes?: Record<string, unknown>;
};

const HIDDEN = new Set(["source_id", "financials"]);
// Shown by the charts (latest year), so not repeated as rows below them.
const CHARTED = new Set(["revenue", "employees", "financial_year", "currency"]);

function display(value: unknown): string {
    if (Array.isArray(value)) return value.map(display).join(", ");
    if (typeof value === "boolean") return value ? "yes" : "no";
    if (value !== null && typeof value === "object") return JSON.stringify(value);
    return String(value);
}

export default function NodeInfo({
    label,
    type,
    color,
    description,
    attributes = {},
}: Props) {
    const url = isUrl(attributes.url) ? attributes.url : null;
    const financials = parseFinancials(attributes.financials);
    const rest = Object.entries(attributes).filter(
        ([key, value]) =>
            key !== "url" &&
            !HIDDEN.has(key) &&
            !(financials.length > 0 && CHARTED.has(key)) &&
            value !== null &&
            value !== "",
    );

    return (
        <div className="w-80 max-h-[80vh] overflow-y-auto [scrollbar-color:#444_transparent] [scrollbar-width:thin] p-5 font-mono text-[#ececec]">
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

            <div className="text-left text-[12px]">
                <div
                    className="mb-2 uppercase tracking-[1px]"
                    style={{ color }}
                >
                    Attributes
                </div>
                {financials.length > 0 && (
                    <Financials
                        years={financials}
                        currency={
                            typeof attributes.currency === "string"
                                ? attributes.currency
                                : undefined
                        }
                    />
                )}
                {rest.map(([key, value]) => (
                    <div key={key} className="mb-[6px] flex flex-col">
                        <span className="text-[#888]">
                            {key.replace(/_/g, " ")}:
                        </span>
                        {isUrl(value) ? (
                            <CopyLink url={value} />
                        ) : (
                            <span className="break-words text-white">
                                {display(value)}
                            </span>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
