import { useWM } from "./store";
import { cn } from "./util";

export function SnapToggle({ className }: { className?: string }) {
    const enabled = useWM((s) => s.snapEnabled);
    const toggle = useWM((s) => s.toggleSnap);

    return (
        <button
            type="button"
            role="switch"
            aria-checked={enabled}
            onClick={toggle}
            className={cn("flex items-center gap-2 text-xs", className)}
        >
            <span
                className={cn(
                    "relative inline-block h-4 w-7 rounded-full transition-colors",
                    enabled ? "bg-primary" : "bg-muted-foreground/40",
                )}
            >
                <span
                    className={cn(
                        "absolute left-0.5 top-0.5 h-3 w-3 rounded-full bg-background transition-transform",
                        enabled && "translate-x-3",
                    )}
                />
            </span>
            Snap windows
        </button>
    );
}
