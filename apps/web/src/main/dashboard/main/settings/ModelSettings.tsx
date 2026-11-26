import { useState } from "react";
import { Check, Cloud, HardDrive, Server, Sparkles, type LucideIcon } from "lucide-react";
import { cn } from "cn";
import {
    loadLlmChoice,
    saveLlmChoice,
} from "../../providers/investigation/api";
import { Group, Row } from "./controls";

const PROVIDERS: {
    id: string;
    label: string;
    hint: string;
    model: string;
    key: boolean;
    icon: LucideIcon;
}[] = [
    {
        id: "",
        label: "Server default",
        hint: "Whatever the API is configured with.",
        model: "",
        key: false,
        icon: Server,
    },
    {
        id: "ollama",
        label: "Local (Ollama)",
        hint: "Runs on the worker machine. No key, nothing leaves it.",
        model: "qwen2.5",
        key: false,
        icon: HardDrive,
    },
    {
        id: "anthropic",
        label: "Anthropic",
        hint: "Claude models, with your own API key.",
        model: "claude-opus-5-5",
        key: true,
        icon: Sparkles,
    },
    {
        id: "openai",
        label: "OpenAI",
        hint: "GPT models, with your own API key.",
        model: "",
        key: true,
        icon: Cloud,
    },
];

const field =
    "w-full rounded-md border border-white/15 bg-background/50 px-3 py-2 font-mono text-sm text-foreground outline-none transition-colors placeholder:text-foreground/30 focus:border-white/40 focus:bg-white/5";

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
            setNote({
                text: "Saved. Used by the searches you start from now on.",
            });
        }
    };

    return (
        <form
            className="flex flex-col gap-7"
            onSubmit={(e) => {
                e.preventDefault();
                save();
            }}
        >
            <section className="flex flex-col gap-2">
                <h4 className="px-1 text-[11px] font-semibold uppercase tracking-[1.2px] text-foreground/50">
                    Provider
                </h4>
                <div
                    role="radiogroup"
                    aria-label="Provider"
                    className="grid grid-cols-1 gap-2 @md:grid-cols-2"
                >
                    {PROVIDERS.map((p) => {
                        const active = p.id === provider;
                        const Icon = p.icon;
                        return (
                            <button
                                key={p.id}
                                type="button"
                                role="radio"
                                aria-checked={active}
                                onClick={() => pick(p.id)}
                                className={cn(
                                    "relative flex cursor-pointer items-start gap-3 rounded-xl border p-4 text-left transition-all",
                                    active
                                        ? "border-white/40 bg-white/[0.07] shadow-[inset_0_0_0_1px_rgb(255_255_255/0.08)]"
                                        : "border-white/10 bg-white/[0.02] hover:border-white/25 hover:bg-white/[0.04]",
                                )}
                            >
                                <span
                                    className={cn(
                                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
                                        active
                                            ? "border-white/30 bg-white text-background"
                                            : "border-white/10 bg-white/5 text-foreground/60",
                                    )}
                                >
                                    <Icon className="h-4 w-4" />
                                </span>
                                <span className="min-w-0 pr-5">
                                    <span className="block text-sm font-medium text-foreground/90">
                                        {p.label}
                                    </span>
                                    <span className="mt-0.5 block text-xs leading-relaxed text-foreground/45">
                                        {p.hint}
                                    </span>
                                </span>
                                {active && (
                                    <Check className="absolute top-3 right-3 h-4 w-4 text-foreground/80" />
                                )}
                            </button>
                        );
                    })}
                </div>
            </section>

            {provider && (
                <Group title="Model">
                    <Row
                        stacked
                        label="Model name"
                        hint={
                            current.model
                                ? `Suggested: ${current.model}`
                                : "As the provider names it."
                        }
                        htmlFor="settings-model-name"
                    >
                        <input
                            id="settings-model-name"
                            value={model}
                            onChange={(e) => setModel(e.target.value)}
                            placeholder={current.model || "model"}
                            spellCheck={false}
                            className={field}
                        />
                    </Row>
                    {current.key && (
                        <Row
                            stacked
                            label="Your API key"
                            hint="Kept in this browser only and sent with your searches."
                            htmlFor="settings-api-key"
                        >
                            <input
                                id="settings-api-key"
                                type="password"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder="sk-…"
                                autoComplete="off"
                                className={field}
                            />
                        </Row>
                    )}
                </Group>
            )}

            <div className="flex items-center justify-end gap-3">
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
