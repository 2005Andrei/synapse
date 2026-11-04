import { cn } from "cn";
import { zoneRect } from "../utils/snap";
import { useWM } from "../utils/store";
import { Window } from "../utils/Window";
import Graph from "./graph/Graph";
import DataContainer from "./sidebars/DataContainer";
import Sidebar from "./sidebars/Sidebar";
import { useEffect, useRef } from "react";

function SnapPreview() {
    const zone = useWM((s) => s.preview);
    const desk = useWM((s) => s.desk);
    const r = zone ? zoneRect(zone, desk) : null;
    return (
        <div
            className={cn(
                "pointer-events-none absolute z-[9999] rounded-lg border-2 border-primary/50 bg-primary/10 transition-all duration-150",
                !r && "opacity-0",
            )}
            style={
                r
                    ? { left: r.x, top: r.y, width: r.width, height: r.height }
                    : undefined
            }
        />
    );
}

export default function DashboardMain() {
    const deskRef = useRef<HTMLElement>(null);

    useEffect(() => {
        const ro = new ResizeObserver(([e]) =>
            useWM.getState().setDesk(e.contentRect.width, e.contentRect.height),
        );
        ro.observe(deskRef.current!);
        return () => ro.disconnect();
    }, []);
    return (
        <main
            className="w-full z-9999 flex-1 overflow-clip"
            id="desktop"
            ref={deskRef}
        >
            <Sidebar />
            <Graph />
            <Window id="data" key={0}>
                <DataContainer />
            </Window>
        </main>
    );
}
