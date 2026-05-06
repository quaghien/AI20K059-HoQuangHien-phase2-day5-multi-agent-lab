from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState


def test_state_records_route_and_trace() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    state.record_route("researcher")
    state.add_trace_event("route", {"next": "researcher"})
    assert state.iteration == 1
    assert state.route_history == ["researcher"]
    assert state.trace[0]["name"] == "route"


def test_state_defaults_support_reasoning_handoff() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    assert state.critic_notes is None
    assert state.next_agent is None
    assert state.status == "pending"
    assert state.judge_score is None
