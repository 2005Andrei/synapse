import { ENTITY_COLORS, LINK_COLORS } from "../config";

const NODE_BASE_SIZE = 4;
const NODE_MAX_SIZE = 11;

// radius of a node with `degree` links. logarithmic, so a hub is visibly a
// hub without swallowing its neighbours: 1 link -> 5.5, 10 -> 9.2, and
// anything past ~25 links stops growing at 11
export function nodeSize(degree) {
    return Math.min(
        NODE_MAX_SIZE,
        NODE_BASE_SIZE + 1.5 * Math.log2(1 + degree),
    );
}

// this function should not add much overhead, O(N + L), N, L = nodes, links is the complexity which should be fine
// what is challenging is the physics engine
export function transformData(data) {
    if (!data?.entities) return { nodes: [], links: [] };

    const nodes = data.entities.map((e) => ({
        id: e.id,
        type: e.type,
        label: e.aliases?.length ? e.aliases[0] : `Unnamed ${e.type}`,
        description: e.description,
        attributes: e.attributes,
        color: ENTITY_COLORS[e.type] || ENTITY_COLORS.Default,
        val: NODE_BASE_SIZE, // size; grows with the number of links, see below
    }));

    const validNodeIds = new Set(nodes.map((n) => n.id));
    console.log("at init mode");
    console.log(validNodeIds);

    const links = [];
    (data.claims || []).forEach((claim) => {
        const subjects = Array.isArray(claim.subject_ids)
            ? claim.subject_ids
            : [claim.subject_ids].filter(Boolean);
        const targets = Array.isArray(claim.reference_ids)
            ? claim.reference_ids
            : [];
        const label = claim.predicate ? claim.predicate.replace(/_/g, " ") : "";

        if (subjects.length > 0 && targets.length > 0) {
            subjects.forEach((src) => {
                targets.forEach((tgt) => {
                    if (validNodeIds.has(src) && validNodeIds.has(tgt)) {
                        links.push({
                            id: `${claim.id}:${src}->${tgt}`,
                            source: src,
                            target: tgt,
                            label,
                            confidence: claim.confidence ?? 1.0,
                            color: LINK_COLORS.Default,
                            text: claim.claim_text,
                            status: claim.claim_status,
                            sourceIds: claim.source_ids ?? [],
                            quote: claim.quote ?? undefined,
                        });
                    }
                });
            });
        } else if (subjects.length === 2 && targets.length === 0) {
            if (
                validNodeIds.has(subjects[0]) &&
                validNodeIds.has(subjects[1])
            ) {
                links.push({
                    id: `${claim.id}:${subjects[0]}->${subjects[1]}`,
                    source: subjects[0],
                    target: subjects[1],
                    label,
                    confidence: claim.confidence ?? 1.0,
                    color: LINK_COLORS.Default,
                    text: claim.claim_text,
                    status: claim.claim_status,
                    sourceIds: claim.source_ids ?? [],
                            quote: claim.quote ?? undefined,
                });
            }
        }
    });

    const degreeMap = new Map();
    links.forEach((l) => {
        degreeMap.set(l.source, (degreeMap.get(l.source) || 0) + 1);
        degreeMap.set(l.target, (degreeMap.get(l.target) || 0) + 1);
    });

    nodes.forEach((n) => {
        n.val = nodeSize(degreeMap.get(n.id) || 0);
    });

    return { nodes, links };
}

export function reconcileGraph(prev, next) {
    const known = new Map(prev.nodes.map((n) => [n.id, n]));
    const nodes = next.nodes.map((n) => {
        const existing = known.get(n.id);
        return existing ? Object.assign(existing, n) : n;
    });
    return { nodes, links: next.links };
}
