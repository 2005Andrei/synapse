import { ENTITY_COLORS, LINK_COLORS } from "../config";

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
        val: 4, // size
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
        n.val += degreeMap.get(n.id) || 0;
    });

    return { nodes, links };
}
