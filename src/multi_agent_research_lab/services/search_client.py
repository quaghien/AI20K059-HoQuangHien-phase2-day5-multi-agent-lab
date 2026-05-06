"""Search client abstraction for ResearcherAgent."""

import logging
from typing import Any, Callable

import requests

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

logger = logging.getLogger(__name__)


class SearchClient:
    """Search client with Tavily primary, Serper fallback, then local fallback."""

    TAVILY_BASIC_SEARCH_CREDITS = 1
    TAVILY_PAYG_USD_PER_CREDIT = 0.008
    SERPER_STARTER_USD_PER_QUERY = 50 / 50_000

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        tavily_client_factory: Callable[[str], Any] | None = None,
        http_post: Callable[..., requests.Response] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._tavily_client_factory = tavily_client_factory or self._build_tavily_client
        self._http_post = http_post or requests.post
        self.last_search_metadata: dict[str, Any] = {
            "provider_used": "none",
            "estimated_cost_usd": 0.0,
        }

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query."""

        normalized_query = query.strip()
        if not normalized_query:
            self.last_search_metadata = {"provider_used": "none", "estimated_cost_usd": 0.0}
            return []

        tavily_results = self._search_with_tavily(normalized_query, max_results)
        if tavily_results:
            self.last_search_metadata = {
                "provider_used": "tavily",
                "estimated_cost_usd": round(
                    self.TAVILY_BASIC_SEARCH_CREDITS * self.TAVILY_PAYG_USD_PER_CREDIT,
                    6,
                ),
            }
            return tavily_results

        serper_results = self._search_with_serper(normalized_query, max_results)
        if serper_results:
            self.last_search_metadata = {
                "provider_used": "serper",
                "estimated_cost_usd": round(self.SERPER_STARTER_USD_PER_QUERY, 6),
            }
            return serper_results

        self.last_search_metadata = {
            "provider_used": "fallback",
            "estimated_cost_usd": 0.0,
        }
        return self._fallback_results(normalized_query, max_results, reason="all_providers_unavailable")

    def _search_with_tavily(self, query: str, max_results: int) -> list[SourceDocument]:
        if not self.settings.tavily_api_key:
            return []
        try:
            client = self._tavily_client_factory(self.settings.tavily_api_key)
            raw_response = client.search(query=query, max_results=max_results)
            documents = self._parse_tavily_results(raw_response, max_results)
            if not documents:
                logger.warning("Tavily returned no usable results; trying Serper fallback.")
            return documents
        except RuntimeError as exc:
            logger.warning("Tavily unavailable (%s); trying Serper fallback.", exc)
            return []
        except Exception:
            logger.exception("Tavily search failed; trying Serper fallback.")
            return []

    def _search_with_serper(self, query: str, max_results: int) -> list[SourceDocument]:
        if not self.settings.serper_api_key:
            return []
        try:
            response = self._http_post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.settings.serper_api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": max_results},
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return self._parse_serper_results(payload, max_results)
        except Exception:
            logger.exception("Serper fallback search failed; using local fallback.")
            return []

    def _build_tavily_client(self, api_key: str) -> Any:
        try:
            from tavily import TavilyClient
        except ImportError as exc:
            raise RuntimeError("Tavily package is not installed.") from exc
        return TavilyClient(api_key=api_key)

    def _parse_tavily_results(self, raw_response: Any, max_results: int) -> list[SourceDocument]:
        results = []
        provider_results = raw_response.get("results", []) if isinstance(raw_response, dict) else getattr(raw_response, "results", [])
        for item in provider_results[:max_results]:
            title = str(item.get("title") or "Untitled source").strip()
            snippet = str(item.get("content") or item.get("snippet") or "").strip()
            if not snippet:
                continue
            results.append(
                SourceDocument(
                    title=title,
                    url=item.get("url"),
                    snippet=snippet,
                    metadata={"source_type": "tavily", "score": item.get("score")},
                )
            )
        return results

    def _parse_serper_results(self, payload: dict[str, Any], max_results: int) -> list[SourceDocument]:
        results = []
        for item in payload.get("organic", [])[:max_results]:
            title = str(item.get("title") or "Untitled source").strip()
            snippet = str(item.get("snippet") or "").strip()
            if not snippet:
                continue
            results.append(
                SourceDocument(
                    title=title,
                    url=item.get("link"),
                    snippet=snippet,
                    metadata={"source_type": "serper", "position": item.get("position")},
                )
            )
        return results

    def _fallback_results(self, query: str, max_results: int, *, reason: str) -> list[SourceDocument]:
        fallback_docs = [
            SourceDocument(
                title="Fallback research note",
                url=None,
                snippet=(
                    f"Local fallback summary for query: {query}. "
                    "This source exists so the researcher flow can proceed when live search is unavailable."
                ),
                metadata={"source_type": "fallback", "reason": reason},
            ),
            SourceDocument(
                title="Fallback benchmarking note",
                url=None,
                snippet=(
                    "Multi-agent labs should preserve a deterministic fallback path for testing, "
                    "benchmark dry runs, and provider outage scenarios."
                ),
                metadata={"source_type": "fallback", "reason": reason},
            ),
        ]
        return fallback_docs[:max_results]
