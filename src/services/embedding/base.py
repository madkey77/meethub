"""Embedding provider abstractions and orchestrator for multi-provider support."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Dict, Sequence

from src.config import settings
from src.services.llm.base import LLMProvider
from src.services.llm.factory import LLMProviderFactory
from src.utils.exceptions import ConfigurationError
from src.utils.logging import get_logger


@dataclass(slots=True)
class EmbeddingBatch:
    """Represents a batch of embedding vectors returned by a provider."""

    vectors: list[list[float]]
    model: str
    provider: str


class EmbeddingProvider(abc.ABC):
    """Abstract interface implemented by concrete embedding providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Canonical provider identifier (e.g., 'openai')."""

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Active embedding model name."""

    @abc.abstractmethod
    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        """Generate embeddings for the supplied text payloads."""


class LLMEmbeddingAdapter(EmbeddingProvider):
    """Adapter that exposes LLMProvider embedding capabilities via EmbeddingProvider."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        if llm_provider.embedding_model_name is None:
            raise ConfigurationError(
                "Selected LLM provider does not expose an embedding model",
                details={"provider": llm_provider.provider_name},
            )

        self._llm_provider = llm_provider

    @property
    def provider_name(self) -> str:
        return self._llm_provider.provider_name

    @property
    def model_name(self) -> str:
        return self._llm_provider.embedding_model_name or self._llm_provider.model_name

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(vectors=[], model=self.model_name, provider=self.provider_name)

        try:
            result = self._llm_provider.embed(texts)
        except NotImplementedError as exc:
            raise ConfigurationError(
                "LLM provider does not implement embedding support",
                details={"provider": self.provider_name},
            ) from exc
        return EmbeddingBatch(
            vectors=result.vectors,
            model=result.model or self.model_name,
            provider=result.provider or self.provider_name,
        )


class EmbeddingService:
    """Registry-oriented service that manages embedding providers."""

    def __init__(
        self,
        *,
        default_provider: str | None = None,
        factory: type[LLMProviderFactory] = LLMProviderFactory,
    ) -> None:
        self._factory = factory
        self._default_provider = (default_provider or settings.llm_provider_preference).lower()
        self._providers: Dict[str, EmbeddingProvider] = {}
        self._logger = get_logger(__name__).bind(service="embedding_service")

    def register_provider(self, name: str, provider: EmbeddingProvider) -> None:
        """Register an embedding provider instance for later use."""

        resolved = name.lower()
        self._providers[resolved] = provider
        self._logger.info("embedding.register_provider", provider=resolved)

    def get_provider(self, name: str | None = None) -> EmbeddingProvider:
        """Return an embedding provider, auto-instantiating when required."""

        resolved = (name or self._default_provider).lower()
        if resolved not in self._providers:
            llm_provider = self._factory.create(resolved)
            provider = LLMEmbeddingAdapter(llm_provider)
            self._providers[resolved] = provider
            self._logger.info(
                "embedding.provider_initialized",
                provider=resolved,
                model=provider.model_name,
            )
        return self._providers[resolved]

    def embed(self, texts: Sequence[str], *, provider_name: str | None = None) -> EmbeddingBatch:
        """Embed text payloads using the resolved provider."""

        provider = self.get_provider(provider_name)
        batch = provider.embed(texts)
        self._logger.debug(
            "embedding.embed",
            provider=provider.provider_name,
            model=provider.model_name,
            count=len(texts),
        )
        return batch

    def available_providers(self) -> list[str]:
        """List provider names currently registered/initialized."""

        return sorted(self._providers.keys())
