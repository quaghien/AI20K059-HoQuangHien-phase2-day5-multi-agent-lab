"""Supervisor / router implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span


class SupervisorAgent(BaseAgent):
    """Deterministic router that decides which worker should run next."""

    name = "supervisor"

    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(self, state: ResearchState) -> ResearchState:
        """Update state with the next route and enforce guardrails."""

        with trace_span(
            "agent.supervisor",
            {"agent": self.name, "iteration": state.iteration},
            input_payload={
                "status": state.status,
                "verification_queries": state.verification_queries,
                "has_sources": bool(state.sources),
                "has_research_notes": state.research_notes is not None,
                "has_analysis_notes": state.analysis_notes is not None,
                "has_critic_notes": state.critic_notes is not None,
                "has_final_answer": state.final_answer is not None,
                "errors": state.errors,
            },
        ) as span:
            if state.iteration >= self.settings.max_iterations:
                route = "done"
                state.errors.append("supervisor:max_iterations_reached")
            else:
                route = self._determine_route(state)

            state.record_route(route)
            state.next_agent = route
            state.status = "completed" if route == "done" else f"routing_to_{route}"
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.SUPERVISOR,
                    content=route,
                    metadata={"iteration": state.iteration, "routing_mode": "deterministic"},
                )
            )
            state.add_trace_event("supervisor.routed", {"next_agent": route, "status": state.status})
            span["output"] = {"route": route, "status": state.status}
            return state

    def _determine_route(self, state: ResearchState) -> str:
        if state.verification_queries:
            return "researcher"
        if not state.sources or not state.research_notes or self._has_stage_error(state, "researcher"):
            return "researcher"
        if not state.analysis_notes or self._has_stage_error(state, "analyst"):
            return "analyst"
        if not state.critic_notes or self._has_stage_error(state, "critic"):
            return "critic"
        if not state.final_answer or self._has_stage_error(state, "writer"):
            return "writer"
        return "done"

    def _has_stage_error(self, state: ResearchState, stage: str) -> bool:
        prefix = f"{stage}:"
        return any(error.startswith(prefix) for error in state.errors)
