import type { Entity, LlmChoice, Run, RunEvent } from "./types";

export const API_URL: string =
    import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const LLM_KEY = "synapse:llm";

/** The user's own model and key, if they set one in Settings. It lives in
 *  this browser only and is sent along with each search they start. */
export function loadLlmChoice(): LlmChoice | null {
    try {
        const stored = JSON.parse(localStorage.getItem(LLM_KEY) ?? "null");
        return stored && typeof stored.model === "string" && stored.model
            ? stored
            : null;
    } catch {
        return null;
    }
}

export function saveLlmChoice(choice: LlmChoice | null): void {
    try {
        if (choice?.model) localStorage.setItem(LLM_KEY, JSON.stringify(choice));
        else localStorage.removeItem(LLM_KEY);
    } catch {
        // Storage unavailable: the server's default model is used.
    }
}

export async function createInvestigation(
    query: string,
    /** Search an entity of an existing run's graph further. */
    further?: { parentId: string; seed: Entity },
): Promise<Run> {
    const response = await fetch(`${API_URL}/api/investigations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            query,
            parent_id: further?.parentId,
            seed: further?.seed,
            llm: loadLlmChoice() ?? undefined,
        }),
    });
    if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail = body?.detail;
        throw new Error(
            typeof detail === "string"
                ? detail
                : `could not start investigation (HTTP ${response.status})`,
        );
    }
    return response.json();
}

export async function listInvestigations(limit = 24): Promise<Run[]> {
    const response = await fetch(
        `${API_URL}/api/investigations?limit=${limit}`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

export function forgetInvestigation(runId: string): void {
    void fetch(`${API_URL}/api/investigations/${runId}`, {
        method: "DELETE",
    }).catch(() => {});
}

export function followInvestigation(
    runId: string,
    onEvent: (event: RunEvent) => void,
    onLost: () => void,
): () => void {
    const stream = new EventSource(
        `${API_URL}/api/investigations/${runId}/events`,
    );

    stream.onmessage = (message) => {
        const event = JSON.parse(message.data) as RunEvent;
        onEvent(event);
        if (event.type === "run.completed" || event.type === "run.failed") {
            stream.close();
        }
    };

    stream.onerror = () => {
        if (stream.readyState === EventSource.CLOSED) onLost();
    };

    return () => stream.close();
}
