from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMResponse


class _FakeSearchClient:
    def __init__(self, sources: list[SourceDocument]) -> None:
        self._sources = sources
        self.last_search_metadata = {"provider_used": "tavily", "estimated_cost_usd": 0.008}

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        return self._sources[:max_results]


class _FakeLLMClient:
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        return LLMResponse(
            content="Research notes:\n- Source 1 supports the main claim.\n- Source 2 adds benchmarking context.",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0012,
        )


def test_researcher_updates_sources_and_notes() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    sources = [
        SourceDocument(title="Doc 1", url="https://example.com/1", snippet="Snippet 1"),
        SourceDocument(title="Doc 2", url="https://example.com/2", snippet="Snippet 2"),
    ]
    agent = ResearcherAgent(search_client=_FakeSearchClient(sources), llm_client=_FakeLLMClient())

    result = agent.run(state)

    assert len(result.sources) == 2
    assert result.research_notes is not None
    assert result.analysis_notes is None
    assert result.final_answer is None
    assert result.agent_results[-1].metadata["source_count"] == 2
    assert result.agent_results[-1].metadata["search_cost_usd"] == 0.008
    assert result.agent_results[-1].metadata["llm_cost_usd"] == 0.0012
    assert result.agent_results[-1].metadata["cost_usd"] == 0.0092
    assert result.trace[-1]["name"] == "researcher.completed"


def test_researcher_handles_empty_sources() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    agent = ResearcherAgent(search_client=_FakeSearchClient([]), llm_client=_FakeLLMClient())

    result = agent.run(state)

    assert result.sources == []
    assert result.research_notes == "No sources were found for the requested query."
    assert "researcher:no_sources" in result.errors
    assert result.agent_results[-1].metadata["cost_usd"] == 0.008


def test_researcher_uses_verification_queries_when_present() -> None:
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        research_notes="Initial research notes",
        verification_queries=["verify multi-agent latency overhead"],
    )
    sources = [SourceDocument(title="Doc 1", url="https://example.com/1", snippet="Snippet 1")]
    agent = ResearcherAgent(search_client=_FakeSearchClient(sources), llm_client=_FakeLLMClient())

    result = agent.run(state)

    assert result.verification_queries == []
    assert "Additional verification research:" in (result.research_notes or "")
    assert result.next_agent == "analyst"
