import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.admin_handler import AdminHandler
from core.interfaces import Message


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator with all required attributes."""
    orc = MagicMock()
    orc.config = MagicMock()
    orc.config.admins = ["admin_user", "admin2"]
    orc.config.policies = {"allow": [], "deny": []}
    orc.config.save = MagicMock()
    orc.config.system = MagicMock()
    orc.config.system.admin_phone = "+1234567890"

    orc.memory = AsyncMock()
    orc.memory.chat_forget = AsyncMock()
    orc.memory.link_identity = AsyncMock()
    orc.memory.get_unified_id = AsyncMock(return_value="unified_id_123")
    orc.memory.chat_read = AsyncMock(
        return_value=[
            {"role": "user", "content": "Test message"},
            {"role": "assistant", "content": "Response"},
        ]
    )
    orc.memory.backup_database = AsyncMock(return_value="Backup completed")

    orc.adapters = {
        "messaging": AsyncMock(),
        "gateway": AsyncMock(),
    }
    orc.adapters["messaging"].voice_adapter = AsyncMock()
    orc.adapters["messaging"].voice_adapter.make_call = AsyncMock()

    orc.llm = AsyncMock()
    orc.llm.generate = AsyncMock(return_value="Test summary")

    orc.rag = MagicMock()
    orc.rag.build_index = AsyncMock()

    orc.health_monitor = AsyncMock()
    orc.health_monitor.get_system_health = AsyncMock(
        return_value={
            "memory": {"status": "up"},
            "llm": {"status": "up"},
            "adapters": {"status": "up"},
        }
    )

    orc.send_platform_message = AsyncMock()
    orc.mode = "plan"
    orc.loki = AsyncMock()
    orc.loki.activate = AsyncMock()

    return orc


@pytest.fixture
def admin_handler(mock_orchestrator):
    """Create AdminHandler instance with mocked orchestrator."""
    return AdminHandler(mock_orchestrator)


@pytest.mark.asyncio
async def test_init(admin_handler, mock_orchestrator):
    """Test AdminHandler initialization."""
    assert admin_handler.orchestrator == mock_orchestrator
    assert admin_handler.approval_queue == []


@pytest.mark.asyncio
async def test_handle_command_non_admin(admin_handler, mock_orchestrator):
    """Test handle_command with non-admin sender."""
    result = await admin_handler.handle_command("!mode build", "non_admin_user")
    assert result is False
    mock_orchestrator.config.admins = None  # Test no admins case
    result = await admin_handler.handle_command("!mode build", "user")
    assert result is False


@pytest.mark.asyncio
async def test_handle_command_invalid_command(admin_handler):
    """Test handle_command with invalid command."""
    result = await admin_handler.handle_command("!invalid", "admin_user")
    assert result is False


@pytest.mark.asyncio
async def test_handle_command_empty(admin_handler):
    """Test handle_command with empty text."""
    result = await admin_handler.handle_command("", "admin_user")
    assert result is False


@pytest.mark.asyncio
async def test_handle_approve_with_id(admin_handler):
    """Test _handle_approve with specific action ID."""
    admin_handler.approval_queue = [{"id": "test_action", "description": "Test action"}]
    with patch.object(
        admin_handler, "_process_approval", new_callable=AsyncMock
    ) as mock_process:
        result = await admin_handler._handle_approve(
            ["!approve", "test_action"], "admin", "chat123", "platform"
        )
        assert result is True
        mock_process.assert_called_once_with("test_action", approved=True)


@pytest.mark.asyncio
async def test_handle_approve_last_in_queue(admin_handler):
    """Test _handle_approve with last action in queue."""
    admin_handler.approval_queue = [{"id": "test_action", "description": "Test action"}]
    with patch.object(
        admin_handler, "_process_approval", new_callable=AsyncMock
    ) as mock_process:
        result = await admin_handler._handle_approve(
            ["!approve"], "admin", "chat123", "platform"
        )
        assert result is True
        mock_process.assert_called_once_with("test_action", approved=True)


@pytest.mark.asyncio
async def test_handle_approve_empty_queue(admin_handler):
    """Test _handle_approve with empty queue."""
    result = await admin_handler._handle_approve(
        ["!approve"], "admin", "chat123", "platform"
    )
    assert result is False


@pytest.mark.asyncio
async def test_handle_reject_with_id(admin_handler):
    """Test _handle_reject with specific action ID."""
    admin_handler.approval_queue = [{"id": "test_action", "description": "Test action"}]
    with patch.object(
        admin_handler, "_process_approval", new_callable=AsyncMock
    ) as mock_process:
        result = await admin_handler._handle_reject(
            ["!reject", "test_action"], "admin", "chat123", "platform"
        )
        assert result is True
        mock_process.assert_called_once_with("test_action", approved=False)


@pytest.mark.asyncio
async def test_handle_reject_last_in_queue(admin_handler):
    """Test _handle_reject with last action in queue."""
    admin_handler.approval_queue = [{"id": "test_action", "description": "Test action"}]
    with patch.object(
        admin_handler, "_process_approval", new_callable=AsyncMock
    ) as mock_process:
        result = await admin_handler._handle_reject(
            ["!no"], "admin", "chat123", "platform"
        )
        assert result is True
        mock_process.assert_called_once_with("test_action", approved=False)


@pytest.mark.asyncio
async def test_handle_reject_empty_queue(admin_handler):
    """Test _handle_reject with empty queue."""
    result = await admin_handler._handle_reject(
        ["!reject"], "admin", "chat123", "platform"
    )
    assert result is False


@pytest.mark.asyncio
async def test_handle_allow_new_pattern(admin_handler, mock_orchestrator):
    """Test _handle_allow with new pattern."""
    result = await admin_handler._handle_allow(
        ["!allow", "test pattern"], "admin", "chat123", "platform"
    )
    assert result is True
    assert "test pattern" in mock_orchestrator.config.policies["allow"]
    mock_orchestrator.config.save.assert_called_once()


@pytest.mark.asyncio
async def test_handle_allow_duplicate_pattern(admin_handler, mock_orchestrator):
    """Test _handle_allow with duplicate pattern."""
    mock_orchestrator.config.policies["allow"] = ["test pattern"]
    result = await admin_handler._handle_allow(
        ["!allow", "test pattern"], "admin", "chat123", "platform"
    )
    assert result is False
    mock_orchestrator.config.save.assert_not_called()


@pytest.mark.asyncio
async def test_handle_allow_no_pattern(admin_handler):
    """Test _handle_allow without pattern."""
    result = await admin_handler._handle_allow(
        ["!allow"], "admin", "chat123", "platform"
    )
    assert result is False


@pytest.mark.asyncio
async def test_handle_deny_new_pattern(admin_handler, mock_orchestrator):
    """Test _handle_deny with new pattern."""
    result = await admin_handler._handle_deny(
        ["!deny", "bad pattern"], "admin", "chat123", "platform"
    )
    assert result is True
    assert "bad pattern" in mock_orchestrator.config.policies["deny"]
    mock_orchestrator.config.save.assert_called_once()


@pytest.mark.asyncio
async def test_handle_deny_duplicate_pattern(admin_handler, mock_orchestrator):
    """Test _handle_deny with duplicate pattern."""
    mock_orchestrator.config.policies["deny"] = ["bad pattern"]
    result = await admin_handler._handle_deny(
        ["!deny", "bad pattern"], "admin", "chat123", "platform"
    )
    assert result is False
    mock_orchestrator.config.save.assert_not_called()


@pytest.mark.asyncio
async def test_handle_deny_no_pattern(admin_handler):
    """Test _handle_deny without pattern."""
    result = await admin_handler._handle_deny(["!deny"], "admin", "chat123", "platform")
    assert result is False


@pytest.mark.asyncio
async def test_handle_policies(admin_handler, mock_orchestrator):
    """Test _handle_policies displays policies."""
    result = await admin_handler._handle_policies(
        ["!policies"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "Policies:" in call_args.content
    assert "Allow:" in call_args.content
    assert "Deny:" in call_args.content


@pytest.mark.asyncio
async def test_handle_mode_with_mode(admin_handler, mock_orchestrator):
    """Test _handle_mode with mode parameter."""
    result = await admin_handler._handle_mode(
        ["!mode", "build"], "admin", "chat123", "platform"
    )
    assert result is True
    assert mock_orchestrator.mode == "build"
    mock_orchestrator.loki.activate.assert_not_called()


@pytest.mark.asyncio
async def test_handle_mode_loki_mode(admin_handler, mock_orchestrator):
    """Test _handle_mode with loki mode triggers activation."""
    result = await admin_handler._handle_mode(
        ["!mode", "loki"], "admin", "chat123", "platform"
    )
    assert result is True
    assert mock_orchestrator.mode == "loki"
    mock_orchestrator.loki.activate.assert_called_once_with("Auto-trigger from chat")


@pytest.mark.asyncio
async def test_handle_mode_no_mode(admin_handler):
    """Test _handle_mode without mode parameter."""
    result = await admin_handler._handle_mode(["!mode"], "admin", "chat123", "platform")
    assert result is False


@pytest.mark.asyncio
async def test_handle_history_clean_with_chat(admin_handler, mock_orchestrator):
    """Test _handle_history_clean with specific chat ID."""
    result = await admin_handler._handle_history_clean(
        ["!history_clean", "chat456"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.memory.chat_forget.assert_called_once_with(
        "chat456", max_history=0
    )
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "History cleaned for chat: chat456" in call_args.content


@pytest.mark.asyncio
async def test_handle_history_clean_current_chat(admin_handler, mock_orchestrator):
    """Test _handle_history_clean with current chat."""
    result = await admin_handler._handle_history_clean(
        ["!history_clean"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.memory.chat_forget.assert_called_once_with(
        "chat123", max_history=0
    )


@pytest.mark.asyncio
async def test_handle_link_with_name(admin_handler, mock_orchestrator):
    """Test _handle_link with identity name."""
    result = await admin_handler._handle_link(
        ["!link", "testuser"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.memory.link_identity.assert_called_once_with(
        "testuser", "platform", "admin"
    )
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "Identity Linked:" in call_args.content
    assert "testuser" in call_args.content


@pytest.mark.asyncio
async def test_handle_link_no_name(admin_handler):
    """Test _handle_link without name."""
    result = await admin_handler._handle_link(["!link"], "admin", "chat123", "platform")
    assert result is False


@pytest.mark.asyncio
async def test_handle_whoami(admin_handler, mock_orchestrator):
    """Test _handle_whoami shows identity info."""
    result = await admin_handler._handle_whoami(
        ["!whoami"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.memory.get_unified_id.assert_called_once_with("platform", "admin")
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "Identity Info:" in call_args.content
    assert "unified_id_123" in call_args.content


@pytest.mark.asyncio
async def test_handle_backup(admin_handler, mock_orchestrator):
    """Test _handle_backup triggers backup."""
    result = await admin_handler._handle_backup(
        ["!backup"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.memory.backup_database.assert_called_once()
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "Backup Triggered:" in call_args.content
    assert "Backup completed" in call_args.content


@pytest.mark.asyncio
async def test_handle_briefing_success(admin_handler, mock_orchestrator):
    """Test _handle_briefing with valid config."""
    result = await admin_handler._handle_briefing(
        ["!briefing"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.send_platform_message.assert_called()


@pytest.mark.asyncio
async def test_handle_briefing_no_phone(admin_handler, mock_orchestrator):
    """Test _handle_briefing without admin phone."""
    mock_orchestrator.config.system.admin_phone = None
    result = await admin_handler._handle_briefing(
        ["!briefing"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "No admin phone" in call_args.content


@pytest.mark.asyncio
async def test_handle_briefing_no_voice_adapter(admin_handler, mock_orchestrator):
    """Test _handle_briefing without voice adapter."""
    mock_orchestrator.adapters["messaging"].voice_adapter = None
    result = await admin_handler._handle_briefing(
        ["!briefing"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "No admin phone or voice adapter" in call_args.content


@pytest.mark.asyncio
async def test_handle_rag_rebuild(admin_handler, mock_orchestrator):
    """Test _handle_rag_rebuild rebuilds index."""
    result = await admin_handler._handle_rag_rebuild(
        ["!rag_rebuild"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.rag.build_index.assert_called_once_with(force_rebuild=True)
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "RAG Index rebuilt" in call_args.content


@pytest.mark.asyncio
async def test_handle_health(admin_handler, mock_orchestrator):
    """Test _handle_health shows system health."""
    result = await admin_handler._handle_health(
        ["!health"], "admin", "chat123", "platform"
    )
    assert result is True
    mock_orchestrator.health_monitor.get_system_health.assert_called_once()
    mock_orchestrator.send_platform_message.assert_called_once()
    call_args = mock_orchestrator.send_platform_message.call_args[0][0]
    assert "System Health:" in call_args.content
    assert "✅ **Memory**" in call_args.content
    assert "✅ **Llm**" in call_args.content


@pytest.mark.asyncio
async def test_process_approval_approved(admin_handler):
    """Test _process_approval with approved action."""
    admin_handler.approval_queue = [{"id": "test_action", "description": "Test action"}]
    with patch.object(
        admin_handler, "_execute_approved_action", new_callable=AsyncMock
    ) as mock_execute:
        await admin_handler._process_approval("test_action", approved=True)
        assert len(admin_handler.approval_queue) == 0
        mock_execute.assert_called_once_with(
            {"id": "test_action", "description": "Test action"}
        )


@pytest.mark.asyncio
async def test_process_approval_rejected(admin_handler):
    """Test _process_approval with rejected action."""
    admin_handler.approval_queue = [{"id": "test_action", "description": "Test action"}]
    await admin_handler._process_approval("test_action", approved=False)
    assert len(admin_handler.approval_queue) == 0


@pytest.mark.asyncio
async def test_process_approval_invalid_id(admin_handler):
    """Test _process_approval with invalid action ID."""
    admin_handler.approval_queue = [{"id": "test_action", "description": "Test action"}]
    await admin_handler._process_approval("invalid_id", approved=True)
    assert len(admin_handler.approval_queue) == 1


@pytest.mark.asyncio
async def test_execute_approved_action(admin_handler):
    """Test _execute_approved_action logs the action."""
    action = {"id": "test_action", "description": "Test action"}
    await admin_handler._execute_approved_action(action)
    # Currently just prints, so no assertions needed beyond no exceptions


@pytest.mark.asyncio
async def test_trigger_voice_briefing_with_history(admin_handler, mock_orchestrator):
    """Test _trigger_voice_briefing with chat history."""
    await admin_handler._trigger_voice_briefing("+1234567890", "chat123", "platform")
    mock_orchestrator.memory.chat_read.assert_called_once_with("chat123", limit=20)
    mock_orchestrator.llm.generate.assert_called_once()
    mock_orchestrator.adapters["messaging"].voice_adapter.make_call.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_voice_briefing_no_history(admin_handler, mock_orchestrator):
    """Test _trigger_voice_briefing with no chat history."""
    mock_orchestrator.memory.chat_read.return_value = []
    await admin_handler._trigger_voice_briefing("+1234567890", "chat123", "platform")
    mock_orchestrator.adapters[
        "messaging"
    ].voice_adapter.make_call.assert_called_once_with(
        "+1234567890", "This is Mega Bot. No recent activity to report."
    )


@pytest.mark.asyncio
async def test_trigger_voice_briefing_exception(admin_handler, mock_orchestrator):
    """Test _trigger_voice_briefing handles exceptions."""
    mock_orchestrator.memory.chat_read.side_effect = Exception("Database error")
    await admin_handler._trigger_voice_briefing("+1234567890", "chat123", "platform")
    # Should not raise exception, just log it
