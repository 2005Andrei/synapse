import { create } from "zustand";
import type { Desk, ZoneId } from "./snap";

export type Win = {
    id: string;
    kind: string;
    title: string;
    x: number;
    y: number;
    width: number;
    height: number;
    z: number;
    minimized: boolean;
    maximized: boolean;
    snap: ZoneId | null;
    props?: Record<string, unknown>;
};

export type OpenSpec = {
    id: string;
    kind: string;
    title: string;
    x?: number;
    y?: number;
    width?: number | null;
    height?: number | null;
    props?: Record<string, unknown>;
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
    openWindow: (spec: OpenSpec) => void;
    closeWindow: (id: string) => void;
};

const base = { z: 0, minimized: false, maximized: false, snap: null };
const initial: Win[] = [
    {
        id: "data",
        kind: "data",
        title: "Data",
        x: 0.72,
        y: 0,
        width: 0.25,
        height: 1 / 1.05,
        ...base,
    },
];

export const useWM = create<Store>((set) => ({
    wins: Object.fromEntries(initial.map((w, i) => [w.id, { ...w, z: i + 1 }])),
    topZ: initial.length,
    focused: null,
    desk: { w: 0, h: 0 },
    preview: null,

    openWindow: (spec) =>
        set((s) => {
            const z = s.topZ + 1;
            const existing = s.wins[spec.id];

            if (existing) {
                return {
                    topZ: z,
                    focused: spec.id,
                    wins: {
                        ...s.wins,
                        [spec.id]: { ...existing, minimized: false, z },
                    },
                };
            }

            const offset = (Object.keys(s.wins).length % 8) * 0.03;
            const win: Win = {
                x: 0.1 + offset,
                y: 0.1 + offset,
                width: 0.3,
                height: 0.4,
                minimized: false,
                maximized: false,
                snap: null,
                ...spec,
                z,
            };
            return {
                topZ: z,
                focused: spec.id,
                wins: { ...s.wins, [spec.id]: win },
            };
        }),

    closeWindow: (id) =>
        set((s) => {
            const wins = { ...s.wins };
            delete wins[id];
            return {
                wins,
                focused: s.focused === id ? null : s.focused,
                preview: null,
            };
        }),

    setDesk: (w, h) =>
        set((s) => (s.desk.w === w && s.desk.h === h ? s : { desk: { w, h } })),
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
