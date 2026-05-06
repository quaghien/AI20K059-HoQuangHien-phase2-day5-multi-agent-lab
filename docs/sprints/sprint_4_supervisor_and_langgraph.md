# Sprint 4: Supervisor and LangGraph

## Goal

Xây orchestration đầy đủ cho multi-agent workflow:

- Implement `SupervisorAgent.run` bằng deterministic state-based routing
- Chốt valid routes và stop condition
- Implement `MultiAgentWorkflow.build/run` với node `critic`
- Giữ route history đủ rõ để trace và debug

## Technical decisions locked in this sprint

- Workflow engine là `LangGraph`
- Valid routes gồm: `researcher`, `analyst`, `critic`, `writer`, `done`
- `Supervisor` dùng rule cứng theo shared state, không gọi LLM để chọn route
- Guardrails bắt buộc: `max_iterations`, timeout, failure fallback, route validation

## Implementation scope

- Implement logic quyết định agent tiếp theo từ state hiện tại
- Thêm stop condition khi state đã đủ hoặc khi guardrail bị chạm
- Build graph với các node `supervisor`, `researcher`, `analyst`, `critic`, `writer`
- Hỗ trợ vòng `Critic -> Researcher` khi có `verification_queries`
- Compile và chạy workflow, đồng bộ kết quả ngược về `ResearchState`

## Primary files

- `src/multi_agent_research_lab/agents/supervisor.py`
- `src/multi_agent_research_lab/graph/workflow.py`
- `src/multi_agent_research_lab/core/config.py`

## Out of scope

- Benchmark scoring chi tiết
- Judge report cuối
- UI hoặc notebook presentation

## Acceptance criteria

- CLI `multi-agent` chạy qua workflow thật thay vì ném `TODO`
- `Supervisor` chỉ trả route hợp lệ hoặc `done`
- Workflow đi được end-to-end với route history rõ ràng
- Nếu `Critic` yêu cầu verify thêm, workflow phải route quay lại `Researcher` đúng theo state
- Guardrail chặn được vòng lặp vô hạn và lỗi route

## Test plan

### Unit tests

- Test `SupervisorAgent` trả route hợp lệ theo từng state mẫu
- Test config guardrail như `max_iterations` được đọc đúng
- Test state có `verification_queries` thì supervisor route về `researcher`

### Integration or workflow tests

- Test workflow đi được end-to-end với mock agents hoặc mock services
- Test `route_history` phản ánh đúng chuỗi node đã đi qua
- Test workflow có thể đi qua chuỗi `researcher -> analyst -> critic -> researcher -> writer -> done`

### Failure-path tests

- Vượt `max_iterations` thì workflow dừng an toàn
- Agent fail ở giữa thì có fallback route hoặc error state rõ ràng
- Router trả route không hợp lệ thì bị chặn và xử lý được

## Risks and fallback

- Rủi ro: rule routing quá cứng cho một số case mơ hồ
- Fallback: mở rộng rule từ state hoặc thêm cờ trạng thái rõ hơn thay vì đưa quyết định cho LLM
- Rủi ro: LangGraph compile/run khó debug
- Fallback: log route history, state snapshot, và dùng node boundary rõ ràng

## Deliverables

- `SupervisorAgent.run` dùng được
- `MultiAgentWorkflow.build/run` hoạt động với `critic` node
- Multi-agent CLI chạy được end-to-end qua graph

## Implementation notes after rollout

- Sprint này dùng `LangGraph` thật với `StateGraph`, `START`, `END`, và conditional edges từ `supervisor`
- `Supervisor` là deterministic router theo state và guardrail, không phụ thuộc model để quyết định route
- `Supervisor` hiện là nơi giữ workflow policy; `LangGraph` thực thi các cạnh theo `state.next_agent`
- `Writer` chi tiết vẫn thuộc Sprint 5; ở Sprint 4 chỉ cần workflow và routing đủ sạch để gắn writer vào không phải sửa kiến trúc
