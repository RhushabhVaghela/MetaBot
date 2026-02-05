import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from adapters.mcp_adapter import MCPAdapter, MCPManager


@pytest.mark.asyncio
async def test_mcp_adapter_execute():
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout.readline = AsyncMock()
        mock_exec.return_value = mock_process
        mock_process.stdout.readline.return_value = (
            json.dumps({"jsonrpc": "2.0", "result": "ok"}).encode() + b"\n"
        )

        adapter = MCPAdapter(
            {"name": "test", "command": "npx", "args": ["test-server"]}
        )
        result = await adapter.execute(method="tools/list")

        assert mock_exec.called
        assert mock_process.stdin.write.called
        assert result["result"] == "ok"


@pytest.mark.asyncio
async def test_mcp_adapter_start():
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        adapter = MCPAdapter({"name": "test", "command": "npx"})
        await adapter.start()
        assert mock_exec.called


@pytest.mark.asyncio
async def test_mcp_adapter_execute_no_stdout():
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout.readline = AsyncMock()
        mock_exec.return_value = mock_process
        mock_process.stdout.readline.return_value = b""

        adapter = MCPAdapter({"name": "test", "command": "npx"})
        result = await adapter.execute(method="test")
        assert result is None


@pytest.mark.asyncio
async def test_mcp_manager_call_tool():
    with patch(
        "adapters.mcp_adapter.MCPAdapter.execute", new_callable=AsyncMock
    ) as mock_execute:
        mock_execute.return_value = {"result": "success"}

        manager = MCPManager([{"name": "test-server", "command": "npx"}])
        manager.servers["test-server"].process = MagicMock()

        result = await manager.call_tool("test-server", "test-tool", {"arg1": "val1"})

        assert result["result"] == "success"
        mock_execute.assert_called_once_with(
            method="tools/call",
            params={"name": "test-tool", "arguments": {"arg1": "val1"}},
        )


@pytest.mark.asyncio
async def test_mcp_manager_call_tool_not_found():
    manager = MCPManager([])
    result = await manager.call_tool("none", "none", {})
    assert "error" in result


@pytest.mark.asyncio
async def test_mcp_manager_start_all():
    manager = MCPManager(
        [{"name": "s1", "command": "c1"}, {"name": "s2", "command": "c2"}]
    )
    for s in manager.servers.values():
        s.start = AsyncMock()

    await manager.start_all()
    for s in manager.servers.values():
        assert s.start.called
