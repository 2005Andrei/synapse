import { useSidebar } from "../../providers/DashboardContext";
import { SnapToggle } from "../../utils/SnapToggle";

export default function DataContainer() {
    // container
    const activeView = useSidebar();

    return (
        <div className="flex flex-col h-full w-full justify-center items-center gap-5">
            data container
            <SnapToggle className="text-white" />
        </div>
    );
}
