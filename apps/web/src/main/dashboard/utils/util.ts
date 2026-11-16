export { cn } from "cn";

/** "A very long headline about…" : cut at a word boundary where possible. */
export function shorten(text: string, max: number): string {
    const clean = (text ?? "").trim();
    if (clean.length <= max) return clean;
    const cut = clean.slice(0, max - 1);
    const space = cut.lastIndexOf(" ");
    return `${(space > max * 0.6 ? cut.slice(0, space) : cut).trimEnd()}…`;
}

export const isUrl = (value: unknown): value is string =>
    typeof value === "string" && /^https?:\/\/\S+$/.test(value);

export function shortUrl(url: string, max = 44): string {
    try {
        const { host, pathname, search } = new URL(url);
        const site = host.replace(/^www\./, "");
        const path = pathname.replace(/\/$/, "") + search;
        if (!path) return site;
        const full = site + path;
        if (full.length <= max) return full;
        const tail = path.slice(-(max - site.length - 2));
        return `${site}/…${tail.replace(/^[^/-]*/, "")}`;
    } catch {
        return shorten(url, max);
    }
}

export async function copyText(text: string): Promise<boolean> {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand("copy");
        area.remove();
        return ok;
    }
}
