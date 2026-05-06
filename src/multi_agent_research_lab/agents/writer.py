"""Writer agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient


class WriterAgent(BaseAgent):
    """Produces final answer from research, analysis, and critique notes."""

    name = "writer"

    def __init__(self, *, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`."""

        with trace_span(
            "agent.writer",
            {
                "agent": self.name,
                "has_research_notes": state.research_notes is not None,
                "has_analysis_notes": state.analysis_notes is not None,
                "has_critic_notes": state.critic_notes is not None,
            },
            input_payload={
                "research_notes": state.research_notes,
                "analysis_notes": state.analysis_notes,
                "critic_notes": state.critic_notes,
            },
        ) as span:
            if not state.analysis_notes or not state.critic_notes:
                error = "Writer requires analysis_notes and critic_notes before it can run."
                state.errors.append("writer:missing_required_notes")
                span["output"] = {"error": error}
                raise ValidationError(error)

            # Format sources for citation
            sources_text = ""
            if state.sources:
                sources_text = "Sources:\n"
                for i, source in enumerate(state.sources, 1):
                    url_display = f" - {source.url}" if source.url else ""
                    sources_text += f"[{i}] {source.title}{url_display}\n"
                sources_text += "\n"

            response = self.llm_client.complete(
                system_prompt=(
                    "You are the Writer agent in a multi-agent research workflow. "
                    "Write a concise final answer for a technical learner using the supplied research, analysis, "
                    "and critic notes. Mention uncertainty when the critic identifies weak evidence. "
                    "IMPORTANT: You MUST cite sources using [1], [2], etc. inline in your text, and provide a complete "
                    "References section at the end listing all sources you referenced."
                ),
                user_prompt=(
                    f"Research query: {state.request.query}\n"
                    f"Audience: {state.request.audience}\n\n"
                    f"{sources_text}"
                    f"Research notes:\n{state.research_notes or 'None'}\n\n"
                    f"Analysis notes:\n{state.analysis_notes}\n\n"
                    f"Critic notes:\n{state.critic_notes}\n\n"
                    "Write a concise final answer in paragraph form. "
                    "Make sure to include inline citations [1], [2], etc. and end with a References section."
                ),
            )
            state.final_answer = response.content
            state.status = "completed"
            state.next_agent = "done"
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.WRITER,
                    content=response.content,
                    metadata={
                        "used_critic_notes": True,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "cost_usd": response.cost_usd,
                    },
                )
            )
            state.add_trace_event(
                "writer.completed",
                {"has_final_answer": state.final_answer is not None, "next_agent": state.next_agent},
            )
            span["output"] = {"final_answer": state.final_answer, "next_agent": state.next_agent}
            return state
