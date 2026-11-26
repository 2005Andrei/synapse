import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Cpu, X } from "lucide-react";
import ModelSettings from "./ModelSettings";

export default function Settings({ onClose }: { onClose: () => void }) {
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
                className="relative flex max-h-[85vh] w-full max-w-lg flex-col rounded-2xl border border-white/10 bg-background/95 p-8 text-foreground shadow-[0_16px_40px_-12px_rgba(0,0,0,0.5)] animate-in zoom-in-95 duration-200"
            >
                <div className="mb-6 flex items-center justify-between">
                    <h2
                        id="settings-title"
                        className="text-xl font-medium tracking-tight"
                    >
                        Settings
                    </h2>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="Close settings"
                        className="cursor-pointer rounded-full p-2 text-foreground/40 transition-colors hover:bg-white/10 hover:text-foreground"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <div className="-mx-2 flex flex-col overflow-y-auto px-2">
                    <Section
                        icon={<Cpu className="h-4 w-4" />}
                        title="AI model"
                        hint="The model that reads sources and extracts entities."
                    >
                        <ModelSettings />
                    </Section>
                </div>
            </div>
        </div>,
        document.body,
    );
}

function Section({
    icon,
    title,
    hint,
    children,
}: {
    icon: ReactNode;
    title: string;
    hint: string;
    children: ReactNode;
}) {
    return (
        <section className="flex flex-col gap-4 border-t border-white/10 py-5 first:border-t-0 first:pt-0">
            <div className="flex items-start gap-2">
                <span className="mt-0.5 text-foreground/50">{icon}</span>
                <div>
                    <h3 className="text-sm font-medium text-foreground/90">
                        {title}
                    </h3>
                    <p className="text-xs text-foreground/45">{hint}</p>
                </div>
            </div>
            {children}
        </section>
    );
}
