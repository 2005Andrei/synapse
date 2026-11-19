import { useState } from "react";
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

export default function ModelSettings() {
    const saved = loadLlmChoice();
    const [provider, setProvider] = useState(saved?.model.split(":")[0] ?? "");
    const [model, setModel] = useState(
        saved?.model.split(":").slice(1).join(":") ?? "",
    );
    const [apiKey, setApiKey] = useState(saved?.api_key ?? "");
    const [note, setNote] = useState("");
    const current = PROVIDERS.find((p) => p.id === provider) ?? PROVIDERS[0];

    const field =
        "w-full rounded border border-white/15 bg-transparent px-2 py-1 text-xs text-white placeholder:text-neutral-600 focus:border-white/40 focus:outline-none";

    const save = () => {
        if (!provider) {
            saveLlmChoice(null);
            setNote("Using the server's model.");
        } else if (!model.trim()) {
            setNote("Name the model.");
        } else {
            saveLlmChoice({
                model: `${provider}:${model.trim()}`,
                api_key: current.key ? apiKey.trim() || undefined : undefined,
            });
            setNote("Saved. Used by the searches you start from now on.");
        }
    };

    return (
        <div className="mx-2 mb-2 flex flex-col gap-2 rounded-lg border border-white/15 p-3 text-xs">
            <label className="flex flex-col gap-1">
                <span className="text-neutral-400">AI model</span>
                <select
                    value={provider}
                    onChange={(e) => {
                        const next = PROVIDERS.find(
                            (p) => p.id === e.target.value,
                        )!;
                        setProvider(next.id);
                        setModel(next.model);
                        setNote("");
                    }}
                    className={`${field} bg-neutral-900`}
                >
                    {PROVIDERS.map((p) => (
                        <option key={p.id} value={p.id}>
                            {p.label}
                        </option>
                    ))}
                </select>
            </label>
            {provider && (
                <label className="flex flex-col gap-1">
                    <span className="text-neutral-400">Model name</span>
                    <input
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        placeholder={current.model || "model"}
                        spellCheck={false}
                        className={field}
                    />
                </label>
            )}
            {current.key && (
                <label className="flex flex-col gap-1">
                    <span className="text-neutral-400">Your API key</span>
                    <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="kept in this browser"
                        autoComplete="off"
                        className={field}
                    />
                </label>
            )}
            {provider === "ollama" && (
                <div className="text-neutral-500">
                    Runs on the machine the worker runs on; no key, nothing
                    leaves it.
                </div>
            )}
            <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 text-neutral-500">{note}</span>
                <button
                    type="button"
                    onClick={save}
                    className="shrink-0 cursor-pointer rounded border border-white/30 px-2 py-0.5 hover:bg-white/10"
                >
                    Save
                </button>
            </div>
        </div>
    );
}
