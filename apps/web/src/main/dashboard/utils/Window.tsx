import { useState, type ReactNode } from "react";
import { Rnd } from "react-rnd";
import { Minus, Maximize2, Minimize2, X } from "lucide-react";
import { useWM } from "./store";
import { cn } from "./util";
import { detectZone, pointer, zoneRect, type ZoneId } from "./snap";

const deskBox = () =>
    document.getElementById("desktop")!.getBoundingClientRect();

export function Window({
    id,
    zones, // optional  restrict which zones this window can snap to
    children,
}: {
    id: string;
    zones?: ZoneId[];
    children: ReactNode;
    onClose?: () => void;
}) {
    const w = useWM((s) => s.wins[id]);
    const desk = useWM((s) => s.desk);
    const focused = useWM((s) => s.focused === id);
    const { focus, patch, toggleMin, toggleMax, setPreview } = useWM.getState();
    const [busy, setBusy] = useState(false);

    const free = w.snap
        ? zoneRect(w.snap, desk)
        : {
              x: w.x * desk.w,
              y: w.y * desk.h,
              width: w.width === null ? "auto" : w.width * desk.w, // important is to give the children a minimum intrinsic size
              height: w.height === null ? "auto" : w.height * desk.h,
          };

    return (
        <Rnd
            bounds="parent"
            dragHandleClassName="win-handle"
            cancel=".no-drag"
            minWidth={220}
            minHeight={120}
            className={cn(
                !busy &&
                    "transition-[transform,width,height] duration-150 ease-out",
            )}
            position={w.maximized ? { x: 0, y: 0 } : { x: free.x, y: free.y }}
            size={
                w.maximized
                    ? { width: "100%", height: "100%" }
                    : { width: free.width, height: free.height }
            }
            disableDragging={w.maximized}
            enableResizing={!w.maximized}
            onMouseDown={() => focus(id)}
            onDragStart={() => setBusy(true)}
            onDrag={(e) => {
                const s = useWM.getState();
                const cur = s.wins[id];
                const r = deskBox();
                if (!r) return;
                const p = pointer(e);
                const px = p.x - r.left;
                const py = p.y - r.top;

                if (cur.snap) {
                    const from = zoneRect(cur.snap, s.desk);
                    const fx = (px - from.x) / from.width;
                    const curW = cur.width * s.desk.w;
                    patch(id, {
                        snap: null,
                        x:
                            Math.min(
                                Math.max(px - curW * fx, 0),
                                s.desk.w - curW,
                            ) / s.desk.w,
                        y: Math.max(py - 16, 0) / s.desk.h,
                    });
                }

                if (!s.snapEnabled) {
                    setPreview(null);
                    return;
                }
                const z = detectZone(px, py, s.desk, s.preview);
                setPreview(z && (!zones || zones.includes(z)) ? z : null);
            }}
            onDragStop={(_, d) => {
                setBusy(false);
                const s = useWM.getState();
                const zone = s.snapEnabled ? s.preview : null;
                setPreview(null);
                if (zone) patch(id, { snap: zone });
                else if (!s.wins[id].snap)
                    patch(id, { x: d.x / s.desk.w, y: d.y / s.desk.h });
            }}
            onResizeStart={() => setBusy(true)}
            onResizeStop={(_, __, ref, ___, pos) => {
                setBusy(false);
                const { w: dw, h: dh } = useWM.getState().desk;
                patch(id, {
                    width: ref.offsetWidth / dw,
                    height: ref.offsetHeight / dh,
                    x: pos.x / dw,
                    y: pos.y / dh,
                    snap: null,
                });
            }}
            style={{ zIndex: w.z, display: w.minimized ? "none" : undefined }}
        >
            <div
                className={cn(
                    "flex h-full flex-col overflow-hidden border border-border/50 bg-card/70 text-card-foreground rounded-sm", // maybe shodow-md
                    focused && "shadow-xl ring-1 ring-ring/40",
                )}
            >
                <div
                    className="win-handle flex h-8 shrink-0 cursor-all-scroll select-none items-center justify-between px-3 text-xs font-medium"
                    onDoubleClick={() => toggleMax(id)}
                >
                    <span className={cn(!focused && "text-muted-foreground")}>
                        {w.title}
                    </span>
                    <div className="no-drag flex gap-1">
                        <button
                            onClick={() => toggleMin(id)}
                            className="rounded p-1 hover:bg-accent hover:cursor-pointer"
                            aria-label="Minimize"
                        >
                            <Minus size={12} />
                        </button>
                        <button
                            onClick={() => toggleMax(id)}
                            className="rounded p-1 hover:bg-accent hover:cursor-pointer"
                            aria-label="Maximize"
                        >
                            {w.maximized ? (
                                <Minimize2 size={12} />
                            ) : (
                                <Maximize2 size={12} />
                            )}
                        </button>
                        <button
                            onClick={() => useWM.getState().closeWindow(id)}
                            className="rounded p-1 hover:bg-accent hover:cursor-pointer"
                            aria-label="Close"
                        >
                            <X size={12} />
                        </button>
                    </div>
                </div>
                <div className="min-h-0 flex-1 overflow-auto">{children}</div>
            </div>
        </Rnd>
    );
}
