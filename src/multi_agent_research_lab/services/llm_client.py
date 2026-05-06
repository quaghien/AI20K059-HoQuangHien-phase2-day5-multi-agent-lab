"""LLM client abstraction.

Production note: agents should depend on this interface instead of importing an SDK directly.
"""

from dataclasses import dataclass
import logging
from typing import Any, Callable

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.observability.tracing import flush_traces, get_langfuse_client, trace_generation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class LLMClient:
    """Provider-agnostic LLM client with OpenAI primary and Anthropic fallback."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        openai_client_factory: Callable[[], Any] | None = None,
        anthropic_client_factory: Callable[[], Any] | None = None,
        langfuse_client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._openai_client_factory = openai_client_factory or self._build_openai_client
        self._anthropic_client_factory = anthropic_client_factory or self._build_anthropic_client
        self._langfuse_client = langfuse_client if langfuse_client is not None else get_langfuse_client(self.settings)

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return a model completion with tracing and fallback behavior."""

        input_payload = {"system_prompt": system_prompt, "user_prompt": user_prompt}
        with trace_generation(
            "llm.complete",
            model=self.settings.openai_model,
            input_payload=input_payload,
            metadata={"provider_order": ["openai", "anthropic", "local_fallback"]},
            langfuse_client=self._langfuse_client,
        ) as generation:
            try:
                response = self._complete_with_openai(system_prompt, user_prompt)
                generation["metadata"]["provider_used"] = "openai"
                generation["output"] = response.content
                generation["usage"] = {"input": response.input_tokens, "output": response.output_tokens}
                generation["cost_usd"] = response.cost_usd
                return response
            except Exception as openai_exc:
                logger.exception("OpenAI completion failed; trying Anthropic fallback.")
                generation["metadata"]["openai_fallback_reason"] = str(openai_exc)

            try:
                response = self._complete_with_anthropic(system_prompt, user_prompt)
                generation["metadata"]["provider_used"] = "anthropic"
                generation["output"] = response.content
                generation["usage"] = {"input": response.input_tokens, "output": response.output_tokens}
                generation["cost_usd"] = response.cost_usd
                return response
            except Exception as anthropic_exc:
                logger.exception("Anthropic completion failed; returning local fallback response.")
                generation["metadata"]["anthropic_fallback_reason"] = str(anthropic_exc)
                response = self._fallback_response(
                    "Both OpenAI and Anthropic provider calls failed. Returning local fallback response."
                )
                generation["metadata"]["provider_used"] = "local_fallback"
                generation["output"] = response.content
                return response
            finally:
                flush_traces(self._langfuse_client)

    def _complete_with_openai(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        if not self.settings.openai_api_key:
            raise RuntimeError("OpenAI API key is not configured.")

        client = self._openai_client_factory()
        raw_response = client.responses.create(
            model=self.settings.openai_model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=self.settings.timeout_seconds,
        )
        return self._build_openai_response(raw_response)

    def _complete_with_anthropic(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        if not self.settings.anthropic_api_key:
            raise RuntimeError("Anthropic API key is not configured.")

        client = self._anthropic_client_factory()
        raw_response = client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=self.settings.timeout_seconds,
        )
        return self._build_anthropic_response(raw_response)

    def _build_openai_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI package is not installed.") from exc
        return OpenAI(api_key=self.settings.openai_api_key)

    def _build_anthropic_client(self) -> Any:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("Anthropic package is not installed.") from exc
        return Anthropic(api_key=self.settings.anthropic_api_key)

    def _build_openai_response(self, raw_response: Any) -> LLMResponse:
        usage = getattr(raw_response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        if input_tokens is None:
            input_tokens = getattr(usage, "prompt_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        if output_tokens is None:
            output_tokens = getattr(usage, "completion_tokens", None)
        return LLMResponse(
            content=self._extract_openai_content(raw_response),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._estimate_cost(input_tokens, output_tokens),
        )

    def _build_anthropic_response(self, raw_response: Any) -> LLMResponse:
        usage = getattr(raw_response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        return LLMResponse(
            content=self._extract_anthropic_content(raw_response),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._estimate_cost(input_tokens, output_tokens),
        )

    def _extract_openai_content(self, raw_response: Any) -> str:
        output_text = getattr(raw_response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        output = getattr(raw_response, "output", None)
        if isinstance(output, list):
            text_chunks: list[str] = []
            for item in output:
                content = getattr(item, "content", None)
                if isinstance(content, list):
                    for part in content:
                        text_value = getattr(part, "text", None)
                        if isinstance(text_value, str) and text_value.strip():
                            text_chunks.append(text_value.strip())
            if text_chunks:
                return "\n".join(text_chunks)
        return "Model returned no textual output."

    def _extract_anthropic_content(self, raw_response: Any) -> str:
        content = getattr(raw_response, "content", None)
        if isinstance(content, list):
            text_chunks: list[str] = []
            for part in content:
                text_value = getattr(part, "text", None)
                if isinstance(text_value, str) and text_value.strip():
                    text_chunks.append(text_value.strip())
            if text_chunks:
                return "\n".join(text_chunks)
        return "Model returned no textual output."

    def _estimate_cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if input_tokens is None and output_tokens is None:
            return None
        prompt_tokens = input_tokens or 0
        completion_tokens = output_tokens or 0
        return round((prompt_tokens * 0.05 + completion_tokens * 0.40) / 1_000_000, 6)

    def _fallback_response(self, reason: str) -> LLMResponse:
        return LLMResponse(
            content=(
                "Fallback baseline response.\n\n"
                f"Reason: {reason}\n"
                "The baseline path is wired correctly, but the real provider call was not used for this run."
            )
        )
