from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow


class _StateMutatingAgent(BaseAgent):
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, state: ResearchState) -> ResearchState:
        if self.name == "researcher":
            state.sources = [SourceDocument(title="Doc", snippet="Snippet")]
            state.research_notes = "research notes"
        elif self.name == "analyst":
            state.analysis_notes = "analysis notes"
        elif self.name == "critic":
            state.critic_notes = "critic notes"
        elif self.name == "writer":
            state.final_answer = "final answer"
        return state


def test_supervisor_routes_to_researcher_when_context_missing() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    agent = SupervisorAgent(settings=Settings(MAX_ITERATIONS=6))

    result = agent.run(state)

    assert result.next_agent == "researcher"
    assert result.route_history[-1] == "researcher"
    assert result.status == "routing_to_researcher"


def test_supervisor_routes_to_analyst_when_research_is_ready() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        sources=[SourceDocument(title="Doc", snippet="Snippet")],
        research_notes="research notes",
    )
    agent = SupervisorAgent(settings=Settings(MAX_ITERATIONS=6))

    result = agent.run(state)

    assert result.next_agent == "analyst"


def test_supervisor_stops_when_max_iterations_reached() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        iteration=6,
    )
    agent = SupervisorAgent(settings=Settings(MAX_ITERATIONS=6))

    result = agent.run(state)

    assert result.next_agent == "done"
    assert result.route_history[-1] == "done"
    assert "supervisor:max_iterations_reached" in result.errors


def test_supervisor_routes_back_to_researcher_for_verification() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        sources=[SourceDocument(title="Doc", snippet="Snippet")],
        research_notes="research notes",
        analysis_notes="analysis notes",
        critic_notes="VERIFY: verify multi-agent latency overhead",
        verification_queries=["verify multi-agent latency overhead"],
    )
    agent = SupervisorAgent(settings=Settings(MAX_ITERATIONS=6))

    result = agent.run(state)

    assert result.next_agent == "researcher"
    assert result.route_history[-1] == "researcher"


def test_workflow_runs_end_to_end_with_stubbed_agents() -> None:
    supervisor = SupervisorAgent(settings=Settings(MAX_ITERATIONS=10))
    workflow = MultiAgentWorkflow(
        supervisor=supervisor,
        researcher=_StateMutatingAgent("researcher"),  # type: ignore[arg-type]
        analyst=_StateMutatingAgent("analyst"),  # type: ignore[arg-type]
        critic=_StateMutatingAgent("critic"),  # type: ignore[arg-type]
        writer=_StateMutatingAgent("writer"),  # type: ignore[arg-type]
    )
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))

    result = workflow.run(state)

    assert result.research_notes == "research notes"
    assert result.analysis_notes == "analysis notes"
    assert result.critic_notes == "critic notes"
    assert result.final_answer == "final answer"
    assert result.route_history == ["researcher", "analyst", "critic", "writer", "done"]
