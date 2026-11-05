// windows/WindowLayer.tsx
import { useShallow } from "zustand/react/shallow";
import { useWM } from "../utils/store";
import { Window } from "../utils/Window";
import { registry } from "./registry";

function WindowHost({ id }: { id: string }) {
    const kind = useWM((s) => s.wins[id].kind);
    const props = useWM((s) => s.wins[id].props);
    const Body = registry[kind];
    if (!Body) return null;
    return (
        <Window id={id}>
            <Body {...props} />
        </Window>
    );
}

export function WindowLayer() {
    // useShallow stops the new-array-every-time infinite loop in zustand v5
    const ids = useWM(useShallow((s) => Object.keys(s.wins)));
    return ids.map((id) => <WindowHost key={id} id={id} />);
}
