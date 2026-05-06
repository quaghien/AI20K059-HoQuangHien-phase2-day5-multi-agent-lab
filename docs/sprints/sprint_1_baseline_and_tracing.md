# Sprint 1: Baseline and Tracing

## Goal

Thiết lập nền cho toàn bộ lab:

- Implement `LLMClient.complete`
- Nối `baseline` CLI với OpenAI
- Instrument `Langfuse` ngay tại `LLMClient.complete`
- Có fallback rõ ràng khi thiếu API key hoặc provider lỗi

## Technical decisions locked in this sprint

- Dùng `OpenAI` làm provider chính cho baseline
- Nếu OpenAI fail hoặc thiếu key, fallback sang `Anthropic`, sau đó mới tới local fallback response
- Tất cả LLM call phải đi qua `LLMClient.complete`
- Trace dùng `Langfuse` và lưu đầy đủ:
  `system_prompt`, `user_prompt`, `response.content`, `model`, `input_tokens`, `output_tokens`, `cost_usd`
- Không dùng masking trong lab này
- Retry và timeout được đặt ở service layer, không nhét vào agent

## Implementation scope

- Implement `LLMResponse` flow thực tế trong `LLMClient.complete`
- Dùng settings từ `core/config.py`
- Thay baseline placeholder bằng flow gọi LLM thật hoặc fallback có kiểm soát
- Tạo helper tracing để mỗi LLM call sinh một `generation` trong Langfuse

## Primary files

- `src/multi_agent_research_lab/services/llm_client.py`
- `src/multi_agent_research_lab/observability/tracing.py`
- `src/multi_agent_research_lab/cli.py`

## Out of scope

- Multi-agent routing
- Search integration
- Benchmark scoring
- Writer/Analyst/Critic logic

## Acceptance criteria

- `python -m multi_agent_research_lab.cli baseline --query ...` trả về output thật, không còn placeholder mặc định
- Có fallback message có kiểm soát nếu thiếu `OPENAI_API_KEY` hoặc provider chính lỗi
- Langfuse trace cho mỗi LLM call hiển thị đủ prompt/completion và metadata chính
- Không agent nào gọi SDK OpenAI trực tiếp ngoài `LLMClient`

## Test plan

### Unit tests

- Test `LLMResponse` giữ đúng shape dữ liệu
- Test `LLMClient.complete` với mocked provider response
- Test helper tracing tạo được generation metadata như mong đợi

### Integration or workflow tests

- Test baseline command gọi được đường code không còn placeholder path
- Test baseline chạy qua `LLMClient` thay vì hard-code output

### Failure-path tests

- Thiếu `OPENAI_API_KEY` thì không crash vô nghĩa, phải fallback sang `Anthropic` hoặc local fallback
- Provider timeout hoặc provider error thì trả lỗi có kiểm soát
- Langfuse không sẵn sàng thì application vẫn chạy, chỉ mất trace

## Risks and fallback

- Rủi ro: API key chưa có hoặc provider quota lỗi
- Fallback: thử `Anthropic` trước, nếu vẫn không được thì trả baseline response có ghi rõ đang dùng fallback path
- Rủi ro: trace không flush kịp trong CLI ngắn
- Fallback: gọi flush rõ ràng ở cuối flow CLI hoặc service wrapper

## Deliverables

- `LLMClient.complete` hoạt động
- Baseline CLI dùng được
- Langfuse trace nhìn thấy prompt/completion cho baseline run

## Implementation notes after rollout

- Ưu tiên inject `client_factory` và `langfuse_client` vào `LLMClient` để unit test không phụ thuộc network
- OpenAI, Anthropic và Langfuse nên import theo runtime trong service/tracing layer để test suite vẫn chạy kể cả khi optional package chưa được cài
- `trace_run(...)` nên đặt tên root span khác với trace name, ví dụ `run.cli.baseline`, để Langfuse list view không trông như bị lặp hai dòng cùng tên
