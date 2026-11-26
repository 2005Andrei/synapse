import { useWM } from "../../utils/store";
import { INVESTIGATION_WINDOW } from "./window";

export function openInvestigationWindow() {
    useWM.getState().openWindow(INVESTIGATION_WINDOW);
}
