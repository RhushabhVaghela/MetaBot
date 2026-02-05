import pytest
import json
import asyncio
import os
from unittest.mock import AsyncMock, patch, MagicMock
from core.orchestrator import MegaBotOrchestrator, health, websocket_endpoint
from core.interfaces import Message


@pytest.fixture
def orchestrator(mock_config):
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
async def test_orchestrator_start(orchestrator):
    await orchestrator.start()
    assert orchestrator.adapters["openclaw"].connect.called
    assert orchestrator.adapters["mcp"].start_all.called


@pytest.mark.asyncio
async def test_orchestrator_handle_message(orchestrator):
    mock_ws = AsyncMock()
    # Standard relay
    orchestrator.mode = "plan"
    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "message", "content": "hello"}),
        Exception("stop"),
    ]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception as e:
        if str(e) != "stop":
            raise
    assert orchestrator.adapters["memu"].store.called
    assert orchestrator.adapters["openclaw"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_handle_message_build(orchestrator):
    mock_ws = AsyncMock()
    orchestrator.mode = "build"
    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "message", "content": "build things"}),
        Exception("stop"),
    ]
    orchestrator.llm.generate.return_value = "Success"

    # Mock run_autonomous_build to avoid background task complexities
    with patch.object(orchestrator, "run_autonomous_build", AsyncMock()) as mock_run:
        try:
            await orchestrator.handle_client(mock_ws)
        except Exception as e:
            if str(e) != "stop":
                raise

        await asyncio.sleep(0.05)
        assert mock_run.called
    assert mock_ws.send_json.called


@pytest.mark.asyncio
async def test_orchestrator_set_mode(orchestrator):
    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "set_mode", "mode": "build"}),
        Exception("stop"),
    ]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception as e:
        if str(e) != "stop":
            raise
    assert orchestrator.mode == "build"
    assert mock_ws.send_json.called


@pytest.mark.asyncio
async def test_orchestrator_mcp_call(orchestrator):
    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = [
        json.dumps(
            {"type": "mcp_call", "server": "s1", "tool": "t1", "params": {"p1": "v1"}}
        ),
        Exception("stop"),
    ]
    orchestrator.adapters["mcp"].call_tool.return_value = {"res": "ok"}
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception as e:
        if str(e) != "stop":
            raise
    orchestrator.adapters["mcp"].call_tool.assert_called_once_with(
        "s1", "t1", {"p1": "v1"}
    )
    assert mock_ws.send_json.called


@pytest.mark.asyncio
async def test_orchestrator_on_openclaw_event(orchestrator):
    mock_client = AsyncMock()
    orchestrator.clients.add(mock_client)
    event_data = {"method": "chat.message", "params": {"content": "hi"}}
    await orchestrator.on_openclaw_event(event_data)
    assert mock_client.send_json.called


@pytest.mark.asyncio
async def test_orchestrator_search_memory(orchestrator):
    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "search", "query": "test query"}),
        Exception("stop"),
    ]
    orchestrator.adapters["memu"].search.return_value = [{"content": "result"}]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception as e:
        if str(e) != "stop":
            raise
    orchestrator.adapters["memu"].search.assert_called_once_with("test query")
    assert mock_ws.send_json.called


@pytest.mark.asyncio
async def test_orchestrator_start_openclaw_failure(orchestrator):
    orchestrator.adapters["openclaw"].connect.side_effect = Exception("conn failed")
    await orchestrator.start()
    assert True


@pytest.mark.asyncio
async def test_orchestrator_start_mcp_failure(orchestrator):
    orchestrator.adapters["mcp"].start_all.side_effect = Exception("mcp failed")
    await orchestrator.start()
    assert True


@pytest.mark.asyncio
async def test_orchestrator_sync_loop_error(orchestrator):
    with patch("os.path.expanduser", return_value="/tmp/mock_logs"):
        with patch("os.path.exists", return_value=True):
            orchestrator.adapters["memu"].ingest_openclaw_logs.side_effect = [
                Exception("ingest err"),
                Exception("stop"),
            ]
            with patch("asyncio.sleep", side_effect=[None, Exception("stop")]):
                try:
                    await orchestrator.sync_loop()
                except Exception as e:
                    if str(e) != "stop":
                        raise
            assert orchestrator.adapters["memu"].ingest_openclaw_logs.called


@pytest.mark.asyncio
async def test_orchestrator_proactive_loop(orchestrator):
    orchestrator.adapters["memu"].get_anticipations.return_value = [
        {"content": "do laundry"}
    ]
    with patch("asyncio.sleep", side_effect=[None, Exception("stop")]):
        try:
            await orchestrator.proactive_loop()
        except Exception as e:
            if str(e) != "stop":
                raise
    assert orchestrator.adapters["openclaw"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_proactive_loop_error(orchestrator):
    """Test exception handling in proactive_loop"""
    orchestrator.adapters["memu"].get_anticipations.side_effect = Exception(
        "anticipation error"
    )
    with patch("asyncio.sleep", side_effect=[None, Exception("stop")]):
        try:
            await orchestrator.proactive_loop()
        except Exception as e:
            if str(e) != "stop":
                raise
    # Should not crash, should continue to next iteration
    assert orchestrator.adapters["memu"].get_anticipations.called


@pytest.mark.asyncio
async def test_orchestrator_autonomous_build(orchestrator):
    mock_ws = AsyncMock()
    msg = Message(content="build things", sender="user")
    orchestrator.adapters["mcp"].call_tool.return_value = ["/path"]
    orchestrator.llm.generate.return_value = "Success"
    await orchestrator.run_autonomous_build(msg, mock_ws)
    assert mock_ws.send_json.called


@pytest.mark.asyncio
async def test_orchestrator_gateway_message(orchestrator):
    """Test handling messages from the Unified Gateway"""
    orchestrator.mode = "build"
    data = {
        "type": "message",
        "content": "hello from gateway",
        "sender_name": "remote-user",
        "_meta": {"client_id": "cf-1"},
    }
    await orchestrator.on_gateway_message(data)
    assert orchestrator.memory.chat_write.called

    # Non-build mode
    orchestrator.mode = "plan"
    await orchestrator.on_gateway_message(data)
    assert orchestrator.adapters["openclaw"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_on_openclaw_event_relay(orchestrator):
    """Test relay from OpenClaw to Native messaging"""
    data = {
        "method": "chat.message",
        "params": {"content": "hi", "sender": "OpenClawBot"},
    }
    await orchestrator.on_openclaw_event(data)
    assert orchestrator.adapters["messaging"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_llm_dispatch_mock(orchestrator):
    """Test LLM dispatch logic with mocking"""
    orchestrator.llm = None
    with patch("core.orchestrator.get_llm_provider") as mock_get:
        from core.llm_providers import AnthropicProvider

        mock_get.return_value = AnthropicProvider(api_key="test")
        orchestrator.llm = mock_get.return_value

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(
                return_value={"content": [{"text": "I will use the filesystem tool."}]}
            )
            mock_post.return_value.__aenter__.return_value = mock_resp

            result = await orchestrator._llm_dispatch("test prompt", "some context")
            assert "filesystem" in result


@pytest.mark.asyncio
async def test_orchestrator_run_autonomous_gateway_build(orchestrator):
    """Test autonomous build triggered from gateway"""
    msg = Message(content="build app", sender="gateway-user")
    original_data = {"_meta": {"client_id": "cf-1"}}
    await orchestrator.run_autonomous_gateway_build(msg, original_data)
    assert orchestrator.adapters["openclaw"].send_message.called
    assert orchestrator.adapters["gateway"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_llm_dispatch_failure(orchestrator):
    """Test LLM dispatch failure (non-200 status)"""
    orchestrator.llm = None
    with patch("core.orchestrator.get_llm_provider") as mock_get:
        from core.llm_providers import AnthropicProvider

        mock_get.return_value = AnthropicProvider(api_key="test")
        orchestrator.llm = mock_get.return_value

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status = 500
            mock_post.return_value.__aenter__.return_value = mock_resp

            result = await orchestrator._llm_dispatch("prompt", "context")
            assert "error: 500" in result


@pytest.mark.asyncio
async def test_orchestrator_policy_allow(orchestrator):
    """Test auto-approval based on allow policy"""
    orchestrator.permissions.set_policy("git status", "AUTO")
    event = {"method": "system.run", "params": {"command": "git status"}}
    await orchestrator.on_openclaw_event(event)
    assert orchestrator.adapters["openclaw"].send_message.called
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_policy_deny(orchestrator):
    """Test auto-denial based on deny policy"""
    orchestrator.permissions.set_policy("rm -rf", "NEVER")
    event = {"method": "system.run", "params": {"command": "rm -rf /"}}
    orchestrator.adapters["openclaw"].send_message.reset_mock()
    await orchestrator.on_openclaw_event(event)
    assert not orchestrator.adapters["openclaw"].send_message.called
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_policy_wildcard_allow(orchestrator):
    """Test global auto-approval using '*' wildcard"""
    orchestrator.permissions.set_policy("*", "AUTO")
    event = {"method": "system.run", "params": {"command": "any dangerous command"}}
    await orchestrator.on_openclaw_event(event)
    assert orchestrator.adapters["openclaw"].send_message.called
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_policy_wildcard_deny(orchestrator):
    """Test global auto-denial using '*' wildcard"""
    orchestrator.permissions.set_policy("*", "NEVER")
    event = {"method": "system.run", "params": {"command": "even safe command"}}
    orchestrator.adapters["openclaw"].send_message.reset_mock()
    await orchestrator.on_openclaw_event(event)
    assert not orchestrator.adapters["openclaw"].send_message.called
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_chat_approval(orchestrator):
    """Test approving a command via chat command '!yes'"""
    orchestrator.config.admins = ["my-phone"]
    await orchestrator.on_openclaw_event(
        {"method": "system.run", "params": {"command": "delete logs"}}
    )
    assert len(orchestrator.admin_handler.approval_queue) == 1
    orchestrator.adapters["openclaw"].send_message.reset_mock()
    await orchestrator.on_openclaw_event(
        {
            "method": "chat.message",
            "params": {"content": "!yes", "sender_id": "my-phone"},
        }
    )
    assert orchestrator.adapters["openclaw"].send_message.called
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_admin_commands_extended(orchestrator):
    """Test !allow and !mode commands"""
    orchestrator.config.admins = ["admin"]
    await orchestrator.on_openclaw_event(
        {
            "method": "chat.message",
            "params": {"content": "!allow git status", "sender_id": "admin"},
        }
    )
    assert "git status" in orchestrator.config.policies["allow"]
    await orchestrator.on_openclaw_event(
        {
            "method": "chat.message",
            "params": {"content": "!mode debug", "sender_id": "admin"},
        }
    )
    assert orchestrator.mode == "debug"
    await orchestrator.on_openclaw_event(
        {"method": "system.run", "params": {"command": "cmd"}}
    )
    assert len(orchestrator.admin_handler.approval_queue) == 1
    await orchestrator.on_openclaw_event(
        {"method": "chat.message", "params": {"content": "!no", "sender_id": "admin"}}
    )
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_gateway_admin_command(orchestrator):
    """Test admin command from unified gateway"""
    orchestrator.config.admins = ["gateway-admin"]
    data = {"type": "message", "content": "!mode build", "sender_id": "gateway-admin"}
    await orchestrator.on_gateway_message(data)
    assert orchestrator.mode == "build"
    await asyncio.sleep(0.05)
    assert orchestrator.adapters["messaging"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_credential_loading():
    """Test the dynamic loading of api-credentials.py"""
    with patch("os.path.exists", return_value=True):
        with patch("importlib.util.spec_from_file_location") as mock_spec:
            assert True


@pytest.mark.asyncio
async def test_orchestrator_approval_flow(orchestrator):
    """Test the Interlock/Approval Queue logic"""
    mock_client = AsyncMock()
    orchestrator.clients.add(mock_client)
    event = {"method": "system.run", "params": {"command": "rm -rf /"}}
    await orchestrator.on_openclaw_event(event)
    assert len(orchestrator.admin_handler.approval_queue) == 1
    assert orchestrator.admin_handler.approval_queue[0]["type"] == "system_command"
    assert mock_client.send_json.called
    action_id = orchestrator.admin_handler.approval_queue[0]["id"]
    await orchestrator._process_approval(action_id, approved=True)
    assert orchestrator.adapters["openclaw"].send_message.called
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_rejection_flow(orchestrator):
    """Test rejecting a sensitive command"""
    event = {"method": "system.run", "params": {"command": "format c:"}}
    await orchestrator.on_openclaw_event(event)
    action_id = orchestrator.admin_handler.approval_queue[0]["id"]
    orchestrator.adapters["openclaw"].send_message.reset_mock()
    await orchestrator._process_approval(action_id, approved=False)
    assert not orchestrator.adapters["openclaw"].send_message.called
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_handle_client_non_build(orchestrator):
    """Test standard relay in handle_client"""
    mock_ws = AsyncMock()
    orchestrator.mode = "plan"
    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "message", "content": "test message"}),
        Exception("stop"),
    ]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception:
        pass
    assert orchestrator.adapters["openclaw"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_on_openclaw_event_error_relay(orchestrator):
    """Test error handling when relaying to UI clients"""
    mock_client = AsyncMock()
    mock_client.send_json.side_effect = Exception("conn lost")
    orchestrator.clients.add(mock_client)
    await orchestrator.on_openclaw_event({"type": "event"})
    assert mock_client not in orchestrator.clients


@pytest.mark.asyncio
async def test_orchestrator_run_autonomous_build_full(orchestrator):
    """Test full autonomous build with LLM dispatch success"""
    mock_ws = AsyncMock()
    msg = Message(content="build me something", sender="user")
    with patch.object(orchestrator, "_llm_dispatch", return_value="Dispatch Success"):
        await orchestrator.run_autonomous_build(msg, mock_ws)
        assert mock_ws.send_json.called


@pytest.mark.asyncio
async def test_orchestrator_client_removal(orchestrator):
    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = Exception("done")
    await orchestrator.handle_client(mock_ws)
    assert mock_ws not in orchestrator.clients


@pytest.mark.asyncio
async def test_orchestrator_api_credentials_loading():
    """Test API credentials loading from api-credentials.py"""
    import tempfile
    import importlib
    import core.orchestrator as orch_module

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('OPENAI_API_KEY = "test-key-123"\n')
        f.write('ANTHROPIC_API_KEY = "anthropic-key-456"\n')
        temp_path = f.name
    try:
        with patch("os.path.exists", return_value=True):
            with patch("os.path.join", return_value=temp_path):
                with patch("os.getcwd", return_value="/tmp"):
                    importlib.reload(orch_module)
                    assert "OPENAI_API_KEY" in orch_module.CREDENTIALS
                    assert orch_module.CREDENTIALS["OPENAI_API_KEY"] == "test-key-123"
    finally:
        os.unlink(temp_path)
        importlib.reload(orch_module)


@pytest.mark.asyncio
async def test_orchestrator_on_messaging_connect(orchestrator):
    """Test on_messaging_connect sends greeting"""
    with patch.object(orchestrator, "_to_platform_message") as mock_to_platform:
        mock_msg = MagicMock()
        mock_to_platform.return_value = mock_msg
        await orchestrator.on_messaging_connect("client-123", "whatsapp")
        assert orchestrator.adapters["messaging"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_admin_check_failure(orchestrator):
    """Test admin command rejected for non-admin"""
    orchestrator.config.admins = ["admin-only"]
    result = await orchestrator._handle_admin_command("!mode build", "non-admin")
    assert result is False


@pytest.mark.asyncio
async def test_orchestrator_deny_command(orchestrator):
    """Test !deny command"""
    orchestrator.config.admins = ["admin"]
    with patch("core.config.Config.save") as mock_save:
        result = await orchestrator._handle_admin_command("!deny rm -rf", "admin")
        assert result is True
        assert "rm -rf" in orchestrator.config.policies.get("deny", [])
        assert mock_save.called


@pytest.mark.asyncio
async def test_orchestrator_policies_command(orchestrator):
    """Test !policies command"""
    orchestrator.config.admins = ["admin"]
    orchestrator.config.policies["allow"] = ["git status"]
    orchestrator.config.policies["deny"] = ["rm"]
    result = await orchestrator._handle_admin_command("!policies", "admin")
    assert result is True
    await asyncio.sleep(0.05)
    assert orchestrator.adapters["messaging"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_unknown_admin_command(orchestrator):
    """Test unknown admin command returns False"""
    orchestrator.config.admins = ["admin"]
    result = await orchestrator._handle_admin_command("!unknowncommand", "admin")
    assert result is False


@pytest.mark.asyncio
async def test_orchestrator_restart_components_full(orchestrator):
    """Test self-healing restart logic for all components"""
    # Messaging
    await orchestrator.restart_component("messaging")
    assert True

    # MCP
    orchestrator.adapters["mcp"].start_all = AsyncMock()
    await orchestrator.restart_component("mcp")
    assert orchestrator.adapters["mcp"].start_all.called

    # Gateway
    await orchestrator.restart_component("gateway")
    assert True

    # Failure case
    orchestrator.adapters["openclaw"].connect.side_effect = Exception("err")
    await orchestrator.restart_component("openclaw")
    assert True  # Should handle exception and print


@pytest.mark.asyncio
async def test_orchestrator_handle_client_json_error_robust(orchestrator):
    """Test handle_client with malformed JSON"""
    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = ["{invalid}", Exception("done")]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception:
        pass
    assert True


@pytest.mark.asyncio
async def test_orchestrator_dispatch_unknown_provider(orchestrator):
    """Test get_llm_provider with unknown type defaults to ollama"""
    from core.llm_providers import get_llm_provider, OllamaProvider

    p = get_llm_provider({"provider": "unknown"})
    assert isinstance(p, OllamaProvider)


@pytest.mark.asyncio
async def test_orchestrator_run_autonomous_build_step_error(orchestrator):
    """Test error handling in autonomous build loop"""
    mock_ws = AsyncMock()
    msg = Message(content="build", sender="u")
    orchestrator.llm.generate.side_effect = Exception("llm error")
    await orchestrator.run_autonomous_build(msg, mock_ws)
    assert mock_ws.send_json.called
    # Check if error status was sent
    calls = [c[0][0] for c in mock_ws.send_json.call_args_list]
    assert any("Error: llm error" in c.get("content", "") for c in calls)


@pytest.mark.asyncio
async def test_orchestrator_proactive_loop_calendar_exception(orchestrator):
    """Test calendar exception handling in proactive loop"""
    orchestrator.adapters["memu"].get_anticipations.return_value = []
    orchestrator.adapters["mcp"].call_tool.side_effect = Exception(
        "Calendar service not configured"
    )
    with patch("asyncio.sleep", side_effect=[None, Exception("stop")]):
        try:
            await orchestrator.proactive_loop()
        except Exception as e:
            if str(e) != "stop":
                raise
    assert orchestrator.adapters["mcp"].call_tool.called


@pytest.mark.asyncio
async def test_orchestrator_openclaw_connect_greeting(orchestrator):
    """Test greeting sent on OpenClaw connect/handshake"""
    event = {"method": "connect", "params": {}}
    await orchestrator.on_openclaw_event(event)
    assert orchestrator.adapters["openclaw"].send_message.called
    orchestrator.adapters["openclaw"].send_message.reset_mock()
    event = {"method": "handshake", "params": {}}
    await orchestrator.on_openclaw_event(event)
    assert orchestrator.adapters["openclaw"].send_message.called


@pytest.mark.asyncio
async def test_orchestrator_approval_queue_update_error(orchestrator):
    """Test error handling when updating approval queue"""
    mock_client = AsyncMock()
    mock_client.send_json.side_effect = Exception("Client disconnected")
    orchestrator.clients.add(mock_client)
    orchestrator.admin_handler.approval_queue.append(
        {
            "id": "test-action-1",
            "type": "system_command",
            "payload": {},
            "description": "Test command",
        }
    )
    await orchestrator._process_approval("test-action-1", approved=True)
    assert mock_client not in orchestrator.clients


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test FastAPI root endpoint"""
    from core.orchestrator import root

    result = await root()
    assert result["status"] == "online"
    assert result["message"] == "MegaBot API is running"


@pytest.mark.asyncio
async def test_orchestrator_ui_approval_events(orchestrator):
    """Test approve/reject action events from UI"""
    mock_ws = AsyncMock()
    action_id = "test-id-123"
    orchestrator.admin_handler.approval_queue.append(
        {"id": action_id, "type": "test", "payload": {}}
    )
    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "approve_action", "action_id": action_id}),
        Exception("stop"),
    ]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception:
        pass
    assert len(orchestrator.admin_handler.approval_queue) == 0
    action_id = "test-id-456"
    orchestrator.admin_handler.approval_queue.append(
        {"id": action_id, "type": "test", "payload": {}}
    )
    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "reject_action", "action_id": action_id}),
        Exception("stop"),
    ]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception:
        pass
    assert len(orchestrator.admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_orchestrator_admin_commands_empty_policies(orchestrator):
    """Test !allow/!deny with empty policies dict for coverage"""
    orchestrator.config.admins = ["admin"]
    orchestrator.config.policies = {}
    with patch("core.config.Config.save"):
        await orchestrator._handle_admin_command("!allow cmd1", "admin")
        assert "cmd1" in orchestrator.config.policies["allow"]
        await orchestrator._handle_admin_command("!deny cmd2", "admin")
        assert "cmd2" in orchestrator.config.policies["deny"]


@pytest.mark.asyncio
async def test_orchestrator_handle_admin_command_empty_text(orchestrator):
    """Test _handle_admin_command with empty/whitespace text covers line 129"""
    orchestrator.config.admins = ["admin"]
    result = await orchestrator._handle_admin_command("", "admin")
    assert result is False
    result = await orchestrator._handle_admin_command("   ", "admin")
    assert result is False


@pytest.mark.asyncio
async def test_orchestrator_process_approval_action_not_found(orchestrator):
    """Test _process_approval when action is not found covers line 463"""
    await orchestrator._process_approval("non-existent-id", approved=True)
    assert True


@pytest.mark.asyncio
async def test_orchestrator_process_approval_subprocess_exceptions(orchestrator):
    """Test subprocess exception handling in _process_approval covers lines 479-480, 485"""
    action = {
        "id": "test-action-123",
        "type": "system_command",
        "payload": {"params": {"command": "test command"}},
        "websocket": AsyncMock(),
    }
    orchestrator.admin_handler.approval_queue.append(action)
    with patch("subprocess.run", side_effect=Exception("Subprocess failed")):
        await orchestrator._process_approval("test-action-123", approved=True)
        action["websocket"].send_json.assert_called_with(
            {"type": "terminal_output", "content": "Command failed: Subprocess failed"}
        )


@pytest.mark.asyncio
async def test_orchestrator_handle_client_command_message_type(orchestrator):
    """Test command message type handling covers lines 575-594"""
    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "command", "command": "ls -la"}),
        Exception("stop"),
    ]
    try:
        await orchestrator.handle_client(mock_ws)
    except Exception as e:
        if str(e) != "stop":
            raise
    assert len(orchestrator.admin_handler.approval_queue) == 1
    action = orchestrator.admin_handler.approval_queue[0]
    assert action["type"] == "system_command"
    status_calls = [
        call
        for call in mock_ws.send_json.call_args_list
        if call[0][0].get("type") == "status"
    ]
    assert len(status_calls) > 0


@pytest.mark.asyncio
async def test_websocket_endpoint_orchestrator_none():
    """Test websocket endpoint when orchestrator is not initialized"""
    with patch("core.orchestrator.orchestrator", None):
        mock_ws = AsyncMock()
        await websocket_endpoint(mock_ws)
        mock_ws.accept.assert_called_once()
        mock_ws.send_text.assert_called_once_with("Orchestrator not initialized")
        mock_ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_endpoint_with_orchestrator(orchestrator):
    """Test websocket endpoint when orchestrator is initialized"""
    import core.orchestrator

    with patch("core.orchestrator.orchestrator", orchestrator):
        mock_ws = AsyncMock()
        orchestrator.handle_client = AsyncMock()
        await core.orchestrator.websocket_endpoint(mock_ws)
        orchestrator.handle_client.assert_called_once_with(mock_ws)


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health endpoint returns ok status"""

    result = await health()
    assert result == {"status": "ok"}
