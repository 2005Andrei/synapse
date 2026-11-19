import { useEffect, useRef } from "react";
import { cn, copyText } from "../../utils/util";

export type NodeMenuState = {
    x: number;
    y: number;
    node: { id: string; label: string; type?: string };
};

export const SEARCHABLE = new Set(["Person", "Organization"]);

type Props = {
    menu: NodeMenuState;
    blocked: string | null;
    status: string | null;
    onSearch: () => void;
    onDetails: () => void;
    onClose: () => void;
};

export default function NodeMenu({
    menu,
    blocked,
    status,
    onSearch,
    onDetails,
    onClose,
}: Props) {
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const outside = (event: Event) => {
            if (!ref.current?.contains(event.target as Node)) onClose();
        };
        const escape = (event: KeyboardEvent) =>
            event.key === "Escape" && onClose();
        window.addEventListener("pointerdown", outside, true);
        window.addEventListener("wheel", onClose, { passive: true });
        window.addEventListener("keydown", escape);
        ref.current
            ?.querySelector<HTMLButtonElement>("button:not(:disabled)")
            ?.focus();
        return () => {
            window.removeEventListener("pointerdown", outside, true);
            window.removeEventListener("wheel", onClose);
            window.removeEventListener("keydown", escape);
        };
    }, [onClose]);

    const item =
        "block w-full cursor-pointer px-3 py-1.5 text-left hover:bg-white/10 focus:bg-white/10 focus:outline-none disabled:cursor-default disabled:text-[#666] disabled:hover:bg-transparent";
    const run = (action: () => void) => () => {
        action();
        onClose();
    };

    return (
        <div
            ref={ref}
            role="menu"
            aria-label={`Actions for ${menu.node.label}`}
            // Kept on screen when the node is near the right or bottom edge.
            style={{
                left: Math.min(menu.x, window.innerWidth - 240),
                top: Math.min(menu.y, window.innerHeight - 150),
            }}
            className="fixed z-50 w-56 rounded-md border border-white/20 bg-[rgba(15,15,20,0.96)] py-1 font-mono text-[12px] text-[#ececec] shadow-[0_8px_32px_rgba(0,0,0,0.6)]"
            onContextMenu={(event) => event.preventDefault()}
        >
            <div
                className="truncate border-b border-white/10 px-3 pb-1.5 pt-1 text-[10px] uppercase tracking-[1px] text-[#888]"
                title={menu.node.label}
            >
                {menu.node.label}
            </div>
            <button
                type="button"
                role="menuitem"
                disabled={blocked !== null || status !== null}
                title={
                    blocked ??
                    "Look this up in every source; results join this graph"
                }
                onClick={run(onSearch)}
                className={cn(item, "text-[#ffd166]")}
            >
                {status ?? "Search further"}
                {blocked && (
                    <span className="block text-[10px] text-[#666]">
                        {blocked}
                    </span>
                )}
            </button>
            <button
                type="button"
                role="menuitem"
                onClick={run(onDetails)}
                className={item}
            >
                Open details
            </button>
            <button
                type="button"
                role="menuitem"
                onClick={run(() => void copyText(menu.node.label))}
                className={item}
            >
                Copy name
            </button>
        </div>
    );
}
