import Graph from "./graph/Graph";
import DataContainer from "./sidebars/DataContainer";
import Sidebar from "./sidebars/Sidebar";

export default function DashboardMain() {
    return (
        <>
            <Sidebar />
            <Graph />
            <DataContainer />
        </>
    );
}
