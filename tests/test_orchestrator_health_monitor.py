import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def orchestrator(mock_config):
    # Minimal orchestrator fixture copied from tests/test_orchestrator.py
    from core.orchestrator import MegaBotOrchestrator

    with patch("core.orchestrator.ModuleDiscovery"):
        with patch("core.orchestrator.OpenClawAdapter"):
            with patch("core.orchestrator.MemUAdapter"):
                with patch("core.orchestrator.MCPManager"):
                    orc = MegaBotOrchestrator(mock_config)
                    # Use fresh mocks for all adapters
                    orc.adapters = {
                        "openclaw": AsyncMock(),
                        "memu": AsyncMock(),
                        "mcp": AsyncMock(),
                        "messaging": AsyncMock(),
                        "gateway": AsyncMock(),
                    }
                    orc.llm = AsyncMock()
                    # Mock memory to avoid database operations
                    orc.memory = AsyncMock()
                    return orc


@pytest.mark.asyncio
async def test_start_handles_create_task_patched(orchestrator):
    """When asyncio.create_task and ensure_future are patched to raise,
    orchestrator.start should not raise and should not leave an unscheduled
    _health_task set (coroutine should be closed).
    """
    # Patch create_task and ensure_future to raise so scheduling fails
    with (
        patch("asyncio.create_task", side_effect=Exception("create_task patched")),
        patch("asyncio.ensure_future", side_effect=Exception("ensure_future patched")),
    ):
        # Should not raise
        await orchestrator.start()

        # Since both scheduling methods failed, _health_task should be None
        assert getattr(orchestrator, "_health_task", None) is None


@pytest.mark.asyncio
async def test_shutdown_closes_underlying_coroutine_for_mock_task(orchestrator):
    """If _health_task is a MagicMock that borrowed a real coroutine's
    __await__, orchestrator.shutdown should attempt to close the underlying
    coroutine to avoid "coroutine was never awaited" warnings.
    """

    async def _dummy_monitor():
        # short sleep to create a real coroutine object
        await asyncio.sleep(0.01)

    coro = _dummy_monitor()

    mock_task = MagicMock()
    # Attach the real coroutine's __await__ bound method so shutdown logic
    # can discover and close the underlying coroutine via __await__.__self__
    mock_task.__await__ = coro.__await__

    orchestrator._health_task = mock_task

    # Should not raise
    await orchestrator.shutdown()

    # Underlying coroutine should be closed (cr_frame becomes None)
    assert getattr(coro, "cr_frame", None) is None
