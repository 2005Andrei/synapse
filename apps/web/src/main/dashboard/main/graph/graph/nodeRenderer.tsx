import * as THREE from "three";
import SpriteText from "three-spritetext";

const SPHERE_GEO = new THREE.SphereGeometry(1, 32, 32);
const noRaycast = () => {};

const HALO_SPREAD = 0.7;
const RING_GAP = 1.5;

const textureCache = {};
const materialCache = {};
const labelCache = new Map();

const STYLE = {
    idle: { glow: 0.22, ring: 0, emissive: 0x000000 },
    hover: { glow: 0.38, ring: 0.5, emissive: 0x222222 },
    selected: { glow: 0.5, ring: 0.95, emissive: 0x444444 },
};

function getTexture(type) {
    if (textureCache[type]) return textureCache[type];

    const size = 256;
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const ctx = c.getContext("2d");

    if (type === "halo") {
        const r0 = 1 / (1 + HALO_SPREAD);
        const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
        g.addColorStop(0, "rgba(255,255,255,1)");
        g.addColorStop(r0, "rgba(255,255,255,1)");
        g.addColorStop(r0 + (1 - r0) * 0.25, "rgba(255,255,255,0.45)");
        g.addColorStop(r0 + (1 - r0) * 0.55, "rgba(255,255,255,0.14)");
        g.addColorStop(1, "rgba(255,255,255,0)");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, size, size);
    } else if (type === "ring") {
        ctx.lineWidth = size * 0.02;
        ctx.strokeStyle = "#fff";
        ctx.beginPath();
        ctx.arc(128, 128, 128 - ctx.lineWidth, 0, Math.PI * 2);
        ctx.stroke();
    }

    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return (textureCache[type] = tex);
}

function getMaterial(type, color, opacity = 1) {
    const key = `${type}_${color}_${opacity}`;
    if (materialCache[key]) return materialCache[key];

    let mat;
    if (type === "orb") {
        mat = new THREE.MeshPhongMaterial({
            color,
            shininess: 30,
            specular: 0x222222,
        });
    } else {
        mat = new THREE.SpriteMaterial({
            map: getTexture(type),
            color,
            transparent: true,
            opacity,
            depthWrite: false,
            blending:
                type === "halo" ? THREE.AdditiveBlending : THREE.NormalBlending,
        });
    }

    return (materialCache[key] = mat);
}

function getLabel(node) {
    if (!labelCache.has(node.id)) {
        const s = new SpriteText(node.label);
        s.color = "#ffffff";
        s.fontFace = "Inter, system-ui, sans-serif";
        s.fontWeight = "600";
        s.textHeight = 3.5;
        s.backgroundColor = "rgba(10, 10, 15, 0.85)";
        s.padding = [3, 2];
        s.borderRadius = 3;
        s.borderColor = node.color;
        s.borderWidth = 0.5;
        s.material.depthTest = false;
        s.renderOrder = 10;
        s.raycast = noRaycast;
        labelCache.set(node.id, s);
    }
    return labelCache.get(node.id);
}

export function createNodeObject(node, isSelected, isHovered) {
    const state = isSelected ? "selected" : isHovered ? "hover" : "idle";
    const st = STYLE[state];

    const group = new THREE.Group();
    const radius = Math.max(3, node.val);

    const halo = new THREE.Sprite(getMaterial("halo", node.color, st.glow));
    halo.scale.setScalar(radius * 2 * (1 + HALO_SPREAD));
    halo.raycast = noRaycast;
    group.add(halo);

    const orbMat = getMaterial("orb", node.color).clone();
    orbMat.emissive.setHex(st.emissive);
    const orb = new THREE.Mesh(SPHERE_GEO, orbMat);
    orb.scale.setScalar(radius);
    group.add(orb);

    if (st.ring > 0) {
        const ring = new THREE.Sprite(getMaterial("ring", node.color, st.ring));
        ring.scale.setScalar((radius + RING_GAP) * 2);
        ring.raycast = noRaycast;
        group.add(ring);
    }

    if (isHovered || isSelected) {
        const label = getLabel(node);
        label.position.set(0, -(radius + RING_GAP + 4), 0);
        group.add(label);
    }

    return group;
}
