import { useSidebar } from "../../providers/DashboardContext";
import { useState } from "react";
import { useInvestigation } from "../../providers/investigation/store";
import { VIEWS } from "../../providers/views";
import { openInvestigationWindow } from "../investigation/open";

export default function DashboardNavbar() {
    const { activeView, setActiveView } = useSidebar();

    const [query, setQuery] = useState("");

    const handleSearch = () => {
        const text = query.trim();
        if (text.length < 2) return;

        useInvestigation.getState().start(text);
        setActiveView("about");
        openInvestigationWindow();
        setQuery("");
    };

    const handleNavClick = (id: string) => {
        setActiveView(id);
        openInvestigationWindow();
    };

    return (
        <nav className="absolute top-0 left-0 w-full h-20 text-primary font-mono p-4 sm:px-6 flex flex-wrap items-center justify-between gap-y-5 z-999">
            <div className="flex flex-col items-start"></div>

            <div className="hidden md:flex order-3 lg:order-2 w-full lg:w-auto lg:flex-1 lg:mx-12 items-center border-b border-gray-700/80 pb-1.5 mt-1 lg:mt-0 max-w-[500px]">
                <span className="text-primary mr-3">/</span>
                <input
                    type="text"
                    placeholder="search entity, company, person.."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    className="bg-transparent border-none outline-none w-full text-xs placeholder-gray-600 focus:ring-0 capitalize max-width-[300px] z-999"
                />
            </div>

            <div className="flex-none order-2 lg:order-3 flex items-center gap-4 lg:gap-6 text-[10px] sm:text-xs uppercase tracking-wider mt-0 lg:mt-1 z-999">
                {VIEWS.map((link) => {
                    const isActive = activeView === link.id;

                    return (
                        <div
                            key={link.id}
                            className={`flex items-center gap-1.5 cursor-pointer ${link.hideOnMobile ? "hidden sm:flex" : "flex"}`}
                            onClick={() => handleNavClick(link.id)}
                            title={link.hint}
                        >
                            {isActive && (
                                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
                            )}

                            <span
                                className={`transition-colors ${isActive ? "text-secondary-foreground" : "hover:text-secondary-foreground"}`}
                            >
                                {link.label}
                            </span>
                        </div>
                    );
                })}
            </div>
        </nav>
    );
}
