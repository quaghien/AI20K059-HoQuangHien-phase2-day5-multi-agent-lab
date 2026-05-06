"""Benchmark helpers for single-agent vs multi-agent runs."""

from time import perf_counter
from typing import Callable

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


Runner = Callable[[str], ResearchState]


def run_benchmark(
    run_name: str,
    query: str,
    runner: Runner,
    *,
    judge: Callable[[str, ResearchState], float | None] | None = None,
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency and summarize benchmark-friendly metrics."""

    started = perf_counter()
    state = runner(query)
    latency = perf_counter() - started

    quality_score: float | None = None
    notes: list[str] = []
    if judge is not None:
        try:
            quality_score = judge(query, state)
            state.judge_score = quality_score
        except Exception as exc:
            notes.append(f"judge_failed:{exc.__class__.__name__}")

    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency,
        estimated_cost_usd=_estimate_run_cost(state),
        quality_score=quality_score,
        citation_coverage=_estimate_citation_coverage(state),
        notes="; ".join(notes + _build_state_notes(state)),
    )
    return state, metrics


def llm_as_a_judge(
    query: str,
    state: ResearchState,
    *,
    llm_client: LLMClient | None = None,
) -> float | None:
    """Use the shared LLM client to assign a 0-10 quality score."""

    client = llm_client or LLMClient()
    has_inline_citations = bool(state.final_answer and "[1]" in state.final_answer)
    has_sources = bool(state.sources)
    citation_hint = (
        "The answer includes inline citations [1],[2]… and was grounded in retrieved sources."
        if has_inline_citations
        else "The answer has NO inline citations and no retrieved sources backing it."
    )
    response = client.complete(
        system_prompt=(
            "You are an evaluation judge for a multi-agent research lab. "
            "Score the final answer from 0 to 10 using this rubric:\n"
            "- Factual accuracy and depth (0-3 pts): Does the answer contain specific, verifiable claims?\n"
            "- Source grounding and citations (0-3 pts): Are claims backed by retrieved sources with inline [N] citations? "
            "Answers with NO citations on factual topics should score 0-1 here.\n"
            "- Handling of uncertainty (0-2 pts): Does it acknowledge weak evidence or conflicting data?\n"
            "- Usefulness and clarity (0-2 pts): Is it clear and actionable for a technical learner?\n"
            "Return ONLY the numeric total score (e.g. '7.5')."
        ),
        user_prompt=(
            f"Query: {query}\n\n"
            f"Citation status: {citation_hint}\n"
            f"Sources available: {len(state.sources)} retrieved documents\n\n"
            f"Final answer:\n{state.final_answer or 'None'}\n\n"
            f"Research notes:\n{state.research_notes or 'None'}\n\n"
            f"Analysis notes:\n{state.analysis_notes or 'None'}\n\n"
            f"Critic notes:\n{state.critic_notes or 'None'}"
        ),
    )
    return _parse_judge_score(response.content)


def _parse_judge_score(raw_score: str) -> float | None:
    for token in raw_score.replace("/", " ").split():
        cleaned = "".join(char for char in token if char.isdigit() or char == ".")
        if not cleaned:
            continue
        try:
            score = float(cleaned)
        except ValueError:
            continue
        if 0 <= score <= 10:
            return score
    return None


def _estimate_run_cost(state: ResearchState) -> float | None:
    total_cost = 0.0
    found_cost = False
    for result in state.agent_results:
        cost = result.metadata.get("cost_usd")
        if isinstance(cost, (int, float)):
            total_cost += float(cost)
            found_cost = True
    return round(total_cost, 6) if found_cost else None


def _estimate_citation_coverage(state: ResearchState) -> float | None:
    if not state.final_answer:
        return None
    if not state.sources:
        return 0.0
    cited = sum(1 for i in range(1, len(state.sources) + 1) if f"[{i}]" in state.final_answer)
    return round(cited / len(state.sources), 2)


def _build_state_notes(state: ResearchState) -> list[str]:
    notes: list[str] = []
    if state.errors:
        notes.append(f"errors={len(state.errors)}")
    if state.final_answer is None:
        notes.append("missing_final_answer")
    return notes
