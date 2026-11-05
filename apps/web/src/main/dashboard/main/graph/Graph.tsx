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
    getLinkWidth,
} from "./graph/linkRenderer";
import { transformData } from "./lib/util";
import { Window } from "../../utils/Window";

export default function Graph() {
    const graphRef = useRef(null);
    const minimapCanvasRef = useRef(null);
    const isDraggingMinimap = useRef(false);
    const lastMousePos = useRef({ x: 0, y: 0 });

    const [selectedNode, setSelectedNode] = useState(null);
    const [hoveredNode, setHoveredNode] = useState(null);

    const [toggledLinks, setToggledLinks] = useState(() => new Set());
    const [hoveredLinkId, setHoveredLinkId] = useState(null);

    const graphData = useMemo(() => transformData(MOCK_DATA), []);

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

    const handleNodeClick = useCallback((node) => {
        setSelectedNode((prev) => (prev?.id === node.id ? null : node));

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
        const key = `${getLinkId(link.source)}-${getLinkId(link.target)}`;
        setToggledLinks((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    }, []);

    const handleLinkHover = useCallback((link) => {
        setHoveredLinkId(
            link ? `${getLinkId(link.source)}-${getLinkId(link.target)}` : null,
        );
    }, []);

    return (
        <div className="relative w-screen h-screen overflow-hidden">
            <ForceGraph3D
                ref={graphRef}
                graphData={graphData}
                backgroundColor="#050505"
                onNodeClick={handleNodeClick}
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
                linkWidth={(link) =>
                    getLinkWidth(link, selectedNode?.id, null, hoveredLinkId)
                }
                linkColor={(link) =>
                    getLinkColor(link, selectedNode?.id, null, hoveredLinkId)
                }
                linkOpacity={0.7}
                linkDirectionalParticles={(link) => {
                    const src = getLinkId(link.source);
                    const tgt = getLinkId(link.target);
                    return selectedNode?.id === src || selectedNode?.id === tgt
                        ? 4
                        : 0;
                }}
                linkDirectionalParticleSpeed={0.007}
                linkDirectionalParticleWidth={1.4}
                linkThreeObjectExtend={true}
                linkThreeObject={(link) => {
                    const key = `${getLinkId(link.source)}-${getLinkId(link.target)}`;
                    const isVisible =
                        hoveredLinkId === key || toggledLinks.has(key);
                    return createLinkThreeObject(link, isVisible);
                }}
                linkPositionUpdate={updateLinkPosition}
            />

            <div className="absolute bottom-25 left-6 w-[170px] h-[170px] bg-[rgba(15,15,20,0.85)] border border-white/15 rounded-xl backdrop-blur-[12px] shadow-[0_8px_32px_rgba(0,0,0,0.5)] z-10 flex flex-col items-center justify-center select-none">
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

            {selectedNode && (
                <Window
                    id="nodeInfo"
                    key={1}
                    onClose={() => setSelectedNode(null)}
                >
                    <div className="w-80 p-5 text-[#ececec] font-mono  z-10 max-h-[calc(100vh-40px)] overflow-y-auto">
                        <div className="flex justify-center items-center mb-[15px]">
                            <h3
                                className="m-0"
                                style={{ color: selectedNode.color }}
                            >
                                {selectedNode.label}
                            </h3>
                        </div>

                        <div className="text-[12px] text-[#aaa] mb-[15px] border-b border-[#333] pb-[15px]">
                            {selectedNode.description}
                        </div>

                        <div className="text-[12px]">
                            <div
                                className="mb-2 uppercase tracking-[1px]"
                                style={{ color: selectedNode.color }}
                            >
                                Attributes
                            </div>
                            {Object.entries(selectedNode.attributes || {}).map(
                                ([key, value]) => (
                                    <div
                                        key={key}
                                        className="mb-[6px] flex flex-col"
                                    >
                                        <span className="text-[#888]">
                                            {key.replace(/_/g, " ")}:
                                        </span>
                                        <span className="text-white">
                                            {Array.isArray(value)
                                                ? value.join(", ")
                                                : String(value)}
                                        </span>
                                    </div>
                                ),
                            )}
                        </div>
                    </div>
                </Window>
            )}
        </div>
    );
}
