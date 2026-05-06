# Sprint Plan Index

## Mục tiêu chung

Bộ tài liệu này chia bài lab multi-agent research thành 5 sprint nhỏ để triển khai tuần tự, có kiểm thử rõ ràng và bám sát deliverable của repo:

- Single-agent baseline chạy được.
- Multi-agent workflow chạy được bằng LangGraph.
- Langfuse trace lưu được prompt/completion của mỗi LLM call.
- Benchmark so sánh được single-agent vs multi-agent theo latency, cost, quality.
- Report cuối map được sang tiêu chí trong `docs/peer_review_rubric.md`.

## Kiến trúc đã chọn

- Workflow engine: `LangGraph`
- LLM provider: `OpenAI -> Anthropic -> local fallback`
- Search provider: `Tavily -> Serper.dev -> local fallback`
- Tracing: `Langfuse`, lưu đầy đủ `system_prompt`, `user_prompt`, `response.content`, model, token usage, cost
- Routing policy: deterministic state-based router
- Core workflow: `Supervisor -> Researcher -> Analyst -> Critic -> Researcher? -> Writer`
- Quality scoring: `LLM-as-a-judge`
- Benchmark scope: `5 query mẫu`, mỗi query yêu cầu search hoặc multi-source synthesis

## Thứ tự sprint

1. [Sprint 1: Baseline and Tracing](./sprint_1_baseline_and_tracing.md)
2. [Sprint 2: Search and Researcher](./sprint_2_search_and_researcher.md)
3. [Sprint 3: Analyst, Critic, and State](./sprint_3_analyst_critic_and_state.md)
4. [Sprint 4: Supervisor and LangGraph](./sprint_4_supervisor_and_langgraph.md)
5. [Sprint 5: Writer, Benchmark, Judge, and Report](./sprint_5_writer_benchmark_and_report.md)

## Dependency giữa các sprint

- Sprint 1 phải xong trước vì `LLMClient` và tracing là nền cho mọi agent.
- Sprint 2 phụ thuộc Sprint 1 để `Researcher` có thể gọi LLM và search service.
- Sprint 3 phụ thuộc Sprint 2 vì `Analyst` và `Critic` cần `research_notes` và `sources`.
- Sprint 4 phụ thuộc Sprint 3 vì workflow cần đủ agent và state handoff.
- Sprint 5 phụ thuộc Sprint 4 vì benchmark và report cần workflow chạy end-to-end.

Nguyên tắc thực hiện:

- Không bắt đầu sprint sau khi sprint trước chưa đạt acceptance criteria.
- Nếu bị chặn bởi API key hoặc provider, phải dùng fallback đã nêu trong sprint tương ứng thay vì bỏ trống chức năng.

## Checklist hoàn thành toàn lab

- `baseline` CLI chạy được bằng LLM thật hoặc fallback có kiểm soát.
- Multi-agent workflow chạy được end-to-end qua `Supervisor -> Researcher -> Analyst -> Critic -> Writer`.
- Nếu `Critic` yêu cầu `VERIFY:`, workflow phải quay lại `Researcher` trước khi sang `Writer`.
- Langfuse hiển thị được prompt/completion cho các LLM generation chính.
- Benchmark có đúng `5` query thiết kế để favor multi-agent, có số liệu `latency`, `cost`, `quality`, `citation_coverage`.
- `reports/benchmark_report.md` giải thích được vì sao multi-agent tốt hơn hoặc kém hơn baseline ở từng metric.

## Mapping sang peer review rubric

| Rubric item | Sprint chính |
|---|---|
| Role clarity | Sprint 2, 3, 4 |
| State design | Sprint 3, 4 |
| Failure guard | Sprint 1, 4, 5 |
| Benchmark | Sprint 5 |
| Trace explanation | Sprint 1, 4, 5 |

## Quy ước test coverage

Mỗi sprint đều phải mô tả đủ 3 lớp test:

- `Unit tests`
- `Integration or workflow tests`
- `Failure-path tests`

Khi triển khai thật:

- Luôn chạy `make test`
- Nếu thêm file test mới, cần map test đó vào sprint tương ứng
- Không chỉ kiểm “chạy được”, mà phải kiểm đúng shape của `state`, `trace`, `metrics`, và hành vi fallback
