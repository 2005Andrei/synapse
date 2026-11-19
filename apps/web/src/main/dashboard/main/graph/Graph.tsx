import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import ForceGraph3D from "react-force-graph-3d";
import * as THREE from "three";
import MOCK_DATA from "./mock_data.json";

import { createNodeObject } from "./graph/nodeRenderer";
import {
    createLinkThreeObject,
    updateLinkPosition,
    getLinkId,
    getLinkColor,
} from "./graph/linkRenderer";
import { reconcileGraph, transformData } from "./lib/util";
import {
    isLive,
    useActiveRun,
    useInvestigation,
} from "../../providers/investigation/store";
import NodeMenu, { SEARCHABLE } from "./NodeMenu";
import { useWM } from "../../utils/store";
import { shorten } from "../../utils/util";
import {
    divide,
    identityLabel,
} from "../../providers/investigation/identities";

const MOCK_SOURCES = Object.fromEntries(
    MOCK_DATA.sources.map((s) => [s.id, s]),
);

function sourcesOf(link) {
    const { activeKey, runs } = useInvestigation.getState();
    const known = activeKey ? runs[activeKey].sources : MOCK_SOURCES;
    return (link.sourceIds || [])
        .map((id) => known[id])
        .filter(Boolean)
        .map((source) => ({ title: source.title, url: source.url }));
}

export default function Graph() {
    const graphRef = useRef(null);
    const minimapCanvasRef = useRef(null);
    const isDraggingMinimap = useRef(false);
    const lastMousePos = useRef({ x: 0, y: 0 });

    const [selectedNode, setSelectedNode] = useState(null);
    const [hoveredNode, setHoveredNode] = useState(null);

    const [selectedLink, setSelectedLink] = useState(null);
    const [menu, setMenu] = useState(null); // right-click menu: { x, y, node }

    const [toggledLinks, setToggledLinks] = useState(() => new Set());
    const [hoveredLinkId, setHoveredLinkId] = useState(null);

    const run = useActiveRun();
    const allRuns = useInvestigation((s) => s.runs);
    const closeMenu = useCallback(() => setMenu(null), []);
    const live = run !== null;
    const liveEntities = run?.entities;
    const liveClaims = run?.claims;
    const lastGraph = useRef({ nodes: [], links: [] });

    const focus = run?.focus ?? null;
    const focused = useMemo(() => {
        if (!run || !focus) return null;
        const { identities, groupOf } = divide(run);
        const identity = identities.find((i) => i.id === focus);
        return identity ? { identity, groupOf } : null;
    }, [run, focus]);

    const graphData = useMemo(() => {
        let entities = live ? Object.values(liveEntities) : MOCK_DATA.entities;
        if (focused)
            entities = entities.filter((e) => focused.groupOf[e.id] === focus);

        const next = transformData({
            entities,
            claims: live ? Object.values(liveClaims) : MOCK_DATA.claims,
        });
        lastGraph.current = reconcileGraph(lastGraph.current, next);
        return lastGraph.current;
    }, [live, liveEntities, liveClaims, focused, focus]);

    useEffect(() => {
        let animationFrameId;

        const renderMinimap = () => {
            const canvas = minimapCanvasRef.current;
            if (!canvas || !graphRef.current) {
                animationFrameId = requestAnimationFrame(renderMinimap);
                return;
            }

            const ctx = canvas.getContext("2d");
            const w = canvas.width;
            const h = canvas.height;
            const centerX = w / 2;
            const centerY = h / 2;

            ctx.clearRect(0, 0, w, h);

            const camera = graphRef.current.camera();
            const controls = graphRef.current.controls();
            const target = controls?.target || new THREE.Vector3(0, 0, 0);
            const nodes = graphData.nodes;

            let maxCoord = 250;
            nodes.forEach((n) => {
                if (n.x !== undefined && n.z !== undefined) {
                    maxCoord = Math.max(maxCoord, Math.abs(n.x), Math.abs(n.z));
                }
            });
            const scale = (w / 2 - 16) / maxCoord;

            ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(centerX, centerY, w * 0.44, 0, Math.PI * 2);
            ctx.arc(centerX, centerY, w * 0.25, 0, Math.PI * 2);
            ctx.stroke();

            nodes.forEach((node) => {
                if (node.x === undefined || node.z === undefined) return;
                const px = centerX + node.x * scale;
                const py = centerY + node.z * scale;

                ctx.fillStyle = node.color || "#ffffff";
                ctx.beginPath();
                ctx.arc(
                    px,
                    py,
                    selectedNode?.id === node.id ? 4 : 2,
                    0,
                    Math.PI * 2,
                );
                ctx.fill();
            });

            if (camera) {
                const camX = centerX + camera.position.x * scale;
                const camY = centerY + camera.position.z * scale;
                const tgtX = centerX + target.x * scale;
                const tgtY = centerY + target.z * scale;

                const targetAngle = Math.atan2(tgtY - camY, tgtX - camX);
                const fovSpread = 0.45;
                const viewDist = 26;

                ctx.fillStyle = "rgba(0, 210, 255, 0.18)";
                ctx.beginPath();
                ctx.moveTo(camX, camY);
                ctx.arc(
                    camX,
                    camY,
                    viewDist,
                    targetAngle - fovSpread,
                    targetAngle + fovSpread,
                );
                ctx.closePath();
                ctx.fill();

                ctx.fillStyle = "#00d2ff";
                ctx.beginPath();
                ctx.arc(camX, camY, 3.5, 0, Math.PI * 2);
                ctx.fill();

                ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
                ctx.beginPath();
                ctx.arc(tgtX, tgtY, 3, 0, Math.PI * 2);
                ctx.stroke();
            }

            animationFrameId = requestAnimationFrame(renderMinimap);
        };

        animationFrameId = requestAnimationFrame(renderMinimap);
        return () => cancelAnimationFrame(animationFrameId);
    }, [graphData, selectedNode]);

    const handleMinimapMouseDown = (e) => {
        isDraggingMinimap.current = true;
        lastMousePos.current = { x: e.clientX, y: e.clientY };
    };

    useEffect(() => {
        const handleMouseMove = (e) => {
            if (!isDraggingMinimap.current || !graphRef.current) return;

            const deltaX = e.clientX - lastMousePos.current.x;
            const deltaY = e.clientY - lastMousePos.current.y;
            lastMousePos.current = { x: e.clientX, y: e.clientY };

            const camera = graphRef.current.camera();
            const controls = graphRef.current.controls();
            if (!camera || !controls) return;

            const distance = camera.position.distanceTo(controls.target);
            const panFactor = Math.max(distance * 0.0018, 0.4);

            const right = new THREE.Vector3();
            const up = new THREE.Vector3();
            camera.matrixWorld.extractBasis(right, up, new THREE.Vector3());

            const translation = new THREE.Vector3()
                .addScaledVector(right, -deltaX * panFactor)
                .addScaledVector(up, deltaY * panFactor);

            camera.position.add(translation);
            controls.target.add(translation);
            controls.update();
        };

        const handleMouseUp = () => {
            isDraggingMinimap.current = false;
        };

        window.addEventListener("mousemove", handleMouseMove);
        window.addEventListener("mouseup", handleMouseUp);
        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            window.removeEventListener("mouseup", handleMouseUp);
        };
    }, []);

    const openWindow = useWM((s) => s.openWindow);

    const handleNodeClick = useCallback((node) => {
        setSelectedNode(node);

        openWindow({
            id: `node:${node.id}`,
            kind: "nodeInfo",
            title: shorten(node.label, 38),
            x: 0.2,
            y: 0.08,
            width: null,
            height: null,
            props: {
                label: node.label,
                type: node.type,
                color: node.color,
                description: node.description,
                attributes: node.attributes,
            },
        });

        if (!graphRef.current) return;

        const cameraDistance = 180;
        const hyp = Math.hypot(node.x || 0, node.y || 0, node.z || 0);
        const distRatio = hyp === 0 ? 1 : 1 + cameraDistance / hyp;

        graphRef.current.cameraPosition(
            {
                x: (node.x || 0) * distRatio,
                y: (node.y || 0) * distRatio,
                z: (node.z || 0) * distRatio + (hyp === 0 ? cameraDistance : 0),
            },
            node,
            1500,
        );
    }, []);

    const handleLinkClick = useCallback((link) => {
        // storeClickPosition(link, event, graphRef);

        // console.log(link.source);
        setSelectedLink(link);

        // node labels can be whole headlines: the title bar gets a short
        // "A → B", the window body has the full text.
        const from = link.source?.label ?? "?";
        const to = link.target?.label ?? "?";

        openWindow({
            id: `link:${link.id}`,
            kind: "linkInfo",
            title: `${shorten(from, 16)} → ${shorten(to, 16)}`,
            x: 0.4,
            y: 0.5,
            width: null,
            height: null,
            props: {
                label: link.label ? link.label : "Link",
                color: link.color,
                sourceLabel: from,
                targetLabel: to,
                confidence: link.confidence,
                status: link.status,
                text: link.text,
                quote: link.quote,
                sources: sourcesOf(link),
            },
        });

        const key = `${getLinkId(link.source)}-${getLinkId(link.target)}`;
        setToggledLinks((prev) => {
            const next = new Set(prev);
            next.has(key) ? next.delete(key) : next.add(key);
            return next;
        });
    }, []);

    const selectedNodeWindowOpen = useWM((s) =>
        selectedNode ? `node:${selectedNode.id}` in s.wins : true,
    );
    const selectedLinkWindowOpen = useWM((s) =>
        selectedLink ? `link:${selectedLink.id}` in s.wins : true,
    );

    useEffect(() => {
        if (!selectedNodeWindowOpen) setSelectedNode(null);
    }, [selectedNodeWindowOpen]);

    useEffect(() => {
        if (!selectedLinkWindowOpen) setSelectedLink(null);
    }, [selectedLinkWindowOpen]);

    // const handleLinkClick = useCallback((link, event) => {
    //     storeClickPosition(link, event, graphRef);
    //
    //     const key = `${getLinkId(link.source)}-${getLinkId(link.target)}`;
    //     setToggledLinks((prev) => {
    //         const next = new Set(prev);
    //         next.has(key) ? next.delete(key) : next.add(key);
    //         return next;
    //     });
    // }, []);

    const handleLinkHover = useCallback((link) => {
        setHoveredLinkId(
            link ? `${getLinkId(link.source)}-${getLinkId(link.target)}` : null,
        );
    }, []);

    // Right-click menu: what "Search further" would do for that node.
    const menuChild =
        menu && run
            ? Object.values(allRuns).find(
                  (r) =>
                      r.parentKey === run.key &&
                      r.entityId === menu.node.id &&
                      r.phase !== "failed",
              )
            : null;
    const menuBlocked = !menu
        ? null
        : !SEARCHABLE.has(menu.node.type)
          ? "Only people and companies can be searched"
          : !run?.runId
            ? "Start a search first: this is sample data"
            : menu.node.id === run.seedId
              ? "This is what the search is about"
              : null;

    return (
        <div className="relative w-full h-full overflow-hidden">
            {menu && (
                <NodeMenu
                    menu={menu}
                    blocked={menuBlocked}
                    status={
                        menuChild
                            ? isLive(menuChild.phase)
                                ? "Searching…"
                                : "Already searched further"
                            : null
                    }
                    onSearch={() =>
                        useInvestigation
                            .getState()
                            .expand(run.key, run.entities[menu.node.id])
                    }
                    onDetails={() => handleNodeClick(menu.node)}
                    onClose={closeMenu}
                />
            )}
            <ForceGraph3D
                ref={graphRef}
                graphData={graphData}
                backgroundColor="rgba(0, 0, 0, 0)"
                onNodeClick={handleNodeClick}
                onNodeRightClick={(node, event) => {
                    event.preventDefault?.();
                    setMenu({ x: event.clientX, y: event.clientY, node });
                }}
                onNodeHover={setHoveredNode}
                nodeThreeObject={(node) =>
                    createNodeObject(
                        node,
                        selectedNode?.id === node.id,
                        hoveredNode?.id === node.id,
                    )
                }
                onLinkClick={handleLinkClick}
                onLinkHover={handleLinkHover}
                linkWidth={0.3}
                linkHoverPrecision={8}
                linkColor={(link) =>
                    getLinkColor(link, selectedNode?.id, null, hoveredLinkId)
                }
                linkOpacity={0.7}
                linkDirectionalParticles={(link) => {
                    const src = getLinkId(link.source);
                    const tgt = getLinkId(link.target);
                    return selectedNode?.id === src || selectedNode?.id === tgt
                        ? 1
                        : 0;
                }}
                linkDirectionalParticleSpeed={0.007}
                linkDirectionalParticleWidth={0.5}
                linkThreeObjectExtend={true}
                linkThreeObject={(link) => {
                    const key = `${getLinkId(link.source)}-${getLinkId(link.target)}`;
                    const isVisible =
                        hoveredLinkId === key || toggledLinks.has(key);
                    return createLinkThreeObject(link, isVisible);
                }}
                linkPositionUpdate={(sprinte, coords, link) =>
                    updateLinkPosition(sprinte, coords, link, graphRef)
                }
            />

            {focused && (
                <button
                    type="button"
                    onClick={() =>
                        useInvestigation.getState().setFocus(run.key, null)
                    }
                    title="Show the whole graph again"
                    className="absolute bottom-10 left-1/2 z-10 -translate-x-1/2 cursor-pointer rounded-full border border-white/20 bg-[rgba(15,15,20,0.85)] px-4 py-1.5 font-mono text-[11px] text-white backdrop-blur-[12px] hover:border-white/50"
                >
                    <span className="mr-2 uppercase tracking-[1px] text-[#ffd166]">
                        {identityLabel(focused.identity)}
                    </span>
                    {shorten(focused.identity.name, 40)}
                    <span className="ml-3 text-[#888]">show all ✕</span>
                </button>
            )}

            <div className="absolute bottom-10 left-6 w-[210px] h-[150px] bg-[rgba(15,15,20,0.85)] border border-white/15 rounded-xl backdrop-blur-[12px] shadow-[0_8px_32px_rgba(0,0,0,0.5)] z-10 flex flex-col items-center justify-center select-none">
                <div className="absolute top-2 left-[10px] text-[9px] font-bold tracking-[0.8px] text-white/50 uppercase font-mono pointer-events-none">
                    Minimap
                </div>

                <canvas
                    ref={minimapCanvasRef}
                    width={150}
                    height={150}
                    onMouseDown={handleMinimapMouseDown}
                    className="cursor-move block mt-2.5"
                />
            </div>
        </div>
    );
}
