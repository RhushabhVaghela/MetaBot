"""Extended tests for MegaBot orchestrator"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from core.orchestrator import MegaBotOrchestrator
from core.interfaces import Message


@pytest.mark.asyncio
async def test_heartbeat_loop(orchestrator):
    """Test heartbeat loop functionality and component restarts"""
    orchestrator.adapters = {"test": MagicMock(is_connected=False)}

    with patch("asyncio.sleep", side_effect=[None, Exception("break")]):
        with patch.object(
            orchestrator, "restart_component", new_callable=AsyncMock
        ) as mock_restart:
            try:
                await orchestrator.heartbeat_loop()
            except Exception:
                pass

            assert mock_restart.called


@pytest.mark.asyncio
async def test_pruning_loop(orchestrator):
    """Test memory pruning loop"""
    orchestrator.memory = MagicMock()
    orchestrator.memory.get_all_chat_ids = AsyncMock(return_value=["chat1"])
    orchestrator.memory.chat_forget = AsyncMock()

    with patch("asyncio.sleep", side_effect=[None, Exception("break")]):
        try:
            await orchestrator.pruning_loop()
        except Exception:
            pass

        assert orchestrator.memory.get_all_chat_ids.called
        assert orchestrator.memory.chat_forget.called


@pytest.mark.asyncio
async def test_proactive_loop(orchestrator):
    """Test proactive task checking loop"""
    orchestrator.adapters = {
        "memu": MagicMock(),
        "openclaw": MagicMock(),
        "mcp": MagicMock(),
    }
    orchestrator.adapters["memu"].get_anticipations = AsyncMock(
        return_value=[{"content": "Action 1"}]
    )
    orchestrator.adapters["openclaw"].send_message = AsyncMock()
    orchestrator.adapters["mcp"].call_tool = AsyncMock(return_value=[])

    with patch("asyncio.sleep", side_effect=[None, Exception("break")]):
        try:
            await orchestrator.proactive_loop()
        except Exception:
            pass

        assert orchestrator.adapters["memu"].get_anticipations.called
        assert orchestrator.adapters["openclaw"].send_message.called


@pytest.mark.asyncio
async def test_check_identity_claims(orchestrator):
    """Test identity linking through conversation"""
    orchestrator.admin_handler = MagicMock()
    orchestrator.admin_handler.approval_queue = []
    orchestrator.llm = MagicMock()
    orchestrator.llm.generate = AsyncMock(return_value="user123")
    orchestrator.send_platform_message = AsyncMock()

    # Simulate a "link" mention
    await orchestrator._check_identity_claims("I am user123", "native", "p1", "c1")

    assert len(orchestrator.admin_handler.approval_queue) == 1
    assert orchestrator.admin_handler.approval_queue[0]["type"] == "identity_link"
    assert (
        orchestrator.admin_handler.approval_queue[0]["payload"]["internal_id"]
        == "USER123"
    )


def test_sanitize_output(orchestrator):
    """Test terminal output sanitization"""
    text = "\x1b[31mRed\x1b[0m text"
    sanitized = orchestrator._sanitize_output(text)
    assert "Red" in sanitized
    assert "\x1b" not in sanitized


@pytest.mark.asyncio
async def test_get_relevant_lessons(orchestrator):
    """Test RAG retrieval of learned lessons"""
    orchestrator.llm = MagicMock()
    orchestrator.llm.generate = AsyncMock(return_value="keyword1, keyword2")
    orchestrator.memory = MagicMock()
    orchestrator.memory.memory_search = AsyncMock(
        return_value=[{"content": "Lesson 1", "key": "k1"}]
    )

    lessons = await orchestrator._get_relevant_lessons("how to fix bugs")
    assert "Lesson 1" in lessons
