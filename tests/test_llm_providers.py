"""
Tests for LLM Providers
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock

from core.llm_providers import (
    OpenAICompatibleProvider,
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    get_llm_provider,
)


class AsyncContextMock:
    """Mock async context manager"""

    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.fixture
def mock_session():
    """Mock aiohttp ClientSession"""
    return AsyncMock()


class TestOpenAICompatibleProvider:
    """Test OpenAICompatibleProvider base class"""

    def test_init(self):
        """Test initialization"""
        provider = OpenAICompatibleProvider("gpt-4", "test_key", "https://api.test.com")
        assert provider.model == "gpt-4"
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://api.test.com"

    @pytest.mark.asyncio
    async def test_generate_missing_api_key(self):
        """Test generate with missing API key"""
        provider = OpenAICompatibleProvider("gpt-4", None, "https://api.test.com")
        result = await provider.generate(prompt="test")
        assert "API key missing" in result

    @pytest.mark.asyncio
    async def test_generate_success_text(self):
        """Test successful generate with text response"""
        provider = OpenAICompatibleProvider("gpt-4", "test_key", "https://api.test.com")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"choices": [{"message": {"content": "test response"}}]}
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            result = await provider.generate(
                prompt="test prompt", context="test context"
            )
            assert result == "test response"

    @pytest.mark.asyncio
    async def test_generate_success_with_tools(self):
        """Test successful generate with tool calls"""
        provider = OpenAICompatibleProvider("gpt-4", "test_key", "https://api.test.com")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"choices": [{"message": {"tool_calls": [{"id": "call_1"}]}}]}
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            result = await provider.generate(
                prompt="test", tools=[{"name": "test_tool"}]
            )
            assert "tool_calls" in result

    @pytest.mark.asyncio
    async def test_generate_with_messages(self):
        """Test generate with messages parameter"""
        provider = OpenAICompatibleProvider("gpt-4", "test_key", "https://api.test.com")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"choices": [{"message": {"content": "response"}}]}
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            messages = [{"role": "user", "content": "test message"}]
            result = await provider.generate(messages=messages)
            assert result == "response"

    @pytest.mark.asyncio
    async def test_generate_http_error(self):
        """Test generate with HTTP error"""
        provider = OpenAICompatibleProvider("gpt-4", "test_key", "https://api.test.com")

        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            result = await provider.generate(prompt="test")
            assert "error: 400" in result

    @pytest.mark.asyncio
    async def test_generate_connection_error(self):
        """Test generate with connection error"""
        provider = OpenAICompatibleProvider("gpt-4", "test_key", "https://api.test.com")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_class.side_effect = Exception("Connection failed")

            result = await provider.generate(prompt="test")
            assert "connection failed" in result


class TestAnthropicProvider:
    """Test AnthropicProvider"""

    def test_init(self):
        """Test initialization"""
        provider = AnthropicProvider("claude-3", "test_key")
        assert provider.model == "claude-3"
        assert provider.api_key == "test_key"

    @pytest.mark.asyncio
    async def test_generate_missing_api_key(self):
        """Test generate with missing API key"""
        provider = AnthropicProvider("claude-3", None)
        result = await provider.generate(prompt="test")
        assert "API key missing" in result

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generate"""
        provider = AnthropicProvider("claude-3", "test_key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"content": [{"text": "test response"}]}
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            result = await provider.generate(prompt="test")
            assert result == "test response"

    @pytest.mark.asyncio
    async def test_generate_with_tools(self):
        """Test generate with computer use tools"""
        provider = AnthropicProvider("claude-3", "test_key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"stop_reason": "tool_use", "content": [{"tool_call": "data"}]}
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            tools = [{"name": "computer"}]
            result = await provider.generate(prompt="test", tools=tools)
            assert result == [{"tool_call": "data"}]


class TestGeminiProvider:
    """Test GeminiProvider"""

    def test_init(self):
        """Test initialization"""
        provider = GeminiProvider("gemini-1.5", "test_key")
        assert provider.model == "gemini-1.5"
        assert provider.api_key == "test_key"

    @pytest.mark.asyncio
    async def test_generate_missing_api_key(self):
        """Test generate with missing API key"""
        provider = GeminiProvider("gemini-1.5", None)
        result = await provider.generate(prompt="test")
        assert "API key missing" in result

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generate"""
        provider = GeminiProvider("gemini-1.5", "test_key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "candidates": [{"content": {"parts": [{"text": "test response"}]}}]
            }
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            result = await provider.generate(prompt="test")
            assert result == "test response"

    @pytest.mark.asyncio
    async def test_generate_with_function_call(self):
        """Test generate with function call response"""
        provider = GeminiProvider("gemini-1.5", "test_key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "candidates": [{"content": {"parts": [{"functionCall": "call_data"}]}}]
            }
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            result = await provider.generate(prompt="test")
            assert result == [{"functionCall": "call_data"}]


class TestOllamaProvider:
    """Test OllamaProvider"""

    def test_init(self):
        """Test initialization"""
        provider = OllamaProvider("llama3", "http://localhost:11434/api/generate")
        assert provider.model == "llama3"
        assert provider.url == "http://localhost:11434/api/generate"

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generate"""
        provider = OllamaProvider("llama3")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "test response"})

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            result = await provider.generate(prompt="test prompt", context="context")
            assert result == "test response"

    @pytest.mark.asyncio
    async def test_generate_with_messages(self):
        """Test generate with messages"""
        provider = OllamaProvider("llama3")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "response"})

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            messages = [{"role": "user", "content": "test"}]
            result = await provider.generate(messages=messages)
            assert result == "response"

    @pytest.mark.asyncio
    async def test_generate_with_tools(self):
        """Test generate with tools"""
        provider = OllamaProvider("llama3")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "response"})

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=AsyncContextMock(mock_response))
            mock_session_class.return_value = mock_session

            tools = [{"name": "tool1"}]
            result = await provider.generate(prompt="test", tools=tools)
            assert result == "response"


class TestGetLLMProvider:
    """Test get_llm_provider factory function"""

    def test_get_openai_provider(self):
        """Test getting OpenAI provider"""
        config = {"provider": "openai", "model": "gpt-4"}
        provider = get_llm_provider(config)
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4"

    def test_get_anthropic_provider(self):
        """Test getting Anthropic provider"""
        config = {"provider": "anthropic", "model": "claude-3"}
        provider = get_llm_provider(config)
        assert isinstance(provider, AnthropicProvider)
        assert provider.model == "claude-3"

    def test_get_gemini_provider(self):
        """Test getting Gemini provider"""
        config = {"provider": "gemini", "model": "gemini-1.5"}
        provider = get_llm_provider(config)
        assert isinstance(provider, GeminiProvider)
        assert provider.model == "gemini-1.5"

    def test_get_ollama_provider_default(self):
        """Test getting default Ollama provider"""
        config = {"provider": "unknown"}
        provider = get_llm_provider(config)
        assert isinstance(provider, OllamaProvider)
        assert provider.model == "llama3"

    def test_get_provider_with_defaults(self):
        """Test provider creation with default models"""
        config = {"provider": "groq"}
        provider = get_llm_provider(config)
        assert provider.model == "llama3-70b-8192"  # Default for Groq
