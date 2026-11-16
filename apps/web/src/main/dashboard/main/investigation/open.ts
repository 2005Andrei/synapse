import { useWM } from "../../utils/store";

export function openInvestigationWindow() {
    useWM.getState().openWindow({
        id: "investigation",
        kind: "investigation",
        title: "Investigation",
        x: 0.21,
        y: 0.1,
        width: 0.34,
        height: 0.72,
    });
}
