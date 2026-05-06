# Sprint 2: Search and Researcher

## Goal

Xây lớp research đầu tiên cho workflow:

- Implement `SearchClient.search`
- Ưu tiên `Tavily` nếu có key
- Có fallback `Serper.dev`, rồi mới tới local fallback nếu provider ngoài không khả dụng
- Implement `ResearcherAgent.run`
- Chuẩn hóa `SourceDocument`, citation metadata, `research_notes`

## Technical decisions locked in this sprint

- Search provider chính là `Tavily`
- Nếu `Tavily` không khả dụng, fallback sang `Serper.dev`, rồi mới tới local/static source để sprint vẫn chạy được
- `Researcher` chỉ tìm nguồn, lọc nguồn, tạo notes và citation; không làm analysis
- `SourceDocument` là shape chuẩn cho handoff sang các agent sau

## Implementation scope

- Implement service search trả `list[SourceDocument]`
- Chuẩn hóa metadata nguồn đủ cho benchmark/citation
- `ResearcherAgent` dùng `SearchClient` để lấy sources
- `ResearcherAgent` dùng `LLMClient` để tóm tắt thành `research_notes`
- `ResearcherAgent` cũng phải hỗ trợ `verification_queries` từ `Critic` để bổ sung research trước khi sang `Writer`
- `ResearcherAgent` nên ghi `search_cost_usd`, `llm_cost_usd`, và `cost_usd` tổng vào `agent_results.metadata` để benchmark dùng lại

## Primary files

- `src/multi_agent_research_lab/services/search_client.py`
- `src/multi_agent_research_lab/agents/researcher.py`
- `src/multi_agent_research_lab/core/schemas.py`

## Out of scope

- So sánh quan điểm giữa nhiều nguồn ở mức analyst
- Final answer writing
- Routing graph đầy đủ

## Acceptance criteria

- `SearchClient.search` trả được danh sách `SourceDocument` hợp lệ
- `ResearcherAgent.run` cập nhật được `state.sources` và `state.research_notes`
- Fallback `Serper.dev` hoặc local search vẫn cho ra source usable khi provider chính lỗi
- Citation metadata đủ để các sprint sau dùng lại

## Test plan

### Unit tests

- Test `SearchClient.search` trả đúng list `SourceDocument`
- Test mỗi source có shape tối thiểu: `title`, `snippet`, optional `url`
- Test `ResearcherAgent` chỉ cập nhật field thuộc trách nhiệm của nó
- Test `ResearcherAgent` xử lý được `verification_queries` và append phần research bổ sung

### Integration or workflow tests

- Test `ResearcherAgent` chạy được với mock search + mock llm client
- Test state sau researcher có đủ dữ liệu cho analyst handoff

### Failure-path tests

- Không có `TAVILY_API_KEY` thì fallback `Serper.dev` hoặc local fallback vẫn hoạt động
- Search provider trả rỗng thì `Researcher` phải ghi lỗi hoặc note phù hợp
- LLM summary fail thì không được làm mất `sources` đã thu thập

## Risks and fallback

- Rủi ro: Tavily unavailable hoặc quota thấp
- Fallback: `Serper.dev`, nếu vẫn lỗi thì static search dataset hoặc mock sources cục bộ
- Rủi ro: nguồn quá nhiễu
- Fallback: giới hạn `max_results` và lọc lại bằng heuristic hoặc prompt

## Deliverables

- `SearchClient.search` có provider path và fallback path
- `ResearcherAgent.run` tạo được `sources` và `research_notes`
- Source format ổn định cho các sprint sau

## Implementation notes after rollout

- Ưu tiên fallback deterministic để test và benchmark dry run không phụ thuộc provider ngoài
- `ResearcherAgent` chỉ cập nhật `sources`, `research_notes`, `agent_results`, `trace`, `errors`; không đụng sang `analysis_notes` hay `final_answer`
- Search provider hiện đi theo thứ tự `Tavily -> Serper.dev -> local fallback`
- Khi có `verification_queries`, `ResearcherAgent` sẽ tìm thêm và append phần `Additional verification research` vào `research_notes`
