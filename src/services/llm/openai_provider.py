"""OpenAI implementation of the LLMProvider interface."""

from __future__ import annotations

import time
from typing import Iterable, Sequence

try:
    from openai import OpenAI
    from openai.error import OpenAIError
except ImportError:  # pragma: no cover - handled during runtime configuration validation
    OpenAI = None
    OpenAIError = Exception

from src.services.llm.base import ChatMessage, LLMEmbeddingResult, LLMGenerationResult, LLMProvider
from src.utils.exceptions import ConfigurationError


class OpenAIProvider(LLMProvider):
    """Concrete LLM provider backed by OpenAI's GPT family."""

    INPUT_COST_PER_MILLION = 5.0
    OUTPUT_COST_PER_MILLION = 15.0

    def __init__(
        self,
        *,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.5,
    ) -> None:
        if not api_key:
            raise ConfigurationError("Missing OpenAI API key", details={"env": "OPENAI_API_KEY"})
        if OpenAI is None:
            raise ConfigurationError(
                "openai package is not installed",
                details={"hint": "Run 'pip install openai' inside the project environment."},
            )

        super().__init__(chat_model=chat_model, embedding_model=embedding_model)
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)

    @property
    def provider_name(self) -> str:
        return "openai"

    def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMGenerationResult:
        openai_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
        ]

        def _invoke_chat() -> LLMGenerationResult:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            message = response.choices[0].message.content or ""
            usage = response.usage
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            return LLMGenerationResult(
                content=message,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=self.model_name,
                provider=self.provider_name,
            )

        return self._run_with_retries(_invoke_chat)

    def embed(self, texts: Iterable[str]) -> LLMEmbeddingResult:
        payload = list(texts)
        if not payload:
            return LLMEmbeddingResult(vectors=[], model=self.embedding_model_name or "", provider=self.provider_name)

        def _invoke_embeddings() -> LLMEmbeddingResult:
            response = self._client.embeddings.create(
                model=self.embedding_model_name,
                input=payload,
            )
            vectors = [data.embedding for data in response.data]
            return LLMEmbeddingResult(
                vectors=vectors,
                model=self.embedding_model_name or "",
                provider=self.provider_name,
            )

        return self._run_with_retries(_invoke_embeddings)

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int = 0) -> float:
        prompt_cost = (prompt_tokens / 1_000_000) * self.INPUT_COST_PER_MILLION
        completion_cost = (completion_tokens / 1_000_000) * self.OUTPUT_COST_PER_MILLION
        return prompt_cost + completion_cost

    def _run_with_retries(self, func):
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return func()
            except OpenAIError as exc:  # pragma: no cover - network dependent
                last_error = exc
                if attempt >= self._max_retries:
                    raise
                time.sleep(self._retry_backoff_seconds * attempt)
        if last_error:  # pragma: no cover - safety net
            raise last_error
        raise RuntimeError("Retry loop exited without result")
