"""Anthropic implementation of the LLMProvider interface."""

from __future__ import annotations

import time
from typing import Iterable, Sequence

try:
    from anthropic import Anthropic, APIError as AnthropicAPIError
except ImportError:  # pragma: no cover - handled by factory validation
    Anthropic = None
    AnthropicAPIError = Exception

from src.services.llm.base import ChatMessage, LLMEmbeddingResult, LLMGenerationResult, LLMProvider
from src.utils.exceptions import ConfigurationError


class AnthropicProvider(LLMProvider):
    """Concrete LLM provider backed by Anthropic Claude models."""

    INPUT_COST_PER_MILLION = 3.0
    OUTPUT_COST_PER_MILLION = 15.0

    def __init__(
        self,
        *,
        api_key: str,
        chat_model: str,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        retry_backoff_seconds: float = 60.0,
    ) -> None:
        if not api_key:
            raise ConfigurationError("Missing Anthropic API key", details={"env": "ANTHROPIC_API_KEY"})
        if Anthropic is None:
            raise ConfigurationError(
                "anthropic package is not installed",
                details={"hint": "Run 'pip install anthropic' inside the project environment."},
            )

        super().__init__(chat_model=chat_model)
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._client = Anthropic(api_key=api_key, timeout=timeout_seconds)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMGenerationResult:
        system_prompt: str | None = None
        converted_messages: list[dict[str, str]] = []

        for message in messages:
            role = message.role.lower()
            if role == "system":
                system_prompt = (
                    message.content
                    if system_prompt is None
                    else f"{system_prompt}\n{message.content}"
                )
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            converted_messages.append({"role": role, "content": message.content})

        def _invoke_chat() -> LLMGenerationResult:
            response = self._client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens or 1024,
                temperature=temperature,
                system=system_prompt,
                messages=converted_messages,
            )
            text_parts = [part.text for part in response.content if hasattr(part, "text")]
            combined_content = "".join(text_parts)
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "output_tokens", 0) if usage else 0
            return LLMGenerationResult(
                content=combined_content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=self.model_name,
                provider=self.provider_name,
            )

        return self._run_with_retries(_invoke_chat)

    def embed(self, texts: Iterable[str]) -> LLMEmbeddingResult:  # pragma: no cover - not supported yet
        raise NotImplementedError("Anthropic provider does not currently support embeddings")

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int = 0) -> float:
        prompt_cost = (prompt_tokens / 1_000_000) * self.INPUT_COST_PER_MILLION
        completion_cost = (completion_tokens / 1_000_000) * self.OUTPUT_COST_PER_MILLION
        return prompt_cost + completion_cost

    def _run_with_retries(self, func):
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return func()
            except AnthropicAPIError as exc:  # pragma: no cover - network dependent
                last_error = exc
                if attempt >= self._max_retries:
                    raise
                time.sleep(self._retry_backoff_seconds * attempt)
        if last_error:  # pragma: no cover - safety net
            raise last_error
        raise RuntimeError("Retry loop exited without result")
