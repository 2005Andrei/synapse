import { Moon, Sun } from "lucide-react";
import { useWM } from "../store.ts";
import { Button } from "../../../../../components/ui/button.tsx";

export function Dock({
    dark,
    onToggleTheme,
}: {
    dark?: boolean;
    onToggleTheme?: () => void;
}) {
    const wins = useWM((s) => s.wins);
    const focused = useWM((s) => s.focused);
    const { focus, toggleMin } = useWM.getState();

    const click = (id: string) => {
        const w = wins[id];
        if (w.minimized) toggleMin(id);
        else if (focused === id) toggleMin(id);
        else focus(id);
    };

    return (
        <div className="flex h-full w-12 shrink-0 flex-col items-center gap-1 border-l bg-card py-2">
            {Object.values(wins).map((w) => (
                <Button
                    key={w.id}
                    size="icon"
                    title={w.title}
                    variant={
                        focused === w.id && !w.minimized ? "secondary" : "ghost"
                    }
                    className={w.minimized ? "opacity-50" : ""}
                    onClick={() => click(w.id)}
                >
                    {w.title[0]}
                </Button>
            ))}
            {onToggleTheme && (
                <Button
                    size="icon"
                    variant="ghost"
                    className="mt-auto"
                    onClick={onToggleTheme}
                >
                    {dark ? <Sun size={14} /> : <Moon size={14} />}
                </Button>
            )}
        </div>
    );
}
