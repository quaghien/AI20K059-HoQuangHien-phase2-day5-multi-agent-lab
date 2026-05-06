from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.services.search_client import SearchClient


class _FakeTavilyClient:
    def search(self, query: str, max_results: int) -> dict[str, object]:
        return {
            "results": [
                {
                    "title": f"Result for {query}",
                    "url": "https://example.com",
                    "content": "A useful summary from the provider.",
                    "score": 0.9,
                }
            ][:max_results]
        }


def test_search_returns_provider_documents() -> None:
    settings = Settings(TAVILY_API_KEY="test-key")
    client = SearchClient(settings=settings, tavily_client_factory=lambda _api_key: _FakeTavilyClient())

    results = client.search("multi-agent systems", max_results=3)

    assert len(results) == 1
    assert results[0].title == "Result for multi-agent systems"
    assert results[0].url == "https://example.com"
    assert results[0].metadata["source_type"] == "tavily"
    assert client.last_search_metadata["provider_used"] == "tavily"
    assert client.last_search_metadata["estimated_cost_usd"] == 0.008


def test_search_falls_back_without_api_key() -> None:
    settings = Settings(TAVILY_API_KEY=None, SERPER_API_KEY=None)
    client = SearchClient(settings=settings)

    results = client.search("multi-agent systems", max_results=2)

    assert len(results) == 2
    assert all(result.title for result in results)
    assert all(result.snippet for result in results)
    assert results[0].metadata["source_type"] == "fallback"
    assert client.last_search_metadata["provider_used"] == "fallback"
    assert client.last_search_metadata["estimated_cost_usd"] == 0.0
