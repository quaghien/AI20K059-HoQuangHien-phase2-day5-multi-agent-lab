"""LangGraph workflow implementation."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from multi_agent_research_lab.agents import AnalystAgent, CriticAgent, ResearcherAgent, SupervisorAgent, WriterAgent
from multi_agent_research_lab.core.state import ResearchState


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph."""

    def __init__(
        self,
        *,
        supervisor: SupervisorAgent | None = None,
        researcher: ResearcherAgent | None = None,
        analyst: AnalystAgent | None = None,
        critic: CriticAgent | None = None,
        writer: WriterAgent | None = None,
    ) -> None:
        self.supervisor = supervisor or SupervisorAgent()
        self.researcher = researcher or ResearcherAgent()
        self.analyst = analyst or AnalystAgent()
        self.critic = critic or CriticAgent()
        self.writer = writer or WriterAgent()

    def build(self) -> Any:
        """Create a LangGraph graph with conditional routing from supervisor."""

        graph = StateGraph(ResearchState)
        graph.add_node("supervisor", self.supervisor.run)
        graph.add_node("researcher", self.researcher.run)
        graph.add_node("analyst", self.analyst.run)
        graph.add_node("critic", self.critic.run)
        graph.add_node("writer", self.writer.run)

        graph.add_edge(START, "supervisor")
        graph.add_conditional_edges(
            "supervisor",
            self._route_from_state,
            {
                "researcher": "researcher",
                "analyst": "analyst",
                "critic": "critic",
                "writer": "writer",
                "done": END,
            },
        )
        graph.add_edge("researcher", "supervisor")
        graph.add_edge("analyst", "supervisor")
        graph.add_edge("critic", "supervisor")
        graph.add_edge("writer", "supervisor")
        return graph.compile()

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the graph and return final state."""

        compiled = self.build()
        result = compiled.invoke(state)
        if isinstance(result, ResearchState):
            return result
        if isinstance(result, dict):
            return ResearchState.model_validate(result)
        raise TypeError(f"Unexpected workflow result type: {type(result)!r}")

    def _route_from_state(self, state: ResearchState) -> str:
        route = state.next_agent or "done"
        return route if route in {"researcher", "analyst", "critic", "writer", "done"} else "done"
