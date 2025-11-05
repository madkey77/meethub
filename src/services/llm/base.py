"""Abstract interface for Large Language Model providers."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence


@dataclass(slots=True)
class ChatMessage:
    """Lightweight chat message container shared across providers."""

    role: str
    content: str


@dataclass(slots=True)
class LLMGenerationResult:
    """Result payload returned by LLMProvider.generate."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str


@dataclass(slots=True)
class LLMEmbeddingResult:
    """Embedding payload returned by LLMProvider.embed."""

    vectors: list[list[float]]
    model: str
    provider: str


class SupportsTokenCounting(Protocol):
    """Protocol describing responses that expose token usage metadata."""

    @property
    def prompt_tokens(self) -> int:  # pragma: no cover - structural typing helper
        ...

    @property
    def completion_tokens(self) -> int:  # pragma: no cover - structural typing helper
        ...


class LLMProvider(abc.ABC):
    """Abstract base class implemented by concrete LLM providers."""

    def __init__(self, *, chat_model: str, embedding_model: str | None = None) -> None:
        self._chat_model = chat_model
        self._embedding_model = embedding_model

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Return canonical provider name (e.g., 'openai', 'anthropic')."""

    @property
    def model_name(self) -> str:
        """Return default chat model name for this provider."""

        return self._chat_model

    @property
    def embedding_model_name(self) -> str | None:
        """Return embedding model name if the provider supports embeddings."""

        return self._embedding_model

    @abc.abstractmethod
    def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMGenerationResult:
        """Generate text completion from a sequence of chat messages."""

    @abc.abstractmethod
    def embed(self, texts: Iterable[str]) -> LLMEmbeddingResult:
        """Compute embeddings for the supplied text payloads."""

    @abc.abstractmethod
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int = 0) -> float:
        """Estimate USD cost for the requested token usage."""
