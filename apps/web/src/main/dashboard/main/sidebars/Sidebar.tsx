import { SidebarLinks } from "./utils/SidebarLinks";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { cn } from "cn";

export default function Sidebar() {
    const links = [
        {
            title: "Projects",
            subprojects: [
                {
                    id: "p-1",
                    label: "mock 1",
                    onClick: () => console.log("clicked"),
                    isActive: true,
                },
                {
                    id: "p-2",
                    label: "mock 2",
                    onClick: () => console.log("clicked"),
                    isActive: false,
                },
                {
                    id: "p-3",
                    label: "mock 3",
                    onClick: () => console.log("clicked"),
                    isActive: false,
                },
            ],
        },
        {
            title: "Notes",
            subprojects: [
                {
                    id: "n-1",
                    label: "note 1",
                    onClick: () => console.log("click"),
                    isActive: false,
                },
                {
                    id: "n-2",
                    label: "note 2",
                    onClick: () => console.log("click"),
                    isActive: true,
                },
                {
                    id: "n-3",
                    label: "note 3",
                    onClick: () => console.log("click"),
                    isActive: false,
                },
                {
                    id: "new-note",
                    label: "+ New Note",
                    onClick: () => console.log("created new note"),
                    isActive: false,
                },
            ],
        },
        {
            title: "Settings",
            onClick: () => console.log("Toggled settings modal"),
        },
    ];

    const notifications_data = [
        {
            title: "Search",
            summary: "/search",
            progress: 50,
        },
        {
            title: "Search",
            summary: "/search",
            progress: 50,
        },
        {
            title: "Search",
            summary: "/search",
            progress: 50,
        },
        {
            title: "Search",
            summary: "/search",
            progress: 50,
        },
    ];

    const [isCompact, setIsCompact] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const observer = new ResizeObserver((entries) => {
            for (let entry of entries) {
                setIsCompact(entry.contentRect.width < 100);
            }
        });

        if (containerRef.current) {
            observer.observe(containerRef.current);
        }

        return () => observer.disconnect();
    }, []);

    return (
        <div className="w-1/5 max-w-[400px] flex h-screen flex-col p-7 border-r-2 bg-transparent">
            <div
                className="mb-6 flex items-center gap-2 px-2"
                ref={containerRef}
            >
                <span className="font-semibold tracking-tight">
                    {/*  
                    className={cn(
                        isCompact ? "hidden" : "font-semibold tracking-tight",
                    )}
                */}
                    Workspace
                </span>
            </div>
            <SidebarLinks data={links} />
        </div>
    );
}
