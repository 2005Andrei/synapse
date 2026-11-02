import DashboardMain from "./main/DashboardMain";
import DashboardNavbar from "./main/navbar/DashboardNavbar";
import { DashboardProvider } from "./providers/DashboardContext";

export default function Dashboard() {
    return (
        <DashboardProvider>
            <div className="w-full h-screen font-sans selection:text-foreground">
                <DashboardNavbar />
                <DashboardMain />
            </div>
        </DashboardProvider>
    );
}
