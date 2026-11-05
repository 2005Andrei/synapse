import DashboardMain from "./main/DashboardMain";
import DashboardNavbar from "./main/navbar/DashboardNavbar";
import { DashboardProvider } from "./providers/DashboardContext";

export default function Dashboard() {
    return (
        <DashboardProvider>
            <main className="w-full h-full font-sans selection:text-foreground flex flex-col">
                <DashboardNavbar />
                <DashboardMain />
            </main>
        </DashboardProvider>
    );
}
