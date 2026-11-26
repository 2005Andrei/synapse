import { useId, type ReactNode } from "react";
import { cn } from "cn";

/** A titled card holding rows of settings. */
export function Group({
    title,
    hint,
    action,
    children,
}: {
    title?: string;
    hint?: string;
    action?: ReactNode;
    children: ReactNode;
}) {
    return (
        <section className="flex flex-col gap-2">
            {(title || action) && (
                <div className="flex items-end justify-between gap-3 px-1">
                    <div>
                        {title && (
                            <h4 className="text-[11px] font-semibold uppercase tracking-[1.2px] text-foreground/50">
                                {title}
                            </h4>
                        )}
                        {hint && (
                            <p className="mt-0.5 text-xs text-foreground/40">
                                {hint}
                            </p>
                        )}
                    </div>
                    {action}
                </div>
            )}
            <div className="divide-y divide-white/[0.06] overflow-hidden rounded-xl border border-white/10 bg-white/[0.025]">
                {children}
            </div>
        </section>
    );
}

/** One setting: label and description on the left, its control on the right. */
export function Row({
    label,
    hint,
    children,
    stacked,
    htmlFor,
}: {
    label: ReactNode;
    hint?: ReactNode;
    children: ReactNode;
    /** Put the control under the label, for wide controls such as sliders. */
    stacked?: boolean;
    htmlFor?: string;
}) {
    return (
        <div
            className={cn(
                "flex gap-x-6 gap-y-3 px-4 py-3.5",
                stacked
                    ? "flex-col"
                    : "flex-col @md:flex-row @md:items-center @md:justify-between",
            )}
        >
            <div className="min-w-0">
                <label
                    htmlFor={htmlFor}
                    className="block text-sm font-medium text-foreground/90"
                >
                    {label}
                </label>
                {hint && (
                    <p className="mt-0.5 text-xs leading-relaxed text-foreground/45">
                        {hint}
                    </p>
                )}
            </div>
            <div className="shrink-0">{children}</div>
        </div>
    );
}

export function Switch({
    checked,
    onChange,
    label,
}: {
    checked: boolean;
    onChange: (on: boolean) => void;
    label: string;
}) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            aria-label={label}
            onClick={() => onChange(!checked)}
            className={cn(
                "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/60",
                checked
                    ? "border-white/80 bg-white"
                    : "border-white/15 bg-white/10 hover:bg-white/15",
            )}
        >
            <span
                className={cn(
                    "inline-block h-3.5 w-3.5 rounded-full shadow transition-transform duration-200",
                    checked
                        ? "translate-x-[18px] bg-background"
                        : "translate-x-[3px] bg-white/70",
                )}
            />
        </button>
    );
}

export function Slider({
    value,
    onChange,
    min,
    max,
    step = 1,
    format = String,
    marks,
    label,
}: {
    value: number;
    onChange: (v: number) => void;
    min: number;
    max: number;
    step?: number;
    format?: (v: number) => string;
    /** Words under the two ends of the track. */
    marks?: [string, string];
    label: string;
}) {
    const id = useId();
    const pct = ((value - min) / (max - min)) * 100;
    return (
        <div className="flex w-full flex-col gap-2">
            <div className="flex items-center gap-4">
                <input
                    id={id}
                    type="range"
                    aria-label={label}
                    min={min}
                    max={max}
                    step={step}
                    value={value}
                    onChange={(e) => onChange(Number(e.target.value))}
                    style={{
                        background: `linear-gradient(to right, rgb(255 255 255 / 0.85) ${pct}%, rgb(255 255 255 / 0.1) ${pct}%)`,
                    }}
                    className={cn(
                        "h-1.5 flex-1 cursor-pointer appearance-none rounded-full outline-none",
                        "[&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-background [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:transition-transform hover:[&::-webkit-slider-thumb]:scale-110",
                        "[&::-moz-range-track]:bg-transparent [&::-moz-range-thumb]:h-3.5 [&::-moz-range-thumb]:w-3.5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-background [&::-moz-range-thumb]:bg-white",
                        "focus-visible:[&::-webkit-slider-thumb]:ring-2 focus-visible:[&::-webkit-slider-thumb]:ring-white/50",
                    )}
                />
                <output
                    htmlFor={id}
                    className="min-w-12 rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-center font-mono text-xs tabular-nums text-foreground/90"
                >
                    {format(value)}
                </output>
            </div>
            {marks && (
                <div className="flex justify-between pr-16 text-[10px] uppercase tracking-[1px] text-foreground/35">
                    <span>{marks[0]}</span>
                    <span>{marks[1]}</span>
                </div>
            )}
        </div>
    );
}

export function Segmented<T extends string | number>({
    value,
    onChange,
    options,
    label,
}: {
    value: T;
    onChange: (v: T) => void;
    options: { value: T; label: string }[];
    label: string;
}) {
    return (
        <div
            role="radiogroup"
            aria-label={label}
            className="inline-flex rounded-lg border border-white/10 bg-white/[0.04] p-0.5"
        >
            {options.map((o) => {
                const active = o.value === value;
                return (
                    <button
                        key={String(o.value)}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        onClick={() => onChange(o.value)}
                        className={cn(
                            "cursor-pointer rounded-md px-3 py-1 text-xs font-medium transition-all",
                            active
                                ? "bg-white text-background shadow-sm"
                                : "text-foreground/55 hover:text-foreground",
                        )}
                    >
                        {o.label}
                    </button>
                );
            })}
        </div>
    );
}

/** Marks a page whose values are remembered but not used yet. */
export function PreviewBadge({ className }: { className?: string }) {
    return (
        <span
            className={cn(
                "rounded-full border border-amber-300/25 bg-amber-300/10 px-1.5 py-px text-[9px] font-semibold uppercase tracking-[1px] text-amber-200/80",
                className,
            )}
        >
            Preview
        </span>
    );
}

export function ResetButton({ onClick }: { onClick: () => void }) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="cursor-pointer rounded-md px-2 py-1 text-xs text-foreground/45 transition-colors hover:bg-white/5 hover:text-foreground"
        >
            Reset to defaults
        </button>
    );
}
