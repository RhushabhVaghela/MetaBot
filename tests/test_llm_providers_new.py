"""Tests for LLM providers"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from core.llm_providers import (
    get_llm_provider,
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    GroqProvider,
    DeepSeekProvider,
    XAIProvider,
    PerplexityProvider,
    CerebrasProvider,
    SambaNovaProvider,
    FireworksProvider,
    DeepInfraProvider,
    MistralProvider,
    OpenRouterProvider,
    GitHubCopilotProvider,
)


class TestLLMProviders:
    """Test suite for LLM provider implementations"""

    @pytest.mark.asyncio
    async def test_openai_provider_success(self):
        """Test OpenAI provider success path"""
        provider = OpenAIProvider(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={"choices": [{"message": {"content": "OpenAI Response"}}]}
        )

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession.post", return_value=mock_cm):
            result = await provider.generate("hello")
            assert result == "OpenAI Response"

    @pytest.mark.asyncio
    async def test_anthropic_provider_success(self):
        """Test Anthropic provider success path"""
        provider = AnthropicProvider(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={"content": [{"text": "Anthropic Response"}]}
        )

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession.post", return_value=mock_cm):
            result = await provider.generate("hello")
            assert result == "Anthropic Response"

    @pytest.mark.asyncio
    async def test_gemini_provider_success(self):
        """Test Gemini provider success path"""
        provider = GeminiProvider(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "candidates": [{"content": {"parts": [{"text": "Gemini Response"}]}}]
            }
        )

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession.post", return_value=mock_cm):
            result = await provider.generate("hello")
            assert result == "Gemini Response"

    @pytest.mark.asyncio
    async def test_ollama_provider_success(self):
        """Test Ollama provider success path"""
        provider = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"response": "Ollama Response"})

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession.post", return_value=mock_cm):
            result = await provider.generate("hello")
            assert result == "Ollama Response"

    @pytest.mark.asyncio
    async def test_reason_method(self):
        """Test the deep reasoning multi-step loop"""
        provider = OpenAIProvider(api_key="test-key")
        # Mock 3 responses: 1. Think, 2. Knowledge Retrieval, 3. Answer
        provider.generate = AsyncMock(
            side_effect=["Step 1: Think", "Step 2: Info", "Step 3: Final Answer"]
        )

        result = await provider.reason("What is life?")
        assert result == "Step 3: Final Answer"
        assert provider.generate.call_count == 3

    def test_get_llm_provider_factory(self):
        """Test factory method for getting providers"""
        assert isinstance(get_llm_provider({"provider": "openai"}), OpenAIProvider)
        assert isinstance(
            get_llm_provider({"provider": "anthropic"}), AnthropicProvider
        )
        assert isinstance(get_llm_provider({"provider": "gemini"}), GeminiProvider)
        assert isinstance(get_llm_provider({"provider": "ollama"}), OllamaProvider)
        assert isinstance(get_llm_provider({"provider": "groq"}), GroqProvider)
        assert isinstance(get_llm_provider({"provider": "deepseek"}), DeepSeekProvider)
        assert isinstance(get_llm_provider({"provider": "xai"}), XAIProvider)
        assert isinstance(
            get_llm_provider({"provider": "perplexity"}), PerplexityProvider
        )
        assert isinstance(get_llm_provider({"provider": "cerebras"}), CerebrasProvider)
        assert isinstance(
            get_llm_provider({"provider": "sambanova"}), SambaNovaProvider
        )
        assert isinstance(
            get_llm_provider({"provider": "fireworks"}), FireworksProvider
        )
        assert isinstance(
            get_llm_provider({"provider": "deepinfra"}), DeepInfraProvider
        )
        assert isinstance(get_llm_provider({"provider": "mistral"}), MistralProvider)
        assert isinstance(
            get_llm_provider({"provider": "openrouter"}), OpenRouterProvider
        )
        assert isinstance(
            get_llm_provider({"provider": "github-copilot"}), GitHubCopilotProvider
        )
