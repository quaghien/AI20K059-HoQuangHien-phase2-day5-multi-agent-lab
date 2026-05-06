"""Researcher agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(
        self,
        *,
        search_client: SearchClient | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.search_client = search_client or SearchClient()
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`."""

        search_query = state.request.query
        if state.verification_queries:
            search_query = " ".join(state.verification_queries)

        with trace_span(
            "agent.researcher",
            {"agent": self.name, "query": search_query},
            input_payload={"query": search_query, "max_sources": state.request.max_sources},
        ) as span:
            sources = self.search_client.search(
                query=search_query,
                max_results=state.request.max_sources,
            )
            search_metadata = getattr(self.search_client, "last_search_metadata", {})
            search_cost_usd = float(search_metadata.get("estimated_cost_usd", 0.0) or 0.0)
            state.sources = sources

            if not sources:
                state.research_notes = "No sources were found for the requested query."
                state.errors.append("researcher:no_sources")
                llm_cost_usd = 0.0
                llm_input_tokens = None
                llm_output_tokens = None
            else:
                source_bullets = "\n".join(
                    f"- {source.title}: {source.snippet}" for source in sources
                )
                response = self.llm_client.complete(
                    system_prompt=(
                        "You are the Researcher agent in a multi-agent research workflow. "
                        "Summarize the retrieved sources into concise research notes for a downstream analyst. "
                        "Use grounded language and avoid claims not supported by the provided sources."
                    ),
                    user_prompt=(
                        f"Research query: {search_query}\n"
                        f"Audience: {state.request.audience}\n"
                        "Summarize the following sources into 3-5 concise bullet-style notes.\n"
                        f"{source_bullets}"
                    ),
                )
                if state.verification_queries and state.research_notes:
                    state.research_notes = (
                        f"{state.research_notes}\n\nAdditional verification research:\n{response.content}"
                    )
                else:
                    state.research_notes = response.content
                state.verification_queries = []
                state.status = "research_ready"
                state.next_agent = "analyst"
                llm_cost_usd = float(response.cost_usd or 0.0)
                llm_input_tokens = response.input_tokens
                llm_output_tokens = response.output_tokens

            result_content = state.research_notes or "Research step produced no notes."
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.RESEARCHER,
                    content=result_content,
                    metadata={
                        "source_count": len(state.sources),
                        "search_provider": search_metadata.get("provider_used"),
                        "search_cost_usd": round(search_cost_usd, 6),
                        "llm_cost_usd": round(llm_cost_usd, 6),
                        "cost_usd": round(search_cost_usd + llm_cost_usd, 6),
                        "input_tokens": llm_input_tokens,
                        "output_tokens": llm_output_tokens,
                    },
                )
            )
            state.add_trace_event(
                "researcher.completed",
                {
                    "source_count": len(state.sources),
                    "has_notes": state.research_notes is not None,
                    "search_provider": search_metadata.get("provider_used"),
                    "cost_usd": round(search_cost_usd + llm_cost_usd, 6),
                },
            )
            span["output"] = {
                "source_count": len(state.sources),
                "research_notes": state.research_notes,
            }
            return state
