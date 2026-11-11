import SpriteText from "three-spritetext";
import * as THREE from "three";

// TO-DO improve link aspect, still not satisfied with the sprite positon
// TO-DO remove onclick bug

const CORNER_GAP_PX = 6;
const _dir = new THREE.Vector3();
const _right = new THREE.Vector3();
const _up = new THREE.Vector3();
const _back = new THREE.Vector3();
const _toPoint = new THREE.Vector3();

export function createLinkThreeObject(link, isVisible) {
    if (!isVisible) return null;

    const sprite = new SpriteText(link.label ? link.label.toUpperCase() : "");
    sprite.color = "#ffffff";
    sprite.textHeight = 2.4;
    sprite.backgroundColor = "rgba(18, 18, 24, 0.9)";
    sprite.padding = [3, 2];
    sprite.borderRadius = 2;
    sprite.borderColor = link.confidence < 0.5 ? "#666" : "#999";
    sprite.borderWidth = 0.5;
    return sprite;
}

export function updateLinkPosition(sprite, { start, end }, link, graphRef) {
    if (!sprite || !start || !end) return true;

    const t = link.__t ?? 0.5;
    sprite.position.set(
        start.x + (end.x - start.x) * t,
        start.y + (end.y - start.y) * t,
        start.z + (end.z - start.z) * t,
    );

    const fg = graphRef?.current;
    const camera = fg?.camera();
    if (!camera) return true;

    camera.matrixWorld.extractBasis(_right, _up, _back);

    _dir.set(end.x - start.x, end.y - start.y, end.z - start.z);
    const sx = _dir.dot(_right);
    const sy = _dir.dot(_up);

    const boxOnLeft = sx * sy >= 0;

    sprite.center.set(boxOnLeft ? 1 : 0, 0);

    const canvasH = fg.renderer().domElement.clientHeight || 1;
    const depth = Math.max(
        -_toPoint.subVectors(sprite.position, camera.position).dot(_back),
        0.001,
    );
    const worldPerPx =
        (2 * depth * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) /
        canvasH;
    const gap = CORNER_GAP_PX * worldPerPx;

    sprite.position
        .addScaledVector(_right, (boxOnLeft ? -1 : 1) * gap)
        .addScaledVector(_up, gap);

    return true;
}

export function getLinkId(nodeRef) {
    return typeof nodeRef === "object" && nodeRef !== null
        ? nodeRef.id
        : nodeRef;
}

export function getLinkColor(
    link,
    selectedNodeId,
    selectedLinkKey,
    hoveredLinkId,
) {
    const src = getLinkId(link.source);
    const tgt = getLinkId(link.target);
    const linkKey = `${src}-${tgt}`;

    const isSelectedNodeNeighbor =
        selectedNodeId && (src === selectedNodeId || tgt === selectedNodeId);
    const isDirectlySelected =
        selectedLinkKey === linkKey || hoveredLinkId === linkKey;

    if (isDirectlySelected) return "#00f5d4";
    if (isSelectedNodeNeighbor) return "#ffd166";
    return link.confidence < 0.5 ? "#444444" : "#777777";
}

export function getLinkWidth(
    link,
    selectedNodeId,
    selectedLinkKey,
    hoveredLinkId,
) {
    const src = getLinkId(link.source);
    const tgt = getLinkId(link.target);
    const linkKey = `${src}-${tgt}`;

    if (selectedLinkKey === linkKey || hoveredLinkId === linkKey) return 50;
    if (selectedNodeId && (src === selectedNodeId || tgt === selectedNodeId))
        return 1.8;
    return 0.6;
}
