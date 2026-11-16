"""The investigation pipeline as a LangGraph graph.

    plan -> scrape -> resolve -> discover -> evaluate -+-> END
                                    ^                  |
                                    +---- not done ----+

`plan`, `scrape` and `resolve` are deterministic and work today. `discover`
and `evaluate` are the agent loop; they are stubs until an LLM is wired in.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.nodes.discover import discover
from agents.nodes.evaluate import evaluate
from agents.nodes.plan import plan
from agents.nodes.resolve import resolve
from agents.nodes.scrape import scrape
from agents.state import InvestigationState, PipelineContext
from core.config import get_settings


def _after_evaluate(state: InvestigationState) -> str:
    if state.get("done") or state.get("iteration", 0) >= get_settings().max_agent_iterations:
        return END
    return "discover"


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(InvestigationState, context_schema=PipelineContext)

    graph.add_node("plan", plan)
    graph.add_node("scrape", scrape)
    graph.add_node("resolve", resolve)
    graph.add_node("discover", discover)
    graph.add_node("evaluate", evaluate)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "scrape")
    graph.add_edge("scrape", "resolve")
    graph.add_edge("resolve", "discover")
    graph.add_edge("discover", "evaluate")
    graph.add_conditional_edges("evaluate", _after_evaluate, ["discover", END])

    return graph.compile()
