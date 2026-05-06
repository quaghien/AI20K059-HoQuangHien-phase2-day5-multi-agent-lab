# Workflow Diagrams

Folder này chứa các diagram SVG workflow cho toàn bộ hệ thống và từng sprint.

## Danh sách diagram

| File | Mô tả |
|---|---|
| [system_overview.svg](system_overview.svg) | Kiến trúc tổng — LangGraph loop, VERIFY re-research, 3-level tracing |
| [sprint_1_baseline_tracing.svg](sprint_1_baseline_tracing.svg) | Sprint 1: LLMClient → OpenAI → Anthropic → local fallback → Langfuse trace_generation |
| [sprint_2_search_researcher.svg](sprint_2_search_researcher.svg) | Sprint 2: SearchClient (Tavily→Serper→local + cost tracking) → ResearcherAgent |
| [sprint_3_analyst_critic_state.svg](sprint_3_analyst_critic_state.svg) | Sprint 3: AnalystAgent → CriticAgent → VERIFY loop → ResearchState fields mới |
| [sprint_4_supervisor_langgraph.svg](sprint_4_supervisor_langgraph.svg) | Sprint 4: SupervisorAgent deterministic router → StateGraph → guardrails |
| [sprint_5_writer_benchmark_report.svg](sprint_5_writer_benchmark_report.svg) | Sprint 5: WriterAgent → BenchmarkMetrics → LLM-as-a-Judge → benchmark_report.md |

## Cách xem

Mở file `.svg` trực tiếp trong trình duyệt hoặc xem inline trong VS Code. Tất cả là vector — zoom không vỡ.
