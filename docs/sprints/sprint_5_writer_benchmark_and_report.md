# Sprint 5: Writer, Benchmark, Judge, and Report

## Goal

Hoàn thiện output cuối và deliverable của lab:

- Implement `WriterAgent.run`
- Benchmark `single-agent vs multi-agent`
- Thêm `LLM-as-a-judge`
- Render `reports/benchmark_report.md`

## Technical decisions locked in this sprint

- `Writer` phải dựa trên `research_notes`, `analysis_notes`, `critic_notes`
- **[NEW]** Writer agent thêm **citation support**: inline citations `[1], [2]...` và References section
- **[NEW]** Writer enforces grounding: tất cả sources từ Researcher được đưa vào prompt để LLM có context
- Quality score dùng `LLM-as-a-judge`
- Benchmark scope là `5 query mẫu`
- Report markdown phải map được sang rubric review và giải thích được trace
- **[NEW]** Citation coverage metric: 0.0 (baseline no citations) vs 1.0 (multi-agent with grounded citations)

## Implementation scope

- `WriterAgent` tổng hợp final answer từ các notes đã qua critic
- **[NEW]** Writer format sources từ `state.sources` thành danh sách `[1] Title - URL, [2] Title - URL...`
- **[NEW]** Writer prompt yêu cầu LLM:
  - Chèn inline citations `[1], [2]` vào text
  - Cung cấp References section cuối cùng với đầy đủ source details
- `run_benchmark` thu thập latency, cost, quality, notes, **citation_coverage**
- Thêm judge path để chấm baseline và multi-agent theo cùng rubric
- `render_markdown_report` tạo báo cáo markdown đủ để nộp lab
- Benchmark nên bao gồm ít nhất một query kích hoạt vòng `Critic -> Researcher -> Writer`
- `estimated_cost_usd` nên được cộng từ `agent_results.metadata.cost_usd` của từng stage, thay vì để benchmark phụ thuộc vào trace backend

## Primary files

- `src/multi_agent_research_lab/agents/writer.py` (citation + grounding support)
- `src/multi_agent_research_lab/evaluation/benchmark.py` (citation_coverage metric)
- `src/multi_agent_research_lab/evaluation/report.py` (render citations in report)
- `reports/benchmark_report.md` (citation coverage comparison)
- `src/multi_agent_research_lab/core/schemas.py` (BenchmarkMetrics.citation_coverage)

## Out of scope

- Tối ưu production eval pipeline
- Dashboard visualization ngoài markdown report
- Mở rộng benchmark set lớn hơn 5 query hoặc tự động hóa query generation

## Acceptance criteria

- `WriterAgent.run` tạo được `final_answer` với inline citations `[1], [2]...`
- Final answer chứa References section liệt kê đầy đủ sources từ `state.sources`
- Benchmark chạy được cho `single-agent` và `multi-agent`
- Metrics có tối thiểu `latency_seconds`, `estimated_cost_usd`, `quality_score`, **`citation_coverage`**
- Report markdown có đủ run names, citation coverage column, và giải thích grounding benefit

## Test plan

### Unit tests

- Test `WriterAgent` sinh `final_answer` từ state đầy đủ **với inline citations**
- Test sources được format đúng `[1] Title - URL` format
- Test `final_answer` chứa References section
- Test metrics object có shape hợp lệ (including `citation_coverage`)
- Test `render_markdown_report` render đúng cột (latency, cost, quality, **citation_coverage**) và run name

### Integration or workflow tests

- Test benchmark chạy được với runner mock cho baseline và multi-agent
- Test judge score được ghi vào metrics và xuất ra report
- Test benchmark/report không làm mất thông tin khi multi-agent có vòng verify bổ sung

### Failure-path tests

- Thiếu `critic_notes` hoặc `analysis_notes` thì Writer phải xử lý có kiểm soát
- Judge fail thì benchmark vẫn giữ được latency/cost và note lỗi phù hợp
- Report generation không được crash chỉ vì thiếu một metric optional
- Multi-agent có thêm vòng verify thì report vẫn phải render route/notes hợp lệ

## Risks and fallback

- Rủi ro: judge model tốn chi phí hoặc phản hồi không ổn định
- Fallback: lưu quality là `None` và ghi rõ note khi judge không chạy được
- Rủi ro: report quá đẹp nhưng không map sang rubric
- Fallback: ép report có mục giải thích theo từng tiêu chí benchmark/trace

## Deliverables

- `WriterAgent.run` hoạt động
- `run_benchmark` có metrics usable
- `reports/benchmark_report.md` đủ nội dung để peer review và nộp lab

## Benchmark query design rationale

5 query được chọn để tạo lợi thế rõ ràng cho multi-agent pipeline so với single LLM call:

| # | Query focus | Tại sao multi-agent có lợi |
|---|---|---|
| Q1 | Context window, pricing, MMLU của 4 model Q1 2026 | Số liệu cụ thể thay đổi nhanh → search thiết yếu; nhiều nguồn mâu thuẫn → analyst + critic cần thiết |
| Q2 | Open-source model ra mắt Oct 2025 – Mar 2026, HumanEval ≥ 80% | Ngoài training cutoff → search bắt buộc; claims cần verify → VERIFY loop kích hoạt |
| Q3 | RAG techniques giảm hallucination trong multi-hop QA từ paper 2025-2026 | Cần tổng hợp nhiều paper với số liệu cụ thể → analyst tổng hợp, critic kiểm tra số |
| Q4 | So sánh EU AI Act vs US NIST AI RMF 2.0 cho LLM high-risk | Cần đối chiếu tài liệu pháp lý nhiều nguồn → analyst + critic essential |
| Q5 | Latency/memory/throughput cho 3 model lớn trên H100 vLLM 2025-2026 | Benchmark số liệu deployment thay đổi theo version → search + verification loop |

**Nguyên tắc chọn query:** mỗi query phải thỏa ít nhất 2 trong 3 điều kiện:
1. Kiến thức sau training cutoff → search không thể bỏ
2. Số liệu cụ thể từ nhiều nguồn → analyst tổng hợp và critic cross-check
3. Claims có thể bị verify sai → VERIFY loop của Critic thực sự kích hoạt

## Implementation notes after rollout

- `Writer` hiện yêu cầu tối thiểu `analysis_notes` và `critic_notes`; nếu thiếu sẽ fail bằng `ValidationError`
- Judge path hiện parse numeric score từ model output và fallback về `None` nếu parse thất bại
- `reports/benchmark_report.md` ghi rõ latency, cost, quality_score, citation_coverage cho từng run
- Route history của mỗi multi-agent run lưu trong `state.route_history` để trace explanation rõ ràng
- Citation coverage là tỷ lệ `[N]` citations thực sự xuất hiện trong `final_answer` so với tổng sources, không phải binary flag
