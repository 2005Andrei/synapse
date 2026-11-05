import { motion, AnimatePresence } from "motion/react";
import { cn } from "cn";

interface DockIconProps {
    id: string;
    title: string;
    isFocused: boolean;
    isMinimized: boolean;
    isHovered: boolean;
    onHoverEnter: () => void;
    onHoverLeave: () => void;
    onClick: () => void;
}

export function DockIcon({
    title,
    isFocused,
    isMinimized,
    isHovered,
    onHoverEnter,
    onHoverLeave,
    onClick,
}: DockIconProps) {
    return (
        <div
            className="relative flex h-10 w-full shrink-0 items-center justify-center group cursor-pointer"
            onMouseEnter={onHoverEnter}
            onMouseLeave={onHoverLeave}
        >
            {isHovered && (
                <motion.div
                    layoutId="dock-hover-pill"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-x-1 inset-y-0 cursor-pointer rounded-xl bg-accent/20 z-0"
                />
            )}

            <button
                onClick={onClick}
                className={cn(
                    "relative z-10 flex h-8 w-8 items-center justify-center rounded-xl font-semibold transition-all duration-200 cursor-pointer",
                    isFocused && !isMinimized
                        ? "text-accent shadow-sm"
                        : "text-muted-foreground hover:text-foreground",
                    isMinimized
                        ? "opacity-50 grayscale scale-90"
                        : "opacity-100 scale-100",
                )}
            >
                {title[0].toUpperCase()}
            </button>

            {!isMinimized && (
                <div
                    className={cn(
                        "absolute right-0 h-1.5 w-1.5 rounded-full transition-colors duration-200",
                        isFocused
                            ? "bg-accent shadow-[0_0_8px_rgba(99,102,241,0.8)]"
                            : "bg-muted-foreground/30",
                    )}
                />
            )}

            <AnimatePresence>
                {isHovered && (
                    <motion.div
                        initial={{ opacity: 0, x: 10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 10 }}
                        transition={{ duration: 0.15, ease: "easeOut" }}
                        className="absolute right-full mr-4 pointer-events-none z-50 rounded-md border border-foreground/10 bg-background/80 backdrop-blur-md px-3 py-1.5 text-xs font-medium text-foreground shadow-lg whitespace-nowrap"
                    >
                        {title}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
