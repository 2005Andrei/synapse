import type { ComponentType } from "react";
import NodeInfo from "../main/graph/cards/NodeInfo";
import LinkInfo from "../main/graph/cards/LinkInfo";
import InvestigationPanel from "../main/investigation/InvestigationPanel";

export const registry: Record<string, ComponentType<any>> = {
    nodeInfo: NodeInfo,
    linkInfo: LinkInfo,
    investigation: InvestigationPanel,
};
