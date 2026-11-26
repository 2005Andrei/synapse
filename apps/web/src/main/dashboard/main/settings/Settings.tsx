import { useEffect, type ComponentType } from "react";
import { createPortal } from "react-dom";
import {
    AppWindow,
    Cpu,
    Database,
    Share2,
    Shield,
    Waypoints,
    X,
    type LucideIcon,
} from "lucide-react";
import { cn } from "cn";
import ModelSettings from "./ModelSettings";
import {
    DataSettings,
    GraphSettings,
    InvestigationSettings,
    SourcesSettings,
    WorkspaceSettings,
} from "./sections";
import { PreviewBadge, ResetButton } from "./controls";
import { useSettings, type SectionKey } from "./store";

type Tab = {
    id: string;
    label: string;
    description: string;
    icon: LucideIcon;
    Body: ComponentType;
    /** Remembered but not used by searches yet. */
    preview?: boolean;
    /** The store section the reset button restores. */
    resets?: SectionKey;
};

const TABS: Tab[] = [
    {
        id: "model",
        label: "AI model",
        description: "The model that reads sources and pulls out people, companies and links.",
        icon: Cpu,
        Body: ModelSettings,
    },
    {
        id: "investigation",
        label: "Investigation",
        description: "How deep a search goes and how much it may spend.",
        icon: Waypoints,
        Body: InvestigationSettings,
        preview: true,
        resets: "investigation",
    },
    {
        id: "sources",
        label: "Sources",
        description: "Which registries and publications a search reads.",
        icon: Database,
        Body: SourcesSettings,
        preview: true,
        resets: "sources",
    },
    {
        id: "graph",
        label: "Graph",
        description: "How the entity graph is laid out and drawn.",
        icon: Share2,
        Body: GraphSettings,
        preview: true,
        resets: "graph",
    },
    {
        id: "workspace",
        label: "Workspace",
        description: "Windows, motion and notifications.",
        icon: AppWindow,
        Body: WorkspaceSettings,
        preview: true,
        resets: "workspace",
    },
    {
        id: "data",
        label: "Data & privacy",
        description: "What is kept, and for how long.",
        icon: Shield,
        Body: DataSettings,
        preview: true,
        resets: "data",
    },
];

export default function Settings({ onClose }: { onClose: () => void }) {
    const tabId = useSettings((s) => s.tab);
    const setTab = useSettings((s) => s.setTab);
    const reset = useSettings((s) => s.reset);
    const seen = useSettings((s) => s.seen);
    const markSeen = useSettings((s) => s.markSeen);
    const tab = TABS.find((t) => t.id === tabId) ?? TABS[0];
    const Body = tab.Body;
    const unseen = (t: Tab) => t.preview && !seen.includes(t.id);

    // Opening a page, by click or by reopening on it, clears its dot.
    useEffect(() => markSeen(tab.id), [tab.id, markSeen]);

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [onClose]);

    return createPortal(
        <div
            className="fixed inset-0 z-[100000] flex items-center justify-center bg-background/60 p-4 backdrop-blur-md animate-in fade-in duration-200"
            onMouseDown={(e) => e.target === e.currentTarget && onClose()}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="settings-title"
                className="relative flex h-[min(720px,88vh)] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-background/95 text-foreground shadow-[0_24px_60px_-12px_rgba(0,0,0,0.65)] animate-in zoom-in-95 duration-200 sm:flex-row"
            >
                <nav className="flex shrink-0 flex-col border-b border-white/10 bg-white/[0.02] sm:w-60 sm:border-r sm:border-b-0">
                    <div className="px-5 pt-6 pb-4">
                        <h2
                            id="settings-title"
                            className="text-lg font-medium tracking-tight"
                        >
                            Settings
                        </h2>
                        <p className="mt-0.5 text-xs text-foreground/40">
                            Synapse workspace
                        </p>
                    </div>
                    <ul className="flex gap-1 overflow-x-auto px-3 pb-3 sm:flex-col sm:overflow-visible">
                        {TABS.map((t) => {
                            const active = t.id === tab.id;
                            const Icon = t.icon;
                            return (
                                <li key={t.id} className="shrink-0">
                                    <button
                                        type="button"
                                        onClick={() => setTab(t.id)}
                                        aria-current={active ? "page" : undefined}
                                        className={cn(
                                            "group flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                                            active
                                                ? "bg-white/10 text-foreground"
                                                : "text-foreground/55 hover:bg-white/5 hover:text-foreground",
                                        )}
                                    >
                                        <Icon
                                            className={cn(
                                                "h-4 w-4 shrink-0",
                                                active
                                                    ? "text-foreground"
                                                    : "text-foreground/40 group-hover:text-foreground/70",
                                            )}
                                        />
                                        <span className="flex-1 whitespace-nowrap">
                                            {t.label}
                                        </span>
                                        {unseen(t) && (
                                            <span
                                                title="Not opened yet"
                                                className="hidden h-1.5 w-1.5 rounded-full bg-amber-300/60 sm:block"
                                            />
                                        )}
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                    {TABS.some(unseen) && (
                        <div className="mt-auto hidden px-5 py-4 text-[11px] leading-relaxed text-foreground/30 sm:block">
                            <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-amber-300/60 align-middle" />
                            Preview pages you haven't opened yet. They are saved
                            in this browser but not used by searches yet.
                        </div>
                    )}
                </nav>

                <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                    <header className="flex items-start justify-between gap-4 border-b border-white/10 px-8 pt-6 pb-5">
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                <h3 className="text-base font-medium">
                                    {tab.label}
                                </h3>
                                {tab.preview && <PreviewBadge />}
                            </div>
                            <p className="mt-1 text-sm text-foreground/45">
                                {tab.description}
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={onClose}
                            aria-label="Close settings"
                            className="-mr-2 cursor-pointer rounded-full p-2 text-foreground/40 transition-colors hover:bg-white/10 hover:text-foreground"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </header>

                    <div
                        key={tab.id}
                        className="@container flex min-h-0 flex-1 flex-col gap-7 overflow-y-auto px-8 py-6 animate-in fade-in slide-in-from-bottom-1 duration-200 [scrollbar-color:#444_transparent] [scrollbar-width:thin]"
                    >
                        <Body />
                    </div>

                    <footer className="flex items-center justify-between gap-3 border-t border-white/10 px-8 py-3">
                        <span className="text-xs text-foreground/35">
                            {tab.resets
                                ? "Changes are saved as you make them."
                                : "Press Save to use this model for new searches."}
                        </span>
                        <div className="flex items-center gap-2">
                            {tab.resets && (
                                <ResetButton onClick={() => reset(tab.resets!)} />
                            )}
                            <button
                                type="button"
                                onClick={onClose}
                                className="cursor-pointer rounded-md border border-white/15 px-4 py-1.5 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/10 hover:text-foreground"
                            >
                                Done
                            </button>
                        </div>
                    </footer>
                </div>
            </div>
        </div>,
        document.body,
    );
}
