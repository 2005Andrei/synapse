import { createContext, useContext, useState, type ReactNode } from "react";

interface DashboardContextType {
    activeView: string;
    setActiveView: (view: string) => void;
}

const DashboardContext = createContext<DashboardContextType | undefined>(
    undefined,
);

export function DashboardProvider({ children }: { children: ReactNode }) {
    const [activeView, setActiveView] = useState<string>("about");

    return (
        <DashboardContext.Provider value={{ activeView, setActiveView }}>
            {children}
        </DashboardContext.Provider>
    );
}

export function useSidebar() {
    const context = useContext(DashboardContext);
    if (context === undefined) {
        throw new Error("you alr know");
    }
    return context;
}
