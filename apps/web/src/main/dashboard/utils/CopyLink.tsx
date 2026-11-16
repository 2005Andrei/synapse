import { useState } from "react";
import { Check, Copy, ExternalLink } from "lucide-react";
import { cn, copyText, shortUrl } from "./util";

export function CopyLink({
    url,
    label,
    compact = false,
    className,
}: {
    url: string;
    label?: string;
    compact?: boolean;
    className?: string;
}) {
    const [copied, setCopied] = useState(false);

    const copy = async () => {
        if (!(await copyText(url))) return;
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };

    return (
        <span
            className={cn(
                "no-drag inline-flex max-w-full items-center gap-1.5 align-middle",
                className,
            )}
        >
            <a
                href={url}
                target="_blank"
                rel="noreferrer"
                title={url}
                className="inline-flex min-w-0 items-center gap-1 text-[#00d2ff] hover:underline"
            >
                {!compact && (
                    <span className="truncate">{label ?? shortUrl(url)}</span>
                )}
                <ExternalLink
                    size={12}
                    className="shrink-0"
                    aria-label="Open in a new tab"
                />
            </a>
            <button
                type="button"
                onClick={copy}
                title={copied ? "Copied" : "Copy link"}
                aria-label={copied ? "Link copied" : "Copy link"}
                className={cn(
                    "shrink-0 cursor-pointer rounded p-0.5 hover:bg-white/10",
                    copied ? "text-[#69ff94]" : "text-[#888] hover:text-white",
                )}
            >
                {copied ? <Check size={12} /> : <Copy size={12} />}
            </button>
        </span>
    );
}
