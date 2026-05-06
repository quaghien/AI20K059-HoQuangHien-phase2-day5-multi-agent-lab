"""Analyst agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def __init__(self, *, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`."""

        with trace_span(
            "agent.analyst",
            {"agent": self.name, "has_research_notes": state.research_notes is not None},
            input_payload={"research_notes": state.research_notes},
        ) as span:
            if not state.research_notes:
                error = "Analyst requires research_notes before it can run."
                state.errors.append("analyst:missing_research_notes")
                span["output"] = {"error": error}
                raise ValidationError(error)

            response = self.llm_client.complete(
                system_prompt=(
                    "You are the Analyst agent in a multi-agent research workflow. "
                    "Turn researcher notes into structured insights, highlight trade-offs, "
                    "and flag where evidence seems thin or uncertain."
                ),
                user_prompt=(
                    f"Research query: {state.request.query}\n"
                    f"Audience: {state.request.audience}\n"
                    "Create concise analysis notes with these sections: key claims, trade-offs, weak evidence.\n"
                    f"Research notes:\n{state.research_notes}"
                ),
            )
            state.analysis_notes = response.content
            state.status = "analysis_ready"
            state.next_agent = "critic"
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.ANALYST,
                    content=response.content,
                    metadata={
                        "used_research_notes": True,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "cost_usd": response.cost_usd,
                    },
                )
            )
            state.add_trace_event(
                "analyst.completed",
                {"has_analysis_notes": state.analysis_notes is not None, "next_agent": state.next_agent},
            )
            span["output"] = {
                "analysis_notes": state.analysis_notes,
                "next_agent": state.next_agent,
            }
            return state
