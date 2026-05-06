# Sprint 3: Analyst, Critic, and State

## Goal

Hoàn thiện tầng reasoning trung gian trước khi viết final answer:

- Mở rộng `ResearchState` vừa đủ cho handoff
- Implement `AnalystAgent.run`
- Implement `CriticAgent.run`
- Giữ ranh giới trách nhiệm rõ ràng giữa phân tích và phản biện

## Technical decisions locked in this sprint

- `Critic` là agent bắt buộc trong flow chính
- `Critic` đặt sau `Analyst` và chỉ đọc `analysis_notes`, không đọc `final_answer`
- `ResearchState` giữ tối giản nhưng phải đủ route/debug/handoff
- Telemetry chi tiết vẫn ưu tiên đọc từ Langfuse và benchmark module, không dồn hết vào state

## Implementation scope

- Bổ sung các field cần thiết như `critic_notes`, `next_agent`, `status`, `judge_score` hoặc equivalent
- Bổ sung `verification_queries` để `Critic` có thể yêu cầu research bổ sung
- `AnalystAgent` chuyển `research_notes` thành `analysis_notes`
- `CriticAgent` review `analysis_notes` để chỉ ra unsupported claims, thiếu bằng chứng, hoặc mâu thuẫn
- Giữ `agent_results`, `trace`, `errors` nhất quán khi qua nhiều agent

## Primary files

- `src/multi_agent_research_lab/core/state.py`
- `src/multi_agent_research_lab/agents/analyst.py`
- `src/multi_agent_research_lab/agents/critic.py`

## Out of scope

- Final answer rendering
- Supervisor routing logic
- Benchmark and report generation

## Acceptance criteria

- State có đủ dữ liệu để đi từ `Researcher -> Analyst -> Critic` mà không mất context
- `AnalystAgent.run` tạo được `analysis_notes`
- `CriticAgent.run` tạo được `critic_notes` hoặc equivalent usable cho Writer
- Nếu cần xác minh thêm, `CriticAgent.run` phải sinh được `verification_queries` usable cho `Researcher`
- Không agent nào ghi đè sai field của agent khác

## Test plan

### Unit tests

- Test `ResearchState` với các field mới và default hợp lệ
- Test `AnalystAgent` tạo `analysis_notes`
- Test `CriticAgent` thêm feedback mà không phá `sources`, `research_notes`, `analysis_notes`
- Test parser `VERIFY:` chuyển đúng sang `verification_queries`

### Integration or workflow tests

- Test handoff state giữa `Researcher -> Analyst -> Critic`
- Test `agent_results` và `trace` được nối thêm đúng thứ tự

### Failure-path tests

- Thiếu `research_notes` thì `Analyst` phải fail có kiểm soát
- Thiếu `analysis_notes` thì `Critic` phải fail có kiểm soát
- Nếu critic phát hiện phân tích yếu, state phải giữ lại feedback thay vì silently pass

## Risks and fallback

- Rủi ro: state phình to quá nhanh
- Fallback: chỉ thêm field phục vụ handoff thực sự cần thiết
- Rủi ro: `Analyst` và `Critic` overlap trách nhiệm
- Fallback: quy ước rõ `Analyst` tạo insight, `Critic` phản biện insight

## Deliverables

- `ResearchState` mở rộng đủ dùng
- `AnalystAgent.run` và `CriticAgent.run` hoạt động
- Handoff giữa ba tầng reasoning rõ ràng, dễ debug

## Implementation notes after rollout

- `Analyst` và `Critic` hiện fail bằng `ValidationError` nếu thiếu input bắt buộc, đồng thời ghi lỗi vào `state.errors`
- `status` và `next_agent` đã đủ để sprint sau dùng trong supervisor/router mà chưa cần state machine quá phức tạp
- `Critic` có thể phát sinh `VERIFY:` queries để yêu cầu `Researcher` tìm thêm hoặc xác minh thông tin trước khi sang `Writer`
- Nếu `Critic` tạo `verification_queries`, trạng thái hiện tại phải đủ rõ để sprint sau route quay lại `Researcher`
