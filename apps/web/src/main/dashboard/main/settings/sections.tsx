import { useWM } from "../../utils/store";
import { Group, Row, Segmented, Slider, Switch } from "./controls";
import { useSettings } from "./store";

const plural = (n: number, one: string, many = `${one}s`) =>
    `${n} ${n === 1 ? one : many}`;

export function InvestigationSettings() {
    const s = useSettings((st) => st.investigation);
    const set = useSettings((st) => st.set);
    const patch = (p: Partial<typeof s>) => set("investigation", p);

    return (
        <>
            <Group
                title="Recursion"
                hint="How far a search keeps going after the first results."
            >
                <Row
                    stacked
                    label="Recursion depth"
                    hint="Rounds the agent runs: each round reads new sources and searches the entities it found in the previous one."
                >
                    <Slider
                        label="Recursion depth"
                        value={s.depth}
                        onChange={(depth) => patch({ depth })}
                        min={1}
                        max={6}
                        format={(v) => plural(v, "round")}
                        marks={["Shallow", "Deep"]}
                    />
                </Row>
                <Row
                    stacked
                    label="Leads per round"
                    hint="Follow-up searches proposed after each round."
                >
                    <Slider
                        label="Leads per round"
                        value={s.leadsPerRound}
                        onChange={(leadsPerRound) => patch({ leadsPerRound })}
                        min={1}
                        max={12}
                    />
                </Row>
                <Row
                    label="Follow leads automatically"
                    hint="Start the proposed follow-ups without asking first."
                >
                    <Switch
                        label="Follow leads automatically"
                        checked={s.autoFollow}
                        onChange={(autoFollow) => patch({ autoFollow })}
                    />
                </Row>
                <Row
                    label="Follow ownership chains"
                    hint="Keep going up through shareholders and administrators, even past the depth limit."
                >
                    <Switch
                        label="Follow ownership chains"
                        checked={s.ownershipChains}
                        onChange={(ownershipChains) =>
                            patch({ ownershipChains })
                        }
                    />
                </Row>
                <Row
                    label="Stop early when nothing new turns up"
                    hint="End the search when a round adds no new entities."
                >
                    <Switch
                        label="Stop early when nothing new turns up"
                        checked={s.stopWhenStale}
                        onChange={(stopWhenStale) => patch({ stopWhenStale })}
                    />
                </Row>
            </Group>

            <Group title="Budget" hint="Limits on time and model cost per search.">
                <Row
                    stacked
                    label="Sources read per round"
                    hint="Documents sent to the model each round. More means more detail and a higher cost."
                >
                    <Slider
                        label="Sources read per round"
                        value={s.sourcesPerRound}
                        onChange={(sourcesPerRound) =>
                            patch({ sourcesPerRound })
                        }
                        min={1}
                        max={20}
                        marks={["Cheaper", "Thorough"]}
                    />
                </Row>
                <Row label="Time limit" hint="A search is stopped after this long.">
                    <Segmented
                        label="Time limit"
                        value={s.timeoutMinutes}
                        onChange={(timeoutMinutes) => patch({ timeoutMinutes })}
                        options={[5, 15, 30, 60].map((m) => ({
                            value: m,
                            label: `${m} min`,
                        }))}
                    />
                </Row>
            </Group>
        </>
    );
}

const SOURCE_GROUPS = [
    {
        title: "Registries",
        hint: "Official records: companies, finances, court cases, contracts.",
        items: [
            ["onrc", "ONRC", "Trade register: companies, shareholders, administrators"],
            ["anaf", "ANAF", "Tax status and yearly financial statements"],
            ["portal_just", "Portal Just", "Court cases and their parties"],
            ["ani", "ANI", "Asset and interest declarations"],
            ["seap", "SEAP", "Public procurement contracts"],
        ],
    },
    {
        title: "Investigative journalism",
        items: [
            ["riseproject", "RISE Project", "Investigations into organized crime and corruption"],
            ["recorder", "Recorder", "Video and long-form investigations"],
            ["zf", "Ziarul Financiar", "Business and financial news"],
        ],
    },
    {
        title: "News",
        items: [
            ["adevarul", "Adevărul", ""],
            ["digi24", "Digi24", ""],
            ["g4media", "G4Media", ""],
            ["hotnews", "HotNews", ""],
        ],
    },
] as const;

export function SourcesSettings() {
    const s = useSettings((st) => st.sources);
    const set = useSettings((st) => st.set);
    const toggle = (id: string, on: boolean) =>
        set("sources", { enabled: { ...s.enabled, [id]: on } });

    return (
        <>
            {SOURCE_GROUPS.map((g) => {
                const ids = g.items.map(([id]) => id);
                const allOn = ids.every((id) => s.enabled[id]);
                return (
                    <Group
                        key={g.title}
                        title={g.title}
                        hint={"hint" in g ? g.hint : undefined}
                        action={
                            <button
                                type="button"
                                onClick={() =>
                                    set("sources", {
                                        enabled: {
                                            ...s.enabled,
                                            ...Object.fromEntries(
                                                ids.map((id) => [id, !allOn]),
                                            ),
                                        },
                                    })
                                }
                                className="cursor-pointer text-xs text-foreground/45 hover:text-foreground"
                            >
                                {allOn ? "Turn all off" : "Turn all on"}
                            </button>
                        }
                    >
                        {g.items.map(([id, label, hint]) => (
                            <Row key={id} label={label} hint={hint || undefined}>
                                <Switch
                                    label={label}
                                    checked={s.enabled[id] ?? true}
                                    onChange={(on) => toggle(id, on)}
                                />
                            </Row>
                        ))}
                    </Group>
                );
            })}

            <Group title="Requests">
                <Row
                    stacked
                    label="Parallel requests"
                    hint="Sources fetched at the same time. Lower it if a site starts refusing requests."
                >
                    <Slider
                        label="Parallel requests"
                        value={s.concurrency}
                        onChange={(concurrency) => set("sources", { concurrency })}
                        min={1}
                        max={12}
                    />
                </Row>
                <Row label="Request timeout" hint="Give up on a slow source after this long.">
                    <Segmented
                        label="Request timeout"
                        value={s.timeoutSeconds}
                        onChange={(timeoutSeconds) =>
                            set("sources", { timeoutSeconds })
                        }
                        options={[30, 60, 90, 120].map((v) => ({
                            value: v,
                            label: `${v}s`,
                        }))}
                    />
                </Row>
            </Group>
        </>
    );
}

export function GraphSettings() {
    const s = useSettings((st) => st.graph);
    const set = useSettings((st) => st.set);
    const patch = (p: Partial<typeof s>) => set("graph", p);

    return (
        <>
            <Group title="Layout">
                <Row label="Arrangement" hint="How nodes are placed on the canvas.">
                    <Segmented
                        label="Arrangement"
                        value={s.layout}
                        onChange={(layout) => patch({ layout })}
                        options={[
                            { value: "force", label: "Force" },
                            { value: "radial", label: "Radial" },
                            { value: "tree", label: "Tree" },
                        ]}
                    />
                </Row>
                <Row label="Live physics" hint="Nodes keep settling while you drag them.">
                    <Switch
                        label="Live physics"
                        checked={s.physics}
                        onChange={(physics) => patch({ physics })}
                    />
                </Row>
                <Row label="Group by type" hint="Pull companies, people and institutions into clusters.">
                    <Switch
                        label="Group by type"
                        checked={s.clusterByType}
                        onChange={(clusterByType) => patch({ clusterByType })}
                    />
                </Row>
            </Group>
            <Group title="Display">
                <Row label="Node size" hint="What makes a node bigger.">
                    <Segmented
                        label="Node size"
                        value={s.nodeSize}
                        onChange={(nodeSize) => patch({ nodeSize })}
                        options={[
                            { value: "uniform", label: "Same" },
                            { value: "connections", label: "Connections" },
                            { value: "revenue", label: "Revenue" },
                        ]}
                    />
                </Row>
                <Row label="Link labels" hint="Show the relationship on each link, such as shareholder or administrator.">
                    <Switch
                        label="Link labels"
                        checked={s.edgeLabels}
                        onChange={(edgeLabels) => patch({ edgeLabels })}
                    />
                </Row>
            </Group>
        </>
    );
}

export function WorkspaceSettings() {
    const s = useSettings((st) => st.workspace);
    const set = useSettings((st) => st.set);
    const patch = (p: Partial<typeof s>) => set("workspace", p);
    const snap = useWM((st) => st.snapEnabled);
    const toggleSnap = useWM((st) => st.toggleSnap);

    return (
        <>
            <Group title="Windows">
                <Row
                    label="Snap windows"
                    hint="Drag a window to an edge or corner to snap it there."
                >
                    <Switch label="Snap windows" checked={snap} onChange={toggleSnap} />
                </Row>
                <Row label="Open the investigation window on start">
                    <Switch
                        label="Open the investigation window on start"
                        checked={s.openInvestigationOnStart}
                        onChange={(openInvestigationOnStart) =>
                            patch({ openInvestigationOnStart })
                        }
                    />
                </Row>
                <Row label="Reduce motion" hint="Fewer animations in windows and the graph.">
                    <Switch
                        label="Reduce motion"
                        checked={s.reducedMotion}
                        onChange={(reducedMotion) => patch({ reducedMotion })}
                    />
                </Row>
            </Group>
            <Group title="Notifications">
                <Row label="Notify when a search finishes">
                    <Switch
                        label="Notify when a search finishes"
                        checked={s.notifyOnFinish}
                        onChange={(notifyOnFinish) => patch({ notifyOnFinish })}
                    />
                </Row>
                <Row label="Play a sound">
                    <Switch
                        label="Play a sound"
                        checked={s.sound}
                        onChange={(sound) => patch({ sound })}
                    />
                </Row>
            </Group>
        </>
    );
}

export function DataSettings() {
    const s = useSettings((st) => st.data);
    const set = useSettings((st) => st.set);
    const patch = (p: Partial<typeof s>) => set("data", p);

    return (
        <>
            <Group title="Storage">
                <Row
                    label="Keep fetched sources for"
                    hint="Searches within this window reuse the copy instead of fetching it again."
                >
                    <Segmented
                        label="Keep fetched sources for"
                        value={s.cacheDays}
                        onChange={(cacheDays) => patch({ cacheDays })}
                        options={[
                            { value: 1, label: "1 day" },
                            { value: 7, label: "7 days" },
                            { value: 30, label: "30 days" },
                            { value: 0, label: "Off" },
                        ]}
                    />
                </Row>
                <Row label="Keep search history" hint="List past searches in the sidebar.">
                    <Switch
                        label="Keep search history"
                        checked={s.keepHistory}
                        onChange={(keepHistory) => patch({ keepHistory })}
                    />
                </Row>
            </Group>
            <Group title="Danger zone">
                <Row
                    label="Clear cached sources"
                    hint="Every source is fetched fresh on the next search."
                >
                    <button
                        type="button"
                        disabled
                        title="Not available yet"
                        className="cursor-not-allowed rounded-md border border-red-400/20 px-3 py-1.5 text-xs font-medium text-red-300/50"
                    >
                        Clear cache
                    </button>
                </Row>
            </Group>
        </>
    );
}
