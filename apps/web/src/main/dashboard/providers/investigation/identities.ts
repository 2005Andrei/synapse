import type { RunState } from "./store";

export type Identity = {
    id: string;
    kind: "subject" | "similar" | "other";
    name: string;
    note: string;
    entityIds: string[];
    joined: { id: string; name: string }[];
};

export type Division = {
    identities: Identity[];
    groupOf: Record<string, string>;
};

export const SUBJECT = "subject";
export const OTHER = "other";

// links that say "the names look alike". They relate identities to each
// other, so following them would glue the identities back together.
export const NAME_LINKS = new Set(["Same_Name", "Similar_Name"]);

// anchor -> who it represents -> their documents -> the other parties there.
// Identities grow level by level, so a record always goes to the nearest one.
const MAX_DEPTH = 3;

const nameOf = (run: RunState, id: string) =>
    run.entities[id]?.aliases?.[0] ?? "?";

export function divide(run: RunState): Division {
    const neighbours = new Map<string, string[]>();
    for (const claim of Object.values(run.claims)) {
        if (NAME_LINKS.has(claim.predicate)) continue;
        const ids = [...claim.subject_ids, ...claim.reference_ids];
        for (const a of ids)
            for (const b of ids)
                if (a !== b)
                    neighbours.set(a, [...(neighbours.get(a) ?? []), b]);
    }

    const groupOf: Record<string, string> = {};
    const identities: Identity[] = [];
    let frontier: string[] = [];

    const anchor = (identity: Identity, ids: string[]) => {
        identities.push(identity);
        for (const id of ids) {
            if (!run.entities[id] || groupOf[id]) continue;
            groupOf[id] = identity.id;
            frontier.push(id);
        }
    };

    const flagged = Object.values(run.entities).filter(
        (e) => e.attributes.match,
    );
    // A similar name stays its own identity unless the user said it is the
    // same person (`run.joined`); only then do its records count as the subject's.
    const isSubject = (e: (typeof flagged)[number]) =>
        e.attributes.match === "exact" || run.joined.includes(e.id);
    anchor(
        {
            id: SUBJECT,
            kind: "subject",
            name: run.seedId ? nameOf(run, run.seedId) : run.query,
            note: "",
            entityIds: [],
            joined: flagged
                .filter((e) => run.joined.includes(e.id))
                .map((e) => ({ id: e.id, name: nameOf(run, e.id) })),
        },
        [run.seedId ?? "", ...flagged.filter(isSubject).map((e) => e.id)],
    );
    for (const entity of flagged.filter((e) => !isSubject(e)))
        anchor(
            {
                id: entity.id,
                kind: "similar",
                name: nameOf(run, entity.id),
                note: String(entity.attributes.match_note ?? ""),
                entityIds: [],
                joined: [],
            },
            [entity.id],
        );

    // Grow all identities one step at a time, the subject first, so a record
    // goes to the identity it is closest to.
    for (let depth = 0; depth < MAX_DEPTH; depth++) {
        const next: string[] = [];
        for (const id of frontier)
            for (const other of neighbours.get(id) ?? []) {
                if (groupOf[other] || !run.entities[other]) continue;
                groupOf[other] = groupOf[id];
                next.push(other);
            }
        frontier = next;
    }

    const other: Identity = {
        id: OTHER,
        kind: "other",
        name: "Other results",
        note: "",
        entityIds: [],
        joined: [],
    };
    const byId = new Map(
        [...identities, other].map((identity) => [identity.id, identity]),
    );
    for (const id of Object.keys(run.entities)) {
        groupOf[id] ??= OTHER;
        byId.get(groupOf[id])!.entityIds.push(id);
    }

    const [subject, ...similar] = identities;
    similar.sort(
        (a, b) =>
            b.entityIds.length - a.entityIds.length ||
            a.name.localeCompare(b.name),
    );
    return {
        identities: [
            subject,
            ...similar,
            ...(other.entityIds.length ? [other] : []),
        ],
        groupOf,
    };
}

export const identityLabel = (identity: Identity) =>
    identity.kind === "subject"
        ? "Matches the search"
        : identity.kind === "similar"
          ? "Similar name"
          : "Not tied to a match";
