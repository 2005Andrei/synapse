import SpriteText from "three-spritetext";

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

export function updateLinkPosition(sprite, { start, end }) {
    if (!sprite || !start || !end) return;
    sprite.position.set(
        start.x + (end.x - start.x) / 2,
        start.y + (end.y - start.y) / 2,
        start.z + (end.z - start.z) / 2,
    );
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

    if (selectedLinkKey === linkKey || hoveredLinkId === linkKey) return 2.2;
    if (selectedNodeId && (src === selectedNodeId || tgt === selectedNodeId))
        return 1.8;
    return 0.6;
}
