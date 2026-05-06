from types import SimpleNamespace

from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse


class _FakeResponsesAPI:
    def __init__(self, raw_response: object) -> None:
        self._raw_response = raw_response

    def create(self, **_: object) -> object:
        return self._raw_response


class _FakeOpenAIClient:
    def __init__(self, raw_response: object) -> None:
        self.responses = _FakeResponsesAPI(raw_response)


class _FailingOpenAIClient:
    def __init__(self) -> None:
        self.responses = self

    def create(self, **_: object) -> object:
        raise RuntimeError("openai failed")


class _FakeAnthropicMessagesAPI:
    def __init__(self, raw_response: object) -> None:
        self._raw_response = raw_response

    def create(self, **_: object) -> object:
        return self._raw_response


class _FakeAnthropicClient:
    def __init__(self, raw_response: object) -> None:
        self.messages = _FakeAnthropicMessagesAPI(raw_response)


def test_llm_response_shape() -> None:
    response = LLMResponse(content="hello", input_tokens=1, output_tokens=2, cost_usd=0.001)
    assert response.content == "hello"
    assert response.input_tokens == 1
    assert response.output_tokens == 2
    assert response.cost_usd == 0.001


def test_complete_returns_provider_response() -> None:
    raw_response = SimpleNamespace(
        output_text="Provider answer",
        usage=SimpleNamespace(input_tokens=12, output_tokens=7),
    )
    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-test",
        LANGFUSE_PUBLIC_KEY=None,
        LANGFUSE_SECRET_KEY=None,
    )
    client = LLMClient(
        settings=settings,
        openai_client_factory=lambda: _FakeOpenAIClient(raw_response),
        langfuse_client=None,
    )

    response = client.complete("system", "user")

    assert response.content == "Provider answer"
    assert response.input_tokens == 12
    assert response.output_tokens == 7
    assert response.cost_usd is not None


def test_complete_falls_back_without_api_key() -> None:
    settings = Settings(
        OPENAI_API_KEY=None,
        ANTHROPIC_API_KEY=None,
        LANGFUSE_PUBLIC_KEY=None,
        LANGFUSE_SECRET_KEY=None,
    )
    client = LLMClient(settings=settings, langfuse_client=None)

    response = client.complete("system", "user")

    assert "Fallback baseline response." in response.content
    assert "failed" in response.content.lower()


def test_complete_falls_back_to_anthropic_when_openai_fails() -> None:
    raw_response = SimpleNamespace(
        content=[SimpleNamespace(text="Anthropic fallback answer")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=6),
    )
    settings = Settings(
        OPENAI_API_KEY="openai-key",
        ANTHROPIC_API_KEY="anthropic-key",
        LANGFUSE_PUBLIC_KEY=None,
        LANGFUSE_SECRET_KEY=None,
    )
    client = LLMClient(
        settings=settings,
        openai_client_factory=lambda: _FailingOpenAIClient(),
        anthropic_client_factory=lambda: _FakeAnthropicClient(raw_response),
        langfuse_client=None,
    )

    response = client.complete("system", "user")

    assert response.content == "Anthropic fallback answer"
