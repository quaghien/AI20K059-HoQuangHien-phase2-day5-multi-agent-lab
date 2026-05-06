"""Critic agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient


class CriticAgent(BaseAgent):
    """Reviews analysis notes before the writer synthesizes the final answer."""

    name = "critic"

    def __init__(self, *, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Validate analysis notes and append critique for downstream writing."""

        with trace_span(
            "agent.critic",
            {"agent": self.name, "has_analysis_notes": state.analysis_notes is not None},
            input_payload={"analysis_notes": state.analysis_notes},
        ) as span:
            if not state.analysis_notes:
                error = "Critic requires analysis_notes before it can run."
                state.errors.append("critic:missing_analysis_notes")
                span["output"] = {"error": error}
                raise ValidationError(error)

            response = self.llm_client.complete(
                system_prompt=(
                    "You are the Critic agent in a multi-agent research workflow. "
                    "Review the analyst's reasoning, identify unsupported claims, weak evidence, "
                    "and suggest corrections before the writer produces a final answer. "
                    "If more evidence is required, add one or more lines starting with VERIFY: followed by "
                    "a concrete search query for the Researcher."
                ),
                user_prompt=(
                    f"Research query: {state.request.query}\n"
                    "Review the following analysis notes. Return concise critique notes with these sections: "
                    "supported points, weak claims, recommended fixes. Add VERIFY lines only when more research is needed.\n"
                    f"Analysis notes:\n{state.analysis_notes}"
                ),
            )
            state.critic_notes = response.content
            state.verification_queries = self._extract_verification_queries(response.content)
            if state.verification_queries:
                state.status = "needs_more_research"
                state.next_agent = "researcher"
            else:
                state.status = "critique_ready"
                state.next_agent = "writer"
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.CRITIC,
                    content=response.content,
                    metadata={
                        "reviewed_analysis": True,
                        "verification_queries": state.verification_queries,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "cost_usd": response.cost_usd,
                    },
                )
            )
            state.add_trace_event(
                "critic.completed",
                {
                    "has_critic_notes": state.critic_notes is not None,
                    "next_agent": state.next_agent,
                    "verification_query_count": len(state.verification_queries),
                },
            )
            span["output"] = {
                "critic_notes": state.critic_notes,
                "next_agent": state.next_agent,
                "verification_queries": state.verification_queries,
            }
            return state

    def _extract_verification_queries(self, critique: str) -> list[str]:
        queries: list[str] = []
        for line in critique.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("VERIFY:"):
                query = stripped.split(":", 1)[1].strip()
                if query:
                    queries.append(query)
        return queries
