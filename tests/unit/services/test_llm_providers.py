"""Unit tests for LLM Provider implementations (OpenAI and Anthropic).

Tests cover:
- generate() method with mocked API calls
- embed() method with mocked embeddings
- estimate_cost() calculation accuracy
- provider_name and model_name properties
- Error handling for invalid configuration
- Retry logic on API failures
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from typing import Any

from src.services.llm.base import ChatMessage, LLMGenerationResult, LLMEmbeddingResult
from src.services.llm.openai_provider import OpenAIProvider
from src.services.llm.anthropic_provider import AnthropicProvider
from src.utils.exceptions import ConfigurationError


class TestOpenAIProvider:
    """Test suite for OpenAIProvider."""

    def test_initialization_success(self):
        """Test successful initialization with valid API key."""
        with patch("src.services.llm.openai_provider.OpenAI") as mock_openai_class:
            provider = OpenAIProvider(
                api_key="sk-test-key",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
            )

            assert provider.provider_name == "openai"
            assert provider.model_name == "gpt-4o"
            assert provider.embedding_model_name == "text-embedding-3-large"
            mock_openai_class.assert_called_once()

    def test_initialization_missing_api_key(self):
        """Test that missing API key raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            OpenAIProvider(
                api_key="",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
            )

        assert "Missing OpenAI API key" in str(exc_info.value)

    def test_initialization_package_not_installed(self):
        """Test that missing openai package raises ConfigurationError."""
        with patch("src.services.llm.openai_provider.OpenAI", None):
            with pytest.raises(ConfigurationError) as exc_info:
                OpenAIProvider(
                    api_key="sk-test-key",
                    chat_model="gpt-4o",
                    embedding_model="text-embedding-3-large",
                )

            assert "openai package is not installed" in str(exc_info.value)

    def test_generate_success(self):
        """Test successful text generation."""
        with patch("src.services.llm.openai_provider.OpenAI") as mock_openai_class:
            # Setup mock response
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Generated response text"
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20

            mock_client.chat.completions.create.return_value = mock_response

            # Create provider and generate
            provider = OpenAIProvider(
                api_key="sk-test-key",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
            )

            messages = [
                ChatMessage(role="system", content="You are a helpful assistant."),
                ChatMessage(role="user", content="Hello!"),
            ]

            result = provider.generate(messages, temperature=0.7, max_tokens=100)

            # Verify
            assert isinstance(result, LLMGenerationResult)
            assert result.content == "Generated response text"
            assert result.prompt_tokens == 10
            assert result.completion_tokens == 20
            assert result.model == "gpt-4o"
            assert result.provider == "openai"

            # Verify API was called correctly
            mock_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "gpt-4o"
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 100

    def test_generate_with_none_content(self):
        """Test generation when API returns None content."""
        with patch("src.services.llm.openai_provider.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = None  # API can return None
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 0

            mock_client.chat.completions.create.return_value = mock_response

            provider = OpenAIProvider(
                api_key="sk-test-key",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
            )

            messages = [ChatMessage(role="user", content="Hello!")]
            result = provider.generate(messages)

            assert result.content == ""  # Should convert None to empty string

    def test_embed_success(self):
        """Test successful embedding generation."""
        with patch("src.services.llm.openai_provider.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            # Setup mock embedding response
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[0.1, 0.2, 0.3]),
                MagicMock(embedding=[0.4, 0.5, 0.6]),
            ]

            mock_client.embeddings.create.return_value = mock_response

            provider = OpenAIProvider(
                api_key="sk-test-key",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
            )

            texts = ["First text", "Second text"]
            result = provider.embed(texts)

            # Verify
            assert isinstance(result, LLMEmbeddingResult)
            assert len(result.vectors) == 2
            assert result.vectors[0] == [0.1, 0.2, 0.3]
            assert result.vectors[1] == [0.4, 0.5, 0.6]
            assert result.model == "text-embedding-3-large"
            assert result.provider == "openai"

            # Verify API call
            mock_client.embeddings.create.assert_called_once_with(
                model="text-embedding-3-large",
                input=["First text", "Second text"],
            )

    def test_embed_empty_list(self):
        """Test embedding with empty text list."""
        with patch("src.services.llm.openai_provider.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            provider = OpenAIProvider(
                api_key="sk-test-key",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
            )

            result = provider.embed([])

            # Should return empty result without API call
            assert len(result.vectors) == 0
            mock_client.embeddings.create.assert_not_called()

    def test_estimate_cost(self):
        """Test cost estimation calculation."""
        with patch("src.services.llm.openai_provider.OpenAI"):
            provider = OpenAIProvider(
                api_key="sk-test-key",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
            )

            # Test with example token counts
            cost = provider.estimate_cost(prompt_tokens=1_000_000, completion_tokens=500_000)

            # OpenAI pricing: $5 per 1M input, $15 per 1M output
            expected_cost = (1_000_000 / 1_000_000 * 5.0) + (500_000 / 1_000_000 * 15.0)
            assert cost == expected_cost
            assert cost == 12.5  # 5.0 + 7.5

    def test_estimate_cost_only_prompt(self):
        """Test cost estimation with only prompt tokens."""
        with patch("src.services.llm.openai_provider.OpenAI"):
            provider = OpenAIProvider(
                api_key="sk-test-key",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
            )

            cost = provider.estimate_cost(prompt_tokens=100_000, completion_tokens=0)

            expected_cost = 100_000 / 1_000_000 * 5.0
            assert cost == expected_cost
            assert cost == 0.5

    def test_retry_logic_on_api_error(self):
        """Test retry logic when API fails."""
        with patch("src.services.llm.openai_provider.OpenAI") as mock_openai_class:
            with patch("src.services.llm.openai_provider.OpenAIError", Exception):
                mock_client = MagicMock()
                mock_openai_class.return_value = mock_client

                # Simulate API failure then success
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Success after retry"
                mock_response.usage.prompt_tokens = 10
                mock_response.usage.completion_tokens = 5

                from src.services.llm.openai_provider import OpenAIError
                mock_client.chat.completions.create.side_effect = [
                    OpenAIError("API Error"),
                    mock_response,
                ]

                provider = OpenAIProvider(
                    api_key="sk-test-key",
                    chat_model="gpt-4o",
                    embedding_model="text-embedding-3-large",
                    max_retries=3,
                    retry_backoff_seconds=0.01,  # Fast retry for testing
                )

                messages = [ChatMessage(role="user", content="Test")]

                with patch("time.sleep"):  # Mock sleep to speed up test
                    result = provider.generate(messages)

                assert result.content == "Success after retry"
                assert mock_client.chat.completions.create.call_count == 2

    def test_retry_exhausted_raises_error(self):
        """Test that exhausting retries raises the original error."""
        with patch("src.services.llm.openai_provider.OpenAI") as mock_openai_class:
            from src.services.llm.openai_provider import OpenAIError

            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            # Always fail
            mock_client.chat.completions.create.side_effect = OpenAIError("Persistent error")

            provider = OpenAIProvider(
                api_key="sk-test-key",
                chat_model="gpt-4o",
                embedding_model="text-embedding-3-large",
                max_retries=2,
                retry_backoff_seconds=0.01,
            )

            messages = [ChatMessage(role="user", content="Test")]

            with patch("time.sleep"):
                with pytest.raises(OpenAIError):
                    provider.generate(messages)

            # Should have tried max_retries times
            assert mock_client.chat.completions.create.call_count == 2


class TestAnthropicProvider:
    """Test suite for AnthropicProvider."""

    def test_initialization_success(self):
        """Test successful initialization with valid API key."""
        with patch("src.services.llm.anthropic_provider.Anthropic") as mock_anthropic_class:
            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
            )

            assert provider.provider_name == "anthropic"
            assert provider.model_name == "claude-3-5-sonnet-20241022"
            mock_anthropic_class.assert_called_once()

    def test_initialization_missing_api_key(self):
        """Test that missing API key raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            AnthropicProvider(
                api_key="",
                chat_model="claude-3-5-sonnet-20241022",
            )

        assert "Missing Anthropic API key" in str(exc_info.value)

    def test_initialization_package_not_installed(self):
        """Test that missing anthropic package raises ConfigurationError."""
        with patch("src.services.llm.anthropic_provider.Anthropic", None):
            with pytest.raises(ConfigurationError) as exc_info:
                AnthropicProvider(
                    api_key="sk-ant-test-key",
                    chat_model="claude-3-5-sonnet-20241022",
                )

            assert "anthropic package is not installed" in str(exc_info.value)

    def test_generate_success(self):
        """Test successful text generation."""
        with patch("src.services.llm.anthropic_provider.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            # Setup mock response
            mock_response = MagicMock()
            mock_text_part = MagicMock()
            mock_text_part.text = "Generated response from Claude"
            mock_response.content = [mock_text_part]

            mock_usage = MagicMock()
            mock_usage.input_tokens = 15
            mock_usage.output_tokens = 25
            mock_response.usage = mock_usage

            mock_client.messages.create.return_value = mock_response

            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
            )

            messages = [
                ChatMessage(role="user", content="Hello Claude!"),
            ]

            result = provider.generate(messages, temperature=0.5, max_tokens=200)

            # Verify
            assert isinstance(result, LLMGenerationResult)
            assert result.content == "Generated response from Claude"
            assert result.prompt_tokens == 15
            assert result.completion_tokens == 25
            assert result.model == "claude-3-5-sonnet-20241022"
            assert result.provider == "anthropic"

            # Verify API call
            mock_client.messages.create.assert_called_once()

    def test_generate_with_system_message(self):
        """Test generation with system message (Anthropic handles system separately)."""
        with patch("src.services.llm.anthropic_provider.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_response = MagicMock()
            mock_text_part = MagicMock()
            mock_text_part.text = "Response"
            mock_response.content = [mock_text_part]
            mock_usage = MagicMock()
            mock_usage.input_tokens = 10
            mock_usage.output_tokens = 5
            mock_response.usage = mock_usage

            mock_client.messages.create.return_value = mock_response

            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
            )

            messages = [
                ChatMessage(role="system", content="You are a helpful assistant."),
                ChatMessage(role="user", content="Hello!"),
            ]

            result = provider.generate(messages)

            # Verify system message was passed separately
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == "You are a helpful assistant."
            assert len(call_kwargs["messages"]) == 1  # Only user message
            assert call_kwargs["messages"][0]["role"] == "user"

    def test_generate_with_multiple_system_messages(self):
        """Test that multiple system messages are concatenated."""
        with patch("src.services.llm.anthropic_provider.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_response = MagicMock()
            mock_text_part = MagicMock()
            mock_text_part.text = "Response"
            mock_response.content = [mock_text_part]
            mock_usage = MagicMock()
            mock_usage.input_tokens = 10
            mock_usage.output_tokens = 5
            mock_response.usage = mock_usage

            mock_client.messages.create.return_value = mock_response

            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
            )

            messages = [
                ChatMessage(role="system", content="First instruction."),
                ChatMessage(role="system", content="Second instruction."),
                ChatMessage(role="user", content="Hello!"),
            ]

            result = provider.generate(messages)

            # Verify system messages were concatenated
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == "First instruction.\nSecond instruction."

    def test_embed_not_implemented(self):
        """Test that embed() raises NotImplementedError for Anthropic."""
        with patch("src.services.llm.anthropic_provider.Anthropic"):
            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
            )

            with pytest.raises(NotImplementedError) as exc_info:
                provider.embed(["Test text"])

            assert "does not currently support embeddings" in str(exc_info.value)

    def test_estimate_cost(self):
        """Test cost estimation calculation."""
        with patch("src.services.llm.anthropic_provider.Anthropic"):
            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
            )

            # Test with example token counts
            cost = provider.estimate_cost(prompt_tokens=1_000_000, completion_tokens=500_000)

            # Anthropic pricing: $3 per 1M input, $15 per 1M output
            expected_cost = (1_000_000 / 1_000_000 * 3.0) + (500_000 / 1_000_000 * 15.0)
            assert cost == expected_cost
            assert cost == 10.5  # 3.0 + 7.5

    def test_retry_logic_on_api_error(self):
        """Test retry logic when API fails."""
        with patch("src.services.llm.anthropic_provider.Anthropic") as mock_anthropic_class:
            from src.services.llm.anthropic_provider import AnthropicAPIError

            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            # Simulate failure then success
            mock_response = MagicMock()
            mock_text_part = MagicMock()
            mock_text_part.text = "Success after retry"
            mock_response.content = [mock_text_part]
            mock_usage = MagicMock()
            mock_usage.input_tokens = 10
            mock_usage.output_tokens = 5
            mock_response.usage = mock_usage

            mock_client.messages.create.side_effect = [
                AnthropicAPIError("API Error"),
                mock_response,
            ]

            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
                max_retries=3,
                retry_backoff_seconds=0.01,
            )

            messages = [ChatMessage(role="user", content="Test")]

            with patch("time.sleep"):
                result = provider.generate(messages)

            assert result.content == "Success after retry"
            assert mock_client.messages.create.call_count == 2

    def test_generate_default_max_tokens(self):
        """Test that default max_tokens is set when None provided."""
        with patch("src.services.llm.anthropic_provider.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_response = MagicMock()
            mock_text_part = MagicMock()
            mock_text_part.text = "Response"
            mock_response.content = [mock_text_part]
            mock_usage = MagicMock()
            mock_usage.input_tokens = 10
            mock_usage.output_tokens = 5
            mock_response.usage = mock_usage

            mock_client.messages.create.return_value = mock_response

            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
            )

            messages = [ChatMessage(role="user", content="Test")]
            result = provider.generate(messages, max_tokens=None)

            # Verify default max_tokens was used
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["max_tokens"] == 1024  # Default value

    def test_generate_handles_role_conversion(self):
        """Test that invalid roles are converted to 'user'."""
        with patch("src.services.llm.anthropic_provider.Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_response = MagicMock()
            mock_text_part = MagicMock()
            mock_text_part.text = "Response"
            mock_response.content = [mock_text_part]
            mock_usage = MagicMock()
            mock_usage.input_tokens = 10
            mock_usage.output_tokens = 5
            mock_response.usage = mock_usage

            mock_client.messages.create.return_value = mock_response

            provider = AnthropicProvider(
                api_key="sk-ant-test-key",
                chat_model="claude-3-5-sonnet-20241022",
            )

            messages = [
                ChatMessage(role="custom_role", content="Test"),  # Invalid role
            ]

            result = provider.generate(messages)

            # Verify invalid role was converted to 'user'
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["messages"][0]["role"] == "user"
