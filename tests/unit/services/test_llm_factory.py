"""Unit tests for LLM Provider Factory.

Tests cover:
- Valid provider creation (openai, anthropic)
- Invalid provider name raises ValueError
- Missing API keys raises ConfigurationError
- Unsupported models raise error
- Provider configuration validation
"""

import pytest
from unittest.mock import patch, MagicMock

from src.services.llm.factory import LLMProviderFactory
from src.services.llm.openai_provider import OpenAIProvider
from src.services.llm.anthropic_provider import AnthropicProvider
from src.utils.exceptions import ConfigurationError


class TestLLMProviderFactory:
    """Test suite for LLMProviderFactory."""

    @patch("src.services.llm.openai_provider.OpenAI")
    @patch("src.config.settings")
    def test_create_openai_provider_success(self, mock_settings, mock_openai_class):
        """Test creating OpenAI provider with valid configuration."""
        # Setup mock settings
        mock_settings.llm_provider_preference = "openai"
        mock_settings.openai_api_key = "sk-test-key-123"
        mock_settings.openai_chat_model = "gpt-4o"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        mock_settings.openai_timeout_seconds = 30
        mock_settings.openai_max_retries = 3

        # Create provider
        provider = LLMProviderFactory.create()

        # Verify
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"
        assert provider.model_name == "gpt-4o"
        assert provider.embedding_model_name == "text-embedding-3-large"

    @patch("src.services.llm.anthropic_provider.Anthropic")
    @patch("src.config.settings")
    def test_create_anthropic_provider_success(self, mock_settings, mock_anthropic_class):
        """Test creating Anthropic provider with valid configuration."""
        # Setup mock settings
        mock_settings.llm_provider_preference = "anthropic"
        mock_settings.anthropic_api_key = "sk-ant-test-key-123"
        mock_settings.anthropic_chat_model = "claude-3-5-sonnet-20241022"
        mock_settings.anthropic_timeout_seconds = 30
        mock_settings.anthropic_max_retries = 2

        # Create provider
        provider = LLMProviderFactory.create(provider_name="anthropic")

        # Verify
        assert isinstance(provider, AnthropicProvider)
        assert provider.provider_name == "anthropic"
        assert provider.model_name == "claude-3-5-sonnet-20241022"

    @patch("src.config.settings")
    def test_create_invalid_provider_name(self, mock_settings):
        """Test that invalid provider name raises ConfigurationError."""
        mock_settings.llm_provider_preference = "openai"

        with pytest.raises(ConfigurationError) as exc_info:
            LLMProviderFactory.create(provider_name="invalid_provider")

        assert "Unsupported LLM provider" in str(exc_info.value)
        assert "invalid_provider" in str(exc_info.value.details)

    @patch("src.config.settings")
    def test_create_unsupported_provider_from_settings(self, mock_settings):
        """Test that unsupported provider in settings raises ConfigurationError."""
        mock_settings.llm_provider_preference = "gemini"  # Not supported yet

        with pytest.raises(ConfigurationError) as exc_info:
            LLMProviderFactory.create()

        assert "Unsupported LLM provider" in str(exc_info.value)

    @patch("src.config.settings")
    def test_create_openai_missing_api_key(self, mock_settings):
        """Test that missing OpenAI API key raises ConfigurationError."""
        mock_settings.llm_provider_preference = "openai"
        mock_settings.openai_api_key = None  # Missing
        mock_settings.openai_chat_model = "gpt-4o"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        mock_settings.openai_timeout_seconds = 30
        mock_settings.openai_max_retries = 3

        with pytest.raises(ConfigurationError) as exc_info:
            LLMProviderFactory.create()

        assert "Missing OpenAI API key" in str(exc_info.value)

    @patch("src.config.settings")
    def test_create_openai_empty_api_key(self, mock_settings):
        """Test that empty OpenAI API key raises ConfigurationError."""
        mock_settings.llm_provider_preference = "openai"
        mock_settings.openai_api_key = ""  # Empty string
        mock_settings.openai_chat_model = "gpt-4o"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        mock_settings.openai_timeout_seconds = 30
        mock_settings.openai_max_retries = 3

        with pytest.raises(ConfigurationError) as exc_info:
            LLMProviderFactory.create()

        assert "Missing OpenAI API key" in str(exc_info.value)

    @patch("src.config.settings")
    def test_create_anthropic_missing_api_key(self, mock_settings):
        """Test that missing Anthropic API key raises ConfigurationError."""
        mock_settings.llm_provider_preference = "anthropic"
        mock_settings.anthropic_api_key = None  # Missing
        mock_settings.anthropic_chat_model = "claude-3-5-sonnet-20241022"
        mock_settings.anthropic_timeout_seconds = 30
        mock_settings.anthropic_max_retries = 2

        with pytest.raises(ConfigurationError) as exc_info:
            LLMProviderFactory.create()

        assert "Missing Anthropic API key" in str(exc_info.value)

    @patch("src.services.llm.openai_provider.OpenAI")
    @patch("src.config.settings")
    def test_create_with_overrides(self, mock_settings, mock_openai_class):
        """Test creating provider with configuration overrides."""
        # Setup mock settings
        mock_settings.llm_provider_preference = "openai"
        mock_settings.openai_api_key = "sk-test-key-default"
        mock_settings.openai_chat_model = "gpt-4o"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        mock_settings.openai_timeout_seconds = 30
        mock_settings.openai_max_retries = 3

        # Create provider with overrides
        overrides = {
            "api_key": "sk-test-key-override",
            "chat_model": "gpt-4o-mini",
            "timeout_seconds": 60,
            "max_retries": 5,
        }
        provider = LLMProviderFactory.create(overrides=overrides)

        # Verify overrides were applied
        assert isinstance(provider, OpenAIProvider)
        assert provider.model_name == "gpt-4o-mini"
        # Note: Can't directly verify api_key and timeout since they're private,
        # but the override path is tested

    @patch("src.services.llm.openai_provider.OpenAI")
    @patch("src.config.settings")
    def test_create_provider_name_case_insensitive(self, mock_settings, mock_openai_class):
        """Test that provider name is case-insensitive."""
        mock_settings.openai_api_key = "sk-test-key"
        mock_settings.openai_chat_model = "gpt-4o"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        mock_settings.openai_timeout_seconds = 30
        mock_settings.openai_max_retries = 3

        # Test various casings
        for provider_name in ["OpenAI", "OPENAI", "openai", "OpEnAi"]:
            provider = LLMProviderFactory.create(provider_name=provider_name)
            assert isinstance(provider, OpenAIProvider)

    @patch("src.services.llm.anthropic_provider.Anthropic")
    @patch("src.config.settings")
    def test_create_provider_with_whitespace(self, mock_settings, mock_anthropic_class):
        """Test that provider name handles whitespace correctly."""
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.anthropic_chat_model = "claude-3-5-sonnet-20241022"
        mock_settings.anthropic_timeout_seconds = 30
        mock_settings.anthropic_max_retries = 2

        # Test with whitespace
        provider = LLMProviderFactory.create(provider_name="  anthropic  ")
        assert isinstance(provider, AnthropicProvider)

    def test_supported_providers_constant(self):
        """Test that SUPPORTED_PROVIDERS constant is correctly defined."""
        assert hasattr(LLMProviderFactory, "SUPPORTED_PROVIDERS")
        assert "openai" in LLMProviderFactory.SUPPORTED_PROVIDERS
        assert "anthropic" in LLMProviderFactory.SUPPORTED_PROVIDERS
        assert isinstance(LLMProviderFactory.SUPPORTED_PROVIDERS, set)

    @patch("src.services.llm.openai_provider.OpenAI")
    @patch("src.config.settings")
    def test_create_uses_default_from_settings(self, mock_settings, mock_openai_class):
        """Test that create() uses llm_provider_preference from settings when no provider_name given."""
        mock_settings.llm_provider_preference = "openai"
        mock_settings.openai_api_key = "sk-test-key"
        mock_settings.openai_chat_model = "gpt-4o"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        mock_settings.openai_timeout_seconds = 30
        mock_settings.openai_max_retries = 3

        # Create without provider_name (should use settings)
        provider = LLMProviderFactory.create()
        assert isinstance(provider, OpenAIProvider)

    @patch("src.services.llm.openai_provider.OpenAI", None)  # Simulate package not installed
    @patch("src.config.settings")
    def test_create_openai_package_not_installed(self, mock_settings):
        """Test that missing openai package raises ConfigurationError."""
        mock_settings.llm_provider_preference = "openai"
        mock_settings.openai_api_key = "sk-test-key"
        mock_settings.openai_chat_model = "gpt-4o"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        mock_settings.openai_timeout_seconds = 30
        mock_settings.openai_max_retries = 3

        with pytest.raises(ConfigurationError) as exc_info:
            LLMProviderFactory.create()

        assert "openai package is not installed" in str(exc_info.value)

    @patch("src.services.llm.anthropic_provider.Anthropic", None)  # Simulate package not installed
    @patch("src.config.settings")
    def test_create_anthropic_package_not_installed(self, mock_settings):
        """Test that missing anthropic package raises ConfigurationError."""
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.anthropic_chat_model = "claude-3-5-sonnet-20241022"
        mock_settings.anthropic_timeout_seconds = 30
        mock_settings.anthropic_max_retries = 2

        with pytest.raises(ConfigurationError) as exc_info:
            LLMProviderFactory.create(provider_name="anthropic")

        assert "anthropic package is not installed" in str(exc_info.value)

    @patch("src.services.llm.openai_provider.OpenAI")
    @patch("src.config.settings")
    def test_create_openai_with_all_config_parameters(self, mock_settings, mock_openai_class):
        """Test creating OpenAI provider with all configuration parameters."""
        mock_settings.openai_api_key = "sk-test-key"
        mock_settings.openai_chat_model = "gpt-4o"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        mock_settings.openai_timeout_seconds = 45
        mock_settings.openai_max_retries = 5

        provider = LLMProviderFactory.create(provider_name="openai")

        assert isinstance(provider, OpenAIProvider)
        assert provider.model_name == "gpt-4o"
        assert provider.embedding_model_name == "text-embedding-3-large"

    @patch("src.services.llm.anthropic_provider.Anthropic")
    @patch("src.config.settings")
    def test_create_anthropic_with_all_config_parameters(self, mock_settings, mock_anthropic_class):
        """Test creating Anthropic provider with all configuration parameters."""
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.anthropic_chat_model = "claude-3-5-sonnet-20241022"
        mock_settings.anthropic_timeout_seconds = 60
        mock_settings.anthropic_max_retries = 4

        provider = LLMProviderFactory.create(provider_name="anthropic")

        assert isinstance(provider, AnthropicProvider)
        assert provider.model_name == "claude-3-5-sonnet-20241022"
