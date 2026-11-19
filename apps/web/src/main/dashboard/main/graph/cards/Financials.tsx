import { useState } from "react";
import { cn } from "../../../utils/util";

export type FinancialYear = {
    year: number;
    revenue: number | null;
    net_result: number | null; // profit > 0, loss < 0
    employees: number | null;
};

type MeasureKey = "revenue" | "net_result" | "employees";

const MEASURES: {
    key: MeasureKey;
    label: string;
    money: boolean;
    upIsGood: boolean | null;
}[] = [
    { key: "revenue", label: "Revenue", money: true, upIsGood: true },
    { key: "net_result", label: "Net result", money: true, upIsGood: true },
    { key: "employees", label: "Employees", money: false, upIsGood: null },
];

const ABOVE = "#3987e5";
const BELOW = "#d95926";
const PLOT_HEIGHT = 40;

const numberOrNull = (value: unknown): number | null =>
    typeof value === "number" && Number.isFinite(value) ? value : null;

export function parseFinancials(value: unknown): FinancialYear[] {
    if (!Array.isArray(value)) return [];
    return value
        .flatMap((row): FinancialYear[] => {
            const year = numberOrNull((row as FinancialYear | null)?.year);
            if (year === null) return [];
            const { revenue, net_result, employees } = row as FinancialYear;
            return [
                {
                    year,
                    revenue: numberOrNull(revenue),
                    net_result: numberOrNull(net_result),
                    employees: numberOrNull(employees),
                },
            ];
        })
        .sort((a, b) => a.year - b.year);
}

const compact = new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
});

function format(value: number | null, money: boolean, currency: string) {
    if (value === null) return "not filed";
    return money
        ? `${compact.format(value)} ${currency}`
        : compact.format(value);
}

function change(now: number | null, before: number | null, year: number) {
    if (now === null || before === null || before <= 0 || now < 0) return null;
    const percent = ((now - before) / before) * 100;
    if (!Number.isFinite(percent)) return null;
    const rounded =
        Math.abs(percent) >= 100 ? percent.toFixed(0) : percent.toFixed(1);
    return {
        up: percent >= 0,
        text: `${percent >= 0 ? "▲" : "▼"} ${rounded.replace("-", "")}% vs ${year}`,
    };
}

function MiniChart({
    years,
    measure,
    currency,
}: {
    years: FinancialYear[];
    measure: (typeof MEASURES)[number];
    currency: string;
}) {
    const [pointed, setPointed] = useState<number | null>(null);
    const index = pointed ?? years.length - 1;
    const values = years.map((year) => year[measure.key]);

    const high = Math.max(0, ...values.map((v) => v ?? 0));
    const low = Math.min(0, ...values.map((v) => v ?? 0));
    const span = high - low || 1;
    const zero = (high / span) * PLOT_HEIGHT;

    const delta =
        index > 0
            ? change(values[index], values[index - 1], years[index - 1].year)
            : null;

    return (
        <div className="mb-3">
            <div className="flex items-baseline justify-between gap-2">
                <span className="text-[10px] uppercase tracking-[1px] text-[#898781]">
                    {measure.label}
                </span>
                <span className="text-[#f0efec]">
                    {format(values[index], measure.money, currency)}
                    <span className="ml-1.5 text-[10px] text-[#898781]">
                        {years[index].year}
                    </span>
                </span>
            </div>
            <div
                className={cn(
                    "h-[14px] text-right text-[10px] text-[#898781]",
                    delta &&
                        measure.upIsGood !== null &&
                        (delta.up === measure.upIsGood
                            ? "text-[#0ca30c]"
                            : "text-[#e66767]"),
                )}
            >
                {delta?.text}
            </div>

            <div className="flex" onPointerLeave={() => setPointed(null)}>
                {years.map((year, i) => {
                    const value = values[i];
                    const size =
                        value === null || value === 0
                            ? 0
                            : Math.max(
                                  2,
                                  (Math.abs(value) / span) * PLOT_HEIGHT,
                              );
                    const readout = `${year.year}: ${format(value, measure.money, currency)}`;
                    return (
                        <button
                            key={year.year}
                            type="button"
                            aria-label={`${measure.label} ${readout}`}
                            title={readout}
                            onPointerEnter={() => setPointed(i)}
                            onFocus={() => setPointed(i)}
                            onBlur={() => setPointed(null)}
                            className="no-drag group min-w-0 flex-1 cursor-default px-px outline-none"
                        >
                            <div
                                className="relative"
                                style={{ height: PLOT_HEIGHT }}
                            >
                                {size > 0 && (
                                    <div
                                        className={cn(
                                            "absolute left-1/2 w-full max-w-[24px] -translate-x-1/2",
                                            value! > 0
                                                ? "rounded-t-[4px]"
                                                : "rounded-b-[4px]",
                                            i === index
                                                ? "brightness-125"
                                                : "opacity-70",
                                            "group-focus-visible:ring-1 group-focus-visible:ring-white/60",
                                        )}
                                        style={{
                                            background:
                                                value! > 0 ? ABOVE : BELOW,
                                            height: size,
                                            top:
                                                value! > 0 ? zero - size : zero,
                                        }}
                                    />
                                )}
                                <div
                                    className="absolute inset-x-0 h-px bg-[#383835]"
                                    style={{ top: zero }}
                                />
                            </div>
                            <div
                                className={cn(
                                    "mt-1 text-center text-[10px] tabular-nums",
                                    i === index
                                        ? "text-[#f0efec]"
                                        : "text-[#898781]",
                                )}
                            >
                                {years.length > 6
                                    ? `’${String(year.year).slice(-2)}`
                                    : year.year}
                            </div>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

export default function Financials({
    years,
    currency = "RON",
}: {
    years: FinancialYear[];
    currency?: string;
}) {
    const shown = MEASURES.filter((measure) =>
        years.some((year) => year[measure.key] !== null),
    );
    if (shown.length === 0) return null;

    return (
        <div className="mb-3 border-b border-[#333] pb-1 text-[12px]">
            {shown.map((measure) => (
                <MiniChart
                    key={measure.key}
                    years={years}
                    measure={measure}
                    currency={currency}
                />
            ))}
            <table className="sr-only">
                <caption>Financial results by year</caption>
                <thead>
                    <tr>
                        <th>Year</th>
                        {shown.map((measure) => (
                            <th key={measure.key}>{measure.label}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {years.map((year) => (
                        <tr key={year.year}>
                            <td>{year.year}</td>
                            {shown.map((measure) => (
                                <td key={measure.key}>
                                    {format(
                                        year[measure.key],
                                        measure.money,
                                        currency,
                                    )}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
