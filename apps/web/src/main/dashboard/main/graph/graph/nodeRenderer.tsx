import * as THREE from "three";
import SpriteText from "three-spritetext";
export function createNodeObject(node, isSelected, isHovered) {
    const group = new THREE.Group();
    const nodeRadius = Math.max(3, node.val);

    const geometry = new THREE.SphereGeometry(nodeRadius, 24, 24);
    const material = new THREE.MeshBasicMaterial({
        color: node.color,
        transparent: true,
        opacity: isSelected ? 1.0 : isHovered ? 0.95 : 0.8,
    });
    const sphere = new THREE.Mesh(geometry, material);
    group.add(sphere);

    if (node.val > 6 || isSelected) {
        const ringGeo = new THREE.TorusGeometry(nodeRadius + 2, 0.25, 16, 64);
        const ringMat = new THREE.MeshBasicMaterial({
            color: node.color,
            transparent: true,
            opacity: isSelected ? 0.9 : 0.5,
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        group.add(ring);
    }

    if (isHovered || isSelected) {
        const labelSprite = new SpriteText(node.label);
        labelSprite.color = "#ffffff";
        labelSprite.textHeight = 3.5;
        labelSprite.backgroundColor = "rgba(10, 10, 15, 0.85)";
        labelSprite.padding = [3, 2];
        labelSprite.borderRadius = 3;
        labelSprite.borderColor = node.color;
        labelSprite.borderWidth = 0.5;
        labelSprite.position.set(0, -(nodeRadius + 5), 0);
        group.add(labelSprite);
    }

    return group;
}
