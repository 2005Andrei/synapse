import type { ComponentType } from "react";
import DataContainer from "../main/sidebars/DataContainer";
import NodeInfo from "../main/graph/cards/NodeInfo";

export const registry: Record<string, ComponentType<any>> = {
    data: DataContainer,
    nodeInfo: NodeInfo,
};
