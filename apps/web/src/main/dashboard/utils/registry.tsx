import type { ComponentType } from "react";
import DataContainer from "../main/sidebars/DataContainer";
import NodeInfo from "../main/graph/cards/NodeInfo";
import LinkInfo from "../main/graph/cards/LinkInfo";

export const registry: Record<string, ComponentType<any>> = {
    data: DataContainer,
    nodeInfo: NodeInfo,
    linkInfo: LinkInfo,
};
