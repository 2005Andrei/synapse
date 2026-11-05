import { useState } from "react";
import { cn } from "cn";
import { useWM } from "../store.ts";
import { DockIcon } from "./DockIcon.tsx";

export function Dock({}: {}) {
    const wins = useWM((s) => s.wins);
    const focused = useWM((s) => s.focused);
    const { focus, toggleMin } = useWM.getState();

    const [hoveredId, setHoveredId] = useState<string | null>(null);

    const click = (id: string) => {
        const w = wins[id];
        if (w.minimized) toggleMin(id);
        else if (focused === id) toggleMin(id);
        else focus(id);
    };

    return (
        <div className="fixed top-1/2 -translate-y-1/2 right-2 z-40 flex w-16 shrink-0 flex-col items-center justify-center py-6">
            <div
                className={cn(
                    "flex w-full min-h-[50vh] max-h-[90vh] flex-col items-center justify-start gap-2 overflow-y-auto rounded-3xl p-2",
                    "bg-background/20 backdrop-blur-xl border border-foreground/10 shadow-2xl",
                    "[&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]",
                )}
                onMouseLeave={() => setHoveredId(null)}
            >
                {Object.values(wins).map((w) => (
                    <DockIcon
                        key={w.id}
                        id={w.id}
                        title={w.title}
                        isFocused={focused === w.id}
                        isMinimized={w.minimized}
                        isHovered={hoveredId === w.id}
                        onHoverEnter={() => setHoveredId(w.id)}
                        onHoverLeave={() => setHoveredId(null)}
                        onClick={() => click(w.id)}
                    />
                ))}
            </div>
        </div>
    );
}
