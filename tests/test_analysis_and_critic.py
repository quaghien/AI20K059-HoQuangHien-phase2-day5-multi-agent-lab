import pytest

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMResponse


class _SequencedLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        del system_prompt
        del user_prompt
        return LLMResponse(content=self._responses.pop(0), input_tokens=120, output_tokens=60, cost_usd=0.0025)


def test_analyst_creates_analysis_notes() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        research_notes="Research notes:\n- Agents can specialize.\n- Parallel work improves coverage.",
    )
    agent = AnalystAgent(llm_client=_SequencedLLMClient(["Analysis notes output"]))

    result = agent.run(state)

    assert result.analysis_notes == "Analysis notes output"
    assert result.critic_notes is None
    assert result.next_agent == "critic"
    assert result.status == "analysis_ready"
    assert result.agent_results[-1].agent.value == "analyst"
    assert result.agent_results[-1].metadata["cost_usd"] == 0.0025
    assert result.trace[-1]["name"] == "analyst.completed"


def test_critic_creates_critic_notes_without_overwriting_analysis() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        research_notes="Research notes",
        analysis_notes="Analysis notes output",
    )
    agent = CriticAgent(llm_client=_SequencedLLMClient(["Critic notes output"]))

    result = agent.run(state)

    assert result.analysis_notes == "Analysis notes output"
    assert result.critic_notes == "Critic notes output"
    assert result.next_agent == "writer"
    assert result.status == "critique_ready"
    assert result.agent_results[-1].agent.value == "critic"
    assert result.agent_results[-1].metadata["cost_usd"] == 0.0025
    assert result.trace[-1]["name"] == "critic.completed"


def test_analyst_requires_research_notes() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    agent = AnalystAgent(llm_client=_SequencedLLMClient(["unused"]))

    with pytest.raises(ValidationError):
        agent.run(state)

    assert "analyst:missing_research_notes" in state.errors


def test_critic_requires_analysis_notes() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        research_notes="Research notes present",
    )
    agent = CriticAgent(llm_client=_SequencedLLMClient(["unused"]))

    with pytest.raises(ValidationError):
        agent.run(state)

    assert "critic:missing_analysis_notes" in state.errors


def test_critic_can_request_more_research() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        research_notes="Research notes",
        analysis_notes="Analysis notes output",
    )
    agent = CriticAgent(
        llm_client=_SequencedLLMClient(
            ["Supported points\nVERIFY: verify multi-agent latency overhead"]
        )
    )

    result = agent.run(state)

    assert result.next_agent == "researcher"
    assert result.status == "needs_more_research"
    assert result.verification_queries == ["verify multi-agent latency overhead"]
