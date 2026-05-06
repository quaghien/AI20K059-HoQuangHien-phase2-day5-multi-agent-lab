"""Command-line entrypoint for the lab starter."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import StudentTodoError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import llm_as_a_judge, run_benchmark
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import trace_run
from multi_agent_research_lab.services.llm_client import LLMClient

app = typer.Typer(help="Multi-Agent Research Lab starter CLI")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a minimal single-agent baseline backed by the shared LLM client."""

    _init()
    request = ResearchQuery(query=query)
    state = ResearchState(request=request)
    settings = get_settings()
    with trace_run(
        "cli.baseline",
        input_payload={"query": query, "audience": request.audience},
        metadata={"command": "baseline"},
        settings=settings,
    ) as run:
        llm_client = LLMClient(settings=settings)
        response = llm_client.complete(
            system_prompt=(
                "You are a concise research assistant for technical learners. "
                "Give a short, grounded answer and mention when the response is a fallback."
            ),
            user_prompt=(
                f"Research query: {query}\n"
                f"Audience: {request.audience}\n"
                "Respond in a concise paragraph."
            ),
        )
        state.final_answer = response.content
        run["output"] = {"final_answer": state.final_answer}
    console.print(Panel.fit(state.final_answer, title="Single-Agent Baseline"))


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the multi-agent workflow skeleton."""

    _init()
    settings = get_settings()
    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow()
    try:
        with trace_run(
            "cli.multi_agent",
            input_payload={"query": query, "audience": state.request.audience},
            metadata={"command": "multi-agent"},
            settings=settings,
        ) as run:
            result = workflow.run(state)
            run["output"] = {
                "route_history": result.route_history,
                "final_answer": result.final_answer,
                "errors": result.errors,
            }
    except StudentTodoError as exc:
        console.print(Panel.fit(str(exc), title="Expected TODO", style="yellow"))
        raise typer.Exit(code=2) from exc
    console.print(result.model_dump_json(indent=2))


@app.command()
def benchmark() -> None:
    """Run benchmark suite: baseline vs multi-agent on preset queries."""

    _init()
    settings = get_settings()
    
    # 5 benchmark queries — each requires recent knowledge, multi-source synthesis, or
    # fact-verification that a single LLM call without search cannot answer reliably.
    benchmark_queries = [
        # Q1: Requires up-to-date pricing/specs across providers → multi-source synthesis, analyst adds value
        "What are the exact context window sizes, API pricing per million tokens, and MMLU scores for GPT-4o, Claude 3.7 Sonnet, Gemini 2.0 Flash, and Llama 3.3 70B as of Q1 2026?",
        # Q2: Requires 2025-2026 release data beyond training cutoff → search essential, critic verifies claims
        "Which open-source LLM models released between October 2025 and March 2026 achieve over 80% on HumanEval, and how do they compare in parameter count and inference speed?",
        # Q3: Requires aggregating specific numbers from recent papers → analyst + VERIFY loop adds value
        "What specific RAG improvements published in 2025-2026 reduce hallucination in multi-hop QA, and what benchmark numbers do the papers report?",
        # Q4: Requires reconciling conflicting regulatory documents across jurisdictions → analyst + critic essential
        "How do EU AI Act enforcement requirements active in 2025-2026 differ from US NIST AI RMF 2.0 for deploying LLM-based systems in high-risk applications?",
        # Q5: Requires current throughput/latency data from deployment benchmarks → search + verification loop
        "What are the current latency, memory, and throughput benchmarks for running Llama 3.1 405B vs Mistral Large 2 vs Qwen 2.5 72B on H100 GPUs using vLLM as of 2025-2026?",
    ]

    console.print(Panel.fit(f"Starting benchmark with {len(benchmark_queries)} queries...", title="Benchmark", style="cyan"))

    metrics_list = []

    for i, query in enumerate(benchmark_queries, 1):
        console.print(f"\n[{i}/{len(benchmark_queries)}] Query: {query}")

        # Run baseline
        console.print("  → Running baseline...")
        def baseline_runner(q: str) -> ResearchState:
            request = ResearchQuery(query=q)
            state = ResearchState(request=request)
            with trace_run(
                "cli.benchmark.baseline",
                input_payload={"query": q},
                metadata={"command": "benchmark-baseline", "query_index": i},
                settings=settings,
            ):
                llm_client = LLMClient(settings=settings)
                response = llm_client.complete(
                    system_prompt=(
                        "You are a concise research assistant for technical learners. "
                        "Give a short, grounded answer and mention when the response is a fallback."
                    ),
                    user_prompt=(f"Research query: {q}\nAudience: {request.audience}\nRespond in a concise paragraph."),
                )
                state.final_answer = response.content
                state.agent_results.append(AgentResult(
                    agent=AgentName.WRITER,
                    content=response.content,
                    metadata={"cost_usd": response.cost_usd or 0.0},
                ))
            return state

        baseline_state, baseline_metrics = run_benchmark(
            f"baseline-q{i}",
            query,
            baseline_runner,
            judge=lambda q, s: llm_as_a_judge(q, s, llm_client=LLMClient(settings=settings)),
        )
        metrics_list.append(baseline_metrics)
        console.print(f"     Latency: {baseline_metrics.latency_seconds:.2f}s, Cost: ${baseline_metrics.estimated_cost_usd or 0:.4f}")

        # Run multi-agent
        console.print("  → Running multi-agent...")
        def multi_agent_runner(q: str) -> ResearchState:
            state = ResearchState(request=ResearchQuery(query=q))
            workflow = MultiAgentWorkflow()
            with trace_run(
                "cli.benchmark.multi_agent",
                input_payload={"query": q},
                metadata={"command": "benchmark-multi-agent", "query_index": i},
                settings=settings,
            ):
                result = workflow.run(state)
            return result

        multi_agent_state, multi_agent_metrics = run_benchmark(
            f"multi-agent-q{i}",
            query,
            multi_agent_runner,
            judge=lambda q, s: llm_as_a_judge(q, s, llm_client=LLMClient(settings=settings)),
        )
        metrics_list.append(multi_agent_metrics)
        console.print(f"     Latency: {multi_agent_metrics.latency_seconds:.2f}s, Cost: ${multi_agent_metrics.estimated_cost_usd or 0:.4f}")

    console.print(Panel.fit("✓ Benchmark complete.", title="Success", style="green"))
