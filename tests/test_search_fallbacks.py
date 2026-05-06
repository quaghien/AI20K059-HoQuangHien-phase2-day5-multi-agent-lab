from typing import Any

from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.services.search_client import SearchClient


class _UnavailableTavilyFactory:
    def __call__(self, api_key: str) -> Any:
        del api_key
        raise RuntimeError("Tavily unavailable")


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_search_falls_back_to_serper_when_tavily_unavailable() -> None:
    settings = Settings(TAVILY_API_KEY="tavily-key", SERPER_API_KEY="serper-key")
    client = SearchClient(
        settings=settings,
        tavily_client_factory=_UnavailableTavilyFactory(),
        http_post=lambda *args, **kwargs: _FakeResponse(
            {
                "organic": [
                    {
                        "title": "Serper result",
                        "link": "https://example.com",
                        "snippet": "Serper snippet",
                        "position": 1,
                    }
                ]
            }
        ),
    )

    results = client.search("multi-agent systems", max_results=3)

    assert len(results) == 1
    assert results[0].metadata["source_type"] == "serper"
