import pytest

from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import AgentResult, AgentName, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import llm_as_a_judge, run_benchmark
from multi_agent_research_lab.services.llm_client import LLMResponse


class _FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        del system_prompt
        del user_prompt
        return LLMResponse(content=self._responses.pop(0), input_tokens=140, output_tokens=70, cost_usd=0.0031)


def test_writer_generates_final_answer() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        research_notes="research notes",
        analysis_notes="analysis notes",
        critic_notes="critic notes",
    )
    agent = WriterAgent(llm_client=_FakeLLMClient(["Final answer output"]))

    result = agent.run(state)

    assert result.final_answer == "Final answer output"
    assert result.next_agent == "done"
    assert result.status == "completed"
    assert result.agent_results[-1].agent == AgentName.WRITER
    assert result.agent_results[-1].metadata["cost_usd"] == 0.0031
    assert result.trace[-1]["name"] == "writer.completed"


def test_writer_requires_analysis_and_critic_notes() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        research_notes="research notes",
    )
    agent = WriterAgent(llm_client=_FakeLLMClient(["unused"]))

    with pytest.raises(ValidationError):
        agent.run(state)

    assert "writer:missing_required_notes" in state.errors


def test_run_benchmark_collects_metrics_and_judge_score() -> None:
    def runner(query: str) -> ResearchState:
        state = ResearchState(
            request=ResearchQuery(query=query),
            research_notes="research notes",
            analysis_notes="analysis notes",
            critic_notes="critic notes",
            final_answer="final answer",
        )
        state.agent_results.append(
            AgentResult(agent=AgentName.WRITER, content="final answer", metadata={"cost_usd": 0.0123})
        )
        return state

    state, metrics = run_benchmark("multi-agent", "Explain multi-agent systems", runner, judge=lambda _q, _s: 8.5)

    assert state.judge_score == 8.5
    assert metrics.run_name == "multi-agent"
    assert metrics.quality_score == 8.5
    assert metrics.estimated_cost_usd == 0.0123
    assert metrics.citation_coverage == 0.0


def test_llm_as_a_judge_parses_numeric_score() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        final_answer="final answer",
    )

    score = llm_as_a_judge(
        "Explain multi-agent systems",
        state,
        llm_client=_FakeLLMClient(["8.5"]),
    )

    assert score == 8.5
