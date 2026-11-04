import { create } from "zustand";
import type { Desk, ZoneId } from "./snap";

export type Win = {
    id: string;
    title: string;
    x: number;
    y: number;
    width: number;
    height: number;
    z: number;
    minimized: boolean;
    maximized: boolean;
    snap: ZoneId | null;
};

type Store = {
    wins: Record<string, Win>;
    topZ: number;
    focused: string | null;
    desk: Desk;
    preview: ZoneId | null;
    setDesk: (w: number, h: number) => void;
    setPreview: (z: ZoneId | null) => void;
    focus: (id: string) => void;
    patch: (id: string, p: Partial<Win>) => void;
    toggleMin: (id: string) => void;
    toggleMax: (id: string) => void;
    snapEnabled: boolean;
    setSnapEnabled: (on: boolean) => void;
    toggleSnap: () => void;
};

const base = { z: 0, minimized: false, maximized: false, snap: null };
const pageWidth = window.innerWidth;
const pageHeight = window.innerHeight;
const dataWidth = window.innerWidth * 0.25;
const initial: Win[] = [
    {
        id: "data",
        title: "Data",
        x: pageWidth - dataWidth - 40,
        y: 0,
        width: dataWidth,
        height: pageHeight / 1.2,
        ...base,
    },
];

export const useWM = create<Store>((set) => ({
    wins: Object.fromEntries(initial.map((w, i) => [w.id, { ...w, z: i + 1 }])),
    topZ: initial.length,
    focused: null,
    desk: { w: 0, h: 0 },
    preview: null,

    setDesk: (w, h) =>
        set((s) => {
            const { w: ow, h: oh } = s.desk;

            if (!w || !h) return s;
            if (!ow || !oh || (ow === w && oh === h)) return { desk: { w, h } };

            const rx = w / ow;
            const ry = h / oh;

            const wins = Object.fromEntries(
                Object.entries(s.wins).map(([id, win]) => [
                    id,
                    {
                        ...win,
                        x: win.x * rx,
                        y: win.y * ry,
                        width: win.width * rx,
                        height: win.height * ry,
                    },
                ]),
            );

            return { desk: { w, h }, wins };
        }),
    setPreview: (z) => set((s) => (s.preview === z ? s : { preview: z })),

    focus: (id) =>
        set((s) => {
            if (s.focused === id) return s;
            const z = s.topZ + 1;
            return {
                topZ: z,
                focused: id,
                wins: { ...s.wins, [id]: { ...s.wins[id], z } },
            };
        }),

    patch: (id, p) =>
        set((s) => ({ wins: { ...s.wins, [id]: { ...s.wins[id], ...p } } })),

    toggleMin: (id) =>
        set((s) => {
            const w = s.wins[id];
            const restoring = w.minimized;
            const z = restoring ? s.topZ + 1 : s.topZ;
            return {
                topZ: z,
                focused: restoring ? id : s.focused === id ? null : s.focused,
                wins: {
                    ...s.wins,
                    [id]: {
                        ...w,
                        minimized: !restoring,
                        z: restoring ? z : w.z,
                    },
                },
            };
        }),

    toggleMax: (id) =>
        set((s) => ({
            wins: {
                ...s.wins,
                [id]: { ...s.wins[id], maximized: !s.wins[id].maximized },
            },
        })),

    snapEnabled: false,
    setSnapEnabled: (on) =>
        set((s) => ({
            snapEnabled: !s.snapEnabled,
            preview: on ? s.preview : null,
        })),

    toggleSnap: () =>
        set((s) => ({
            snapEnabled: !s.snapEnabled,
            preview: s.snapEnabled ? null : s.preview,
        })),
}));
