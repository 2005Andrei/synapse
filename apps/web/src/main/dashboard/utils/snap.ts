export type ZoneId = "tl" | "tr" | "bl" | "br";
export type Desk = { w: number; h: number };

// x, y, width, height are fractions of the desktop
export const ZONES: Record<ZoneId, [number, number, number, number]> = {
    tl: [0, 0, 0.5, 0.5],
    tr: [0.5, 0, 0.5, 0.5],
    bl: [0, 0.5, 0.5, 0.5],
    br: [0.5, 0.5, 0.5, 0.5],
};

const EDGE = 24;
const GAP = 4;
const BAND = 40;

export function detectZone(
    px: number,
    py: number,
    { w, h }: Desk,
    prev: ZoneId | null = null,
): ZoneId | null {
    const onEdge = px < EDGE || px > w - EDGE || py < EDGE || py > h - EDGE;
    if (!onEdge) return null;

    const wasLeft = prev === "tl" || prev === "bl";
    const wasTop = prev === "tl" || prev === "tr";
    const left = prev
        ? wasLeft
            ? px < w / 2 + BAND
            : px < w / 2 - BAND
        : px < w / 2;
    const top = prev
        ? wasTop
            ? py < h / 2 + BAND
            : py < h / 2 - BAND
        : py < h / 2;

    return `${top ? "t" : "b"}${left ? "l" : "r"}` as ZoneId;
}

export function zoneRect(zone: ZoneId, { w, h }: Desk) {
    const [fx, fy, fw, fh] = ZONES[zone];
    return {
        x: Math.round(fx * w) + GAP,
        y: Math.round(fy * h) + GAP,
        width: Math.round(fw * w) - GAP * 2,
        height: Math.round(fh * h) - GAP * 2,
    };
}

type P = { clientX: number; clientY: number };

export function pointer(e: unknown) {
    const ev = e as Partial<P> & {
        touches?: ArrayLike<P>;
        changedTouches?: ArrayLike<P>;
    };
    const t = ev.touches?.[0] ?? ev.changedTouches?.[0] ?? ev;
    return { x: t.clientX ?? 0, y: t.clientY ?? 0 };
}
