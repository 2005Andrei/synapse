import type { Run, RunEvent } from "./types";

export const API_URL: string =
    import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function createInvestigation(
    query: string,
    scrapers?: string[],
): Promise<Run> {
    const response = await fetch(`${API_URL}/api/investigations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, scrapers }),
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

export async function listInvestigations(limit = 8): Promise<Run[]> {
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
