import { useState, type ReactNode } from "react";
import { cn } from "cn";
import {
    loadLlmChoice,
    saveLlmChoice,
} from "../../providers/investigation/api";

const PROVIDERS = [
    { id: "", label: "Server default", model: "", key: false },
    { id: "ollama", label: "Local (Ollama)", model: "qwen2.5", key: false },
    {
        id: "anthropic",
        label: "Anthropic",
        model: "claude-opus-5-5",
        key: true,
    },
    { id: "openai", label: "OpenAI", model: "", key: true },
];

const field =
    "w-full rounded-md border border-white/15 bg-background/50 px-3 py-1.5 text-sm text-foreground outline-none transition-colors placeholder:text-foreground/30 focus:border-white/40 focus:bg-white/5";

export default function ModelSettings() {
    const saved = loadLlmChoice();
    const [provider, setProvider] = useState(saved?.model.split(":")[0] ?? "");
    const [model, setModel] = useState(
        saved?.model.split(":").slice(1).join(":") ?? "",
    );
    const [apiKey, setApiKey] = useState(saved?.api_key ?? "");
    const [note, setNote] = useState<{ text: string; error?: boolean }>();
    const current = PROVIDERS.find((p) => p.id === provider) ?? PROVIDERS[0];

    const pick = (id: string) => {
        const next = PROVIDERS.find((p) => p.id === id)!;
        setProvider(next.id);
        setModel(next.model);
        setNote(undefined);
    };

    const save = () => {
        if (!provider) {
            saveLlmChoice(null);
            setNote({ text: "Using the server's model." });
        } else if (!model.trim()) {
            setNote({ text: "Name the model.", error: true });
        } else {
            saveLlmChoice({
                model: `${provider}:${model.trim()}`,
                api_key: current.key ? apiKey.trim() || undefined : undefined,
            });
            setNote({ text: "Saved. Used by the searches you start from now on." });
        }
    };

    return (
        <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
                e.preventDefault();
                save();
            }}
        >
            <div
                role="radiogroup"
                aria-label="Provider"
                className="flex flex-wrap gap-2"
            >
                {PROVIDERS.map((p) => {
                    const active = p.id === provider;
                    return (
                        <button
                            key={p.id}
                            type="button"
                            role="radio"
                            aria-checked={active}
                            onClick={() => pick(p.id)}
                            className={cn(
                                "cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium transition-all",
                                active
                                    ? "border-white/40 bg-white/15 text-foreground shadow-sm"
                                    : "border-white/10 text-foreground/60 hover:border-white/30 hover:bg-white/5 hover:text-foreground",
                            )}
                        >
                            {p.label}
                        </button>
                    );
                })}
            </div>

            {provider && (
                <Field label="Model name">
                    <input
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        placeholder={current.model || "model"}
                        spellCheck={false}
                        className={field}
                    />
                </Field>
            )}
            {current.key && (
                <Field label="Your API key" hint="Kept in this browser only.">
                    <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="sk-…"
                        autoComplete="off"
                        className={field}
                    />
                </Field>
            )}
            {provider === "ollama" && (
                <p className="text-xs text-foreground/45">
                    Runs on the machine the worker runs on; no key, nothing
                    leaves it.
                </p>
            )}

            <div className="flex items-center justify-between gap-3 pt-1">
                <span
                    aria-live="polite"
                    className={cn(
                        "min-w-0 text-xs",
                        note?.error ? "text-red-400" : "text-foreground/50",
                    )}
                >
                    {note?.text}
                </span>
                <button
                    type="submit"
                    className="shrink-0 cursor-pointer rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
                >
                    Save
                </button>
            </div>
        </form>
    );
}

function Field({
    label,
    hint,
    children,
}: {
    label: string;
    hint?: string;
    children: ReactNode;
}) {
    return (
        <label className="flex flex-col gap-1.5">
            <span className="flex items-baseline justify-between text-xs text-foreground/60">
                {label}
                {hint && <span className="text-foreground/35">{hint}</span>}
            </span>
            {children}
        </label>
    );
}
