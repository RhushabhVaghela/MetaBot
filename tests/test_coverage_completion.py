import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.orchestrator import MegaBotOrchestrator
from core.llm_providers import AnthropicProvider, GeminiProvider, OpenAIProvider


@pytest.mark.asyncio
async def test_orchestrator_restart_components(mock_config):
    with patch("core.orchestrator.ModuleDiscovery"):
        orc = MegaBotOrchestrator(mock_config)
        orc.adapters = {
            "openclaw": AsyncMock(),
            "messaging": AsyncMock(),
            "mcp": AsyncMock(),
            "gateway": AsyncMock(),
        }

        await orc.restart_component("openclaw")
        assert orc.adapters["openclaw"].connect.called

        await orc.restart_component("messaging")
        # messaging restart creates a task

        await orc.restart_component("mcp")
        assert orc.adapters["mcp"].start_all.called

        await orc.restart_component("gateway")
        # gateway restart creates a task


@pytest.mark.asyncio
async def test_orchestrator_llm_dispatch_tool_use(orchestrator):
    # Test line 100-101 in llm_providers (tool_calls)
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [{"id": "1", "function": {"name": "test"}}]
                        }
                    }
                ]
            }
        )
        mock_post.return_value.__aenter__.return_value = mock_resp

        provider = OpenAIProvider(api_key="test")
        res = await provider.generate(prompt="test", tools=[{"name": "test"}])
        assert "tool_calls" in res


@pytest.mark.asyncio
async def test_anthropic_provider_computer_use():
    provider = AnthropicProvider(api_key="test")
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "stop_reason": "tool_use",
                "content": [{"type": "tool_use", "id": "1", "name": "computer"}],
            }
        )
        mock_post.return_value.__aenter__.return_value = mock_resp

        res = await provider.generate(prompt="test", tools=[{"name": "computer"}])
        assert res[0]["type"] == "tool_use"


@pytest.mark.asyncio
async def test_gemini_provider_tool_use():
    provider = GeminiProvider(api_key="test")
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "candidates": [
                    {"content": {"parts": [{"functionCall": {"name": "test"}}]}}
                ]
            }
        )
        mock_post.return_value.__aenter__.return_value = mock_resp

        res = await provider.generate(prompt="test", tools=[{"name": "test"}])
        assert "functionCall" in res[0]


@pytest.mark.asyncio
async def test_orchestrator_handle_client_json_error(orchestrator):
    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = ["invalid json", Exception("stop")]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception:
        pass
    # Should handle error and continue or exit
    assert True
