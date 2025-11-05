"""Factory for constructing configured LLM provider instances."""

from __future__ import annotations

from typing import Any

from src.config import settings
from src.services.llm.anthropic_provider import AnthropicProvider
from src.services.llm.base import LLMProvider
from src.services.llm.openai_provider import OpenAIProvider
from src.utils.exceptions import ConfigurationError


class LLMProviderFactory:
    """Factory helpers for instantiating LLM providers from configuration."""

    SUPPORTED_PROVIDERS = {"openai", "anthropic"}

    @classmethod
    def create(
        cls,
        provider_name: str | None = None,
        *,
        overrides: dict[str, Any] | None = None,
    ) -> LLMProvider:
        """Create an LLM provider using environment configuration.

        Args:
            provider_name: Optional provider override. Defaults to LLM_PROVIDER_PREFERENCE.
            overrides: Optional keyword overrides for provider-specific parameters.
        """

        resolved_provider = (provider_name or settings.llm_provider_preference).strip().lower()
        if resolved_provider not in cls.SUPPORTED_PROVIDERS:
            raise ConfigurationError(
                "Unsupported LLM provider",
                details={
                    "requested": provider_name,
                    "supported": sorted(cls.SUPPORTED_PROVIDERS),
                },
            )

        config_overrides = overrides or {}

        if resolved_provider == "openai":
            api_key = config_overrides.get("api_key", settings.openai_api_key)
            chat_model = config_overrides.get("chat_model", settings.openai_chat_model)
            embedding_model = config_overrides.get(
                "embedding_model",
                settings.openai_embedding_model,
            )
            timeout = int(config_overrides.get("timeout_seconds", settings.openai_timeout_seconds))
            max_retries = int(config_overrides.get("max_retries", settings.openai_max_retries))

            return OpenAIProvider(
                api_key=api_key,
                chat_model=chat_model,
                embedding_model=embedding_model,
                timeout_seconds=timeout,
                max_retries=max_retries,
            )

        if resolved_provider == "anthropic":
            api_key = config_overrides.get("api_key", settings.anthropic_api_key)
            chat_model = config_overrides.get("chat_model", settings.anthropic_chat_model)
            timeout = int(config_overrides.get("timeout_seconds", settings.anthropic_timeout_seconds))
            max_retries = int(config_overrides.get("max_retries", settings.anthropic_max_retries))

            return AnthropicProvider(
                api_key=api_key,
                chat_model=chat_model,
                timeout_seconds=timeout,
                max_retries=max_retries,
            )

        raise ConfigurationError("Unhandled LLM provider", details={"provider": resolved_provider})
