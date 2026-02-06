"""
Tests for FastAPI lifespan and websocket endpoints.

These tests are separated because they test module-level globals
and need to run in isolation.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from core.orchestrator import websocket_endpoint, lifespan


@pytest.mark.asyncio
async def test_lifespan():
    """Test FastAPI lifespan context manager"""
    import core.orchestrator as orch_module

    original_orchestrator = orch_module.orchestrator
    orch_module.orchestrator = None  # Reset to None before test

    try:
        with patch("core.orchestrator.MegaBotOrchestrator") as mock_orc_class:
            mock_instance = Mock()
            mock_instance.start = AsyncMock()
            mock_instance.shutdown = AsyncMock()
            mock_orc_class.return_value = mock_instance
            mock_app = MagicMock()

            # Actually call the async context manager
            async with lifespan(mock_app):
                # Verify orchestrator was created and started
                assert mock_orc_class.called, (
                    "MegaBotOrchestrator should be instantiated"
                )

            # Verify start and shutdown were called
            assert mock_instance.start.called, "orchestrator.start() should be called"
            assert mock_instance.shutdown.called, (
                "orchestrator.shutdown() should be called"
            )
    finally:
        orch_module.orchestrator = original_orchestrator


@pytest.mark.asyncio
async def test_websocket_endpoint():
    """Test websocket endpoint when orchestrator is available"""
    import core.orchestrator as orch_module

    original_orchestrator = orch_module.orchestrator

    try:
        with patch("core.orchestrator.orchestrator") as mock_orc:
            mock_orc.handle_client = AsyncMock()
            mock_ws = AsyncMock()
            await websocket_endpoint(mock_ws)
            mock_orc.handle_client.assert_called_once_with(mock_ws)
    finally:
        orch_module.orchestrator = original_orchestrator


@pytest.mark.asyncio
async def test_websocket_endpoint_uninitialized():
    """Test websocket endpoint when orchestrator is None"""
    import core.orchestrator as orch_module

    original_orchestrator = orch_module.orchestrator
    orch_module.orchestrator = None  # Ensure it's None for this test

    try:
        mock_ws = AsyncMock()
        await websocket_endpoint(mock_ws)
        assert mock_ws.accept.called
        assert mock_ws.send_text.called
        assert mock_ws.close.called
    finally:
        orch_module.orchestrator = original_orchestrator


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the /health endpoint returns ok status"""
    from core.orchestrator import health

    result = await health()
    assert result == {"status": "ok"}
