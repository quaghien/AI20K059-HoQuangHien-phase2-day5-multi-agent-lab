# Lab 20: Multi-Agent Research System Starter

Starter repo cho bài lab **Multi-Agent Systems**: xây dựng hệ thống nghiên cứu gồm **Supervisor + Researcher + Analyst + Writer** và benchmark với single-agent baseline.

> Mục tiêu của repo này là cung cấp **production-grade skeleton** để học viên phát triển code cá nhân. Các phần logic quan trọng được để ở dạng `TODO` để học viên tự triển khai.

## Learning outcomes

Sau 2 giờ lab, học viên cần có thể:

1. Thiết kế role rõ ràng cho nhiều agent.
2. Xây dựng shared state đủ thông tin cho handoff.
3. Thêm guardrail tối thiểu: max iterations, timeout, retry/fallback, validation.
4. Trace được luồng chạy và giải thích agent nào làm gì.
5. Benchmark single-agent vs multi-agent theo quality, latency, cost.

## Architecture mục tiêu

```text
User Query
   |
   v
Supervisor / Router
   |------> Researcher Agent  -> research_notes
   |------> Analyst Agent     -> analysis_notes
   |------> Writer Agent      -> final_answer
   |
   v
Trace + Benchmark Report
```

## Cấu trúc repo

```text
.
├── src/multi_agent_research_lab/
│   ├── agents/              # Agent interfaces + skeletons
│   ├── core/                # Config, state, schemas, errors
│   ├── graph/               # LangGraph workflow skeleton
│   ├── services/            # LLM, search, storage clients
│   ├── evaluation/          # Benchmark/evaluation skeleton
│   ├── observability/       # Logging/tracing hooks
│   └── cli.py               # CLI entrypoint
├── configs/                 # YAML configs for lab variants
├── docs/                    # Lab guide, rubric, design notes
├── tests/                   # Unit tests for skeleton behavior
├── notebooks/               # Optional notebook entrypoint
├── scripts/                 # Helper scripts
├── .env.example             # Environment variables template
├── pyproject.toml           # Python project config
├── Dockerfile               # Containerized dev/runtime
└── Makefile                 # Common commands
```

## Quickstart

### 1. Tạo môi trường

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e ".[dev,llm]"
cp .env.example .env
```

### 2. Cấu hình API keys

Mở `.env` và điền key cần thiết.

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
# optional
TAVILY_API_KEY=...
SERPER_API_KEY=...
```

### 3. Chạy smoke test

```bash
make test
python -m multi_agent_research_lab.cli --help
```

### 4. Chạy baseline skeleton

```bash
python -m multi_agent_research_lab.cli baseline \
  --query "Research GraphRAG state-of-the-art and write a 500-word summary"
```

Lệnh này gọi `LLMClient` và sẽ dùng OpenAI nếu có key hợp lệ. Nếu provider chưa sẵn sàng, baseline sẽ trả fallback response có kiểm soát để vẫn chứng minh được wiring của CLI và tracing.

Search layer của `Researcher` ưu tiên Tavily khi package và API key sẵn sàng, sau đó fallback sang Serper.dev, rồi mới dùng nguồn nội bộ nếu cả hai provider đều không khả dụng. LLM layer ưu tiên OpenAI và fallback sang Anthropic trước khi dùng local fallback response.

Benchmark cost hiện được ước lượng từ `metadata` của từng agent result, bao gồm LLM token cost và phần search cost ước lượng ở tầng `Researcher`, để report local có thể tự tính mà không phải query ngược lại từ Langfuse.

### 5. Chạy multi-agent

```bash
python -m multi_agent_research_lab.cli multi-agent \
  --query "Research GraphRAG state-of-the-art and write a 500-word summary"
```

Lệnh chạy full pipeline: `Supervisor → Researcher → Analyst → Critic → Writer`. Nếu Critic phát sinh `VERIFY:` query, workflow tự loop lại Researcher trước khi sang Writer. Kết quả trả về JSON đầy đủ gồm `route_history`, `final_answer`, `sources`, và `errors`.

### 6. Chạy benchmark

```bash
make benchmark
```

Chạy 5 preset queries so sánh baseline vs multi-agent, in metrics (latency, cost, quality, citation coverage) ra console. Kết quả thực tế nằm trong [`reports/benchmark_report.md`](reports/benchmark_report.md).

## Milestones trong 2 giờ lab

| Thời lượng | Milestone | File gợi ý |
|---:|---|---|
| 0-15' | Setup, chạy baseline skeleton | `cli.py`, `services/llm_client.py` |
| 15-45' | Build Supervisor / router | `agents/supervisor.py`, `graph/workflow.py` |
| 45-75' | Thêm Researcher, Analyst, Writer | `agents/*.py`, `core/state.py` |
| 75-95' | Trace + benchmark single vs multi | `observability/tracing.py`, `evaluation/benchmark.py` |
| 95-115' | Peer review theo rubric | `docs/peer_review_rubric.md` |
| 115-120' | Exit ticket | `docs/lab_guide.md` |

## Quy ước production trong repo

- Tách rõ `agents`, `services`, `core`, `graph`, `evaluation`, `observability`.
- Không hard-code API key trong code.
- Tất cả input/output chính dùng Pydantic schema.
- Có type hints, linting, formatting, unit test tối thiểu.
- Có logging/tracing hook ngay từ đầu.
- Không để agent chạy vô hạn: dùng `max_iterations`, `timeout_seconds`.
- Có benchmark report thay vì chỉ demo output đẹp.

## TODO chính cho học viên

Tìm trong code các marker:

```bash
grep -R "TODO(student)" -n src tests docs
```

Các phần học viên cần tự làm:

1. Implement LLM client.
2. Implement web/search client hoặc mock search source.
3. Implement routing decision trong Supervisor.
4. Implement từng worker agent.
5. Build LangGraph workflow.
6. Thêm tracing provider thật: LangSmith, Langfuse hoặc OpenTelemetry.
7. Viết benchmark report.

Toàn bộ pipeline đã được implement đầy đủ: LLMClient (OpenAI → Anthropic → local), SearchClient (Tavily → Serper → local), ResearcherAgent, AnalystAgent, CriticAgent (với VERIFY loop), WriterAgent (với inline citations), SupervisorAgent (deterministic router), LangGraph workflow, và Langfuse 3-level tracing.

Langfuse tracing tách `trace name` và `root span name` theo dạng `cli.multi_agent` / `run.cli.multi_agent` để list view trên Langfuse không bị lặp tên.

## Deliverables

Học viên nộp:

1. GitHub repo cá nhân.
2. Screenshot trace hoặc link trace.
3. `reports/benchmark_report.md` so sánh single vs multi-agent.
4. Một đoạn giải thích failure mode và cách fix.

## Workflow Diagrams

Các diagram SVG mô tả kiến trúc và luồng dữ liệu của hệ thống. Mở trực tiếp trong trình duyệt hoặc xem inline trong VS Code:

| Diagram | Mô tả |
|---|---|
| [System Overview](docs/diagrams/system_overview.svg) | LangGraph StateGraph 5 nodes, supervisor routing, VERIFY loop, 3-level tracing |
| [Sprint 1 – Baseline & Tracing](docs/diagrams/sprint_1_baseline_tracing.svg) | CLI baseline, LLMClient 3-tier fallback, Langfuse trace hierarchy |
| [Sprint 2 – Search & ResearcherAgent](docs/diagrams/sprint_2_search_researcher.svg) | SearchClient 3-tier (Tavily → Serper → local), ResearcherAgent.run(), metadata |
| [Sprint 3 – Analyst, Critic & State](docs/diagrams/sprint_3_analyst_critic_state.svg) | AnalystAgent, CriticAgent, guard clauses, VERIFY extraction, ResearchState fields |
| [Sprint 4 – Supervisor & LangGraph](docs/diagrams/sprint_4_supervisor_langgraph.svg) | MultiAgentWorkflow.build(), _determine_route(), guardrail, conditional_edges |
| [Sprint 5 – Writer, Benchmark & Report](docs/diagrams/sprint_5_writer_benchmark_report.svg) | WriterAgent, run_benchmark(), LLM-as-Judge, BenchmarkMetrics, markdown report |

## References

- Anthropic: Building effective agents — https://www.anthropic.com/engineering/building-effective-agents
- OpenAI Agents SDK orchestration/handoffs — https://developers.openai.com/api/docs/guides/agents/orchestration
- LangGraph concepts — https://langchain-ai.github.io/langgraph/concepts/
- LangSmith tracing — https://docs.smith.langchain.com/
- Langfuse tracing — https://langfuse.com/docs
