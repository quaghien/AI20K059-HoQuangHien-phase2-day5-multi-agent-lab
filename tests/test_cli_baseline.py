from typer.testing import CliRunner

from multi_agent_research_lab.cli import app
from multi_agent_research_lab.services.llm_client import LLMResponse

runner = CliRunner()


def test_baseline_command_uses_llm_client(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class _FakeLLMClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args
            del kwargs

        def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            return LLMResponse(content="Real baseline output")

    monkeypatch.setattr("multi_agent_research_lab.cli.LLMClient", _FakeLLMClient)

    result = runner.invoke(app, ["baseline", "--query", "Explain multi-agent systems"])

    assert result.exit_code == 0
    assert "Real baseline output" in result.stdout
    assert "TODO(student)" not in result.stdout
    assert "Explain multi-agent systems" in captured["user_prompt"]
