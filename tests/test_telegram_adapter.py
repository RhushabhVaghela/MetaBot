"""
Tests for Telegram Adapter
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from adapters.messaging import MessageType
from adapters.telegram_adapter import (
    TelegramAdapter,
    ParseMode,
    ChatType,
    TelegramUser,
    TelegramChat,
    TelegramMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardButton,
    ReplyKeyboardMarkup,
    ForceReplyMarkup,
)


class TestTelegramDataClasses:
    """Test Telegram data classes"""

    def test_telegram_user_creation(self):
        user = TelegramUser.from_dict(
            {
                "id": 12345,
                "is_bot": False,
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
                "language_code": "en",
            }
        )
        assert user.id == 12345
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.username == "johndoe"
        assert user.language_code == "en"

    def test_telegram_chat_creation(self):
        chat = TelegramChat.from_dict(
            {
                "id": 12345,
                "type": "private",
                "title": "Test Chat",
                "username": "user",
                "first_name": "First",
                "last_name": "Last",
            }
        )
        assert chat.id == 12345
        assert chat.type == ChatType.PRIVATE
        assert chat.title == "Test Chat"
        assert chat.username == "user"
        assert chat.first_name == "First"
        assert chat.last_name == "Last"

    def test_telegram_message_creation(self):
        msg_dict = {
            "message_id": 1,
            "date": 1699000000,
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "first_name": "User"},
            "text": "hello",
            "caption": "capt",
            "photo": [{"file_id": "p1"}],
            "document": {"file_id": "d1"},
            "audio": {"file_id": "a1"},
            "voice": {"file_id": "v1"},
            "video": {"file_id": "vid1"},
            "location": {"latitude": 1.0, "longitude": 2.0},
            "contact": {"phone_number": "123"},
            "reply_to_message": {
                "message_id": 0,
                "date": 1699000000,
                "chat": {"id": 123, "type": "private"},
                "text": "original",
            },
            "entities": [{"type": "bold"}],
            "callback_query": {"id": "cq1"},
        }
        msg = TelegramMessage.from_dict(msg_dict)
        assert msg.message_id == 1
        assert msg.text == "hello"
        assert msg.caption == "capt"
        assert len(msg.photo) == 1
        assert msg.document["file_id"] == "d1"
        assert msg.audio["file_id"] == "a1"
        assert msg.voice["file_id"] == "v1"
        assert msg.video["file_id"] == "vid1"
        assert msg.location["latitude"] == 1.0
        assert msg.contact["phone_number"] == "123"
        assert msg.reply_to_message.text == "original"
        assert len(msg.entities) == 1
        assert msg.callback_query["id"] == "cq1"

    def test_inline_keyboard(self):
        btn = InlineKeyboardButton(
            text="T",
            callback_data="C",
            url="U",
            login_url={"url": "L"},
            switch_inline_query="S",
            switch_inline_query_current_chat="SC",
            callback_game={},
            pay=True,
        )
        d = btn.to_dict()
        assert d["text"] == "T"
        assert d["callback_data"] == "C"
        assert d["url"] == "U"
        assert d["login_url"] == {"url": "L"}
        assert d["switch_inline_query"] == "S"
        assert d["switch_inline_query_current_chat"] == "SC"
        assert d["callback_game"] == {}
        assert d["pay"] is True

        markup = InlineKeyboardMarkup(inline_keyboard=[[btn]])
        md = markup.to_dict()
        assert len(md["inline_keyboard"]) == 1

    def test_reply_keyboard(self):
        btn = ReplyKeyboardButton(
            text="R", request_contact=True, request_location=True, request_poll={}
        )
        d = btn.to_dict()
        assert d["text"] == "R"
        assert d["request_contact"] is True
        assert d["request_location"] is True
        assert d["request_poll"] == {}

        markup = ReplyKeyboardMarkup(
            keyboard=[[btn]],
            resize_keyboard=True,
            one_time_keyboard=True,
            selective=True,
        )
        md = markup.to_dict()
        assert md["resize_keyboard"] is True
        assert md["one_time_keyboard"] is True
        assert md["selective"] is True

        force = ForceReplyMarkup(selective=True)
        assert force.to_dict() == {"selective": True}


class TestTelegramAdapter:
    """Test Telegram adapter functionality"""

    @pytest.fixture
    def adapter(self):
        return TelegramAdapter(
            bot_token="test_token",
            webhook_url="https://test.com",
            parse_mode=ParseMode.HTML,
            admin_ids=[123],
        )

    @pytest.mark.asyncio
    async def test_initialize_full(self, adapter):
        with (
            patch.object(adapter, "get_me", new_callable=AsyncMock) as mock_me,
            patch.object(
                adapter, "set_webhook", new_callable=AsyncMock
            ) as mock_webhook,
        ):
            mock_me.return_value = {"id": 1, "username": "bot"}
            mock_webhook.return_value = True

            assert await adapter.initialize() is True
            assert adapter.is_initialized is True

            # Test exception in initialize
            adapter.get_me = AsyncMock(side_effect=Exception("API error"))
            assert await adapter.initialize() is False

    @pytest.mark.asyncio
    async def test_initialize_failure_closes_session(self, adapter):
        with patch(
            "adapters.telegram_adapter.aiohttp.ClientSession"
        ) as mock_session_cls:
            session_instance = MagicMock()
            session_instance.close = AsyncMock()
            mock_session_cls.return_value = session_instance
            adapter.get_me = AsyncMock(side_effect=RuntimeError("boom"))
            assert await adapter.initialize() is False
            session_instance.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_methods(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []
            await adapter.get_updates(limit=50, timeout=10, allowed_updates=["message"])
            mock_req.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_methods_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"message_id": 1}

            await adapter.send_message(
                "123",
                "text",
                parse_mode=ParseMode.MARKDOWN_V2,
                entities=[{"type": "bold", "offset": 0, "length": 4}],
                disable_web_page_preview=True,
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                allow_sending_without_reply=True,
                reply_markup=InlineKeyboardMarkup(),
            )

            await adapter.send_photo(
                "123",
                "p",
                caption="c",
                parse_mode=ParseMode.HTML,
                has_spoiler=True,
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                reply_markup=InlineKeyboardMarkup(),
            )

            await adapter.send_document(
                "123",
                "d",
                thumbnail="t",
                caption="c",
                parse_mode=ParseMode.HTML,
                disable_content_type_detection=True,
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                reply_markup=InlineKeyboardMarkup(),
            )

            await adapter.send_audio(
                "123",
                "a",
                caption="c",
                parse_mode=ParseMode.HTML,
                duration=10,
                performer="p",
                title="t",
                thumb="th",
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                reply_markup=InlineKeyboardMarkup(),
            )

            await adapter.send_voice(
                "123",
                "v",
                caption="c",
                parse_mode=ParseMode.HTML,
                duration=10,
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                reply_markup=InlineKeyboardMarkup(),
            )

            await adapter.send_video(
                "123",
                "vid",
                thumbnail="t",
                caption="c",
                parse_mode=ParseMode.HTML,
                has_spoiler=True,
                duration=10,
                width=100,
                height=100,
                supports_streaming=True,
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                reply_markup=InlineKeyboardMarkup(),
            )

            await adapter.send_location(
                "123",
                1.0,
                2.0,
                horizontal_accuracy=1.0,
                live_period=60,
                heading=90,
                proximity_alert_radius=100,
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                reply_markup=InlineKeyboardMarkup(),
            )

            await adapter.send_contact(
                "123",
                "p",
                "f",
                last_name="l",
                vcard="v",
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                reply_markup=InlineKeyboardMarkup(),
            )

            await adapter.send_poll(
                "123",
                "q",
                ["a"],
                is_anonymous=False,
                type_poll="quiz",
                allows_multiple_answers=True,
                correct_option_id=0,
                explanation="e",
                explanation_parse_mode=ParseMode.HTML,
                open_period=10,
                close_date=100,
                is_closed=True,
                disable_notification=True,
                protect_content=True,
                reply_to_message_id=1,
                reply_markup=InlineKeyboardMarkup(),
            )

            assert mock_req.call_count == 9

    @pytest.mark.asyncio
    async def test_edit_delete_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = True
            await adapter.edit_message_text(
                "123",
                1,
                "t",
                parse_mode=ParseMode.HTML,
                entities=[{"type": "italic", "offset": 0, "length": 1}],
                disable_web_page_preview=True,
                inline_message_id="i1",
                reply_markup=InlineKeyboardMarkup(),
            )
            await adapter.delete_message("123", 1)
            assert mock_req.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_mgmt_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = True
            await adapter.create_chat_invite_link(
                "123",
                name="n",
                expire_date=100,
                member_limit=10,
                creates_join_request=True,
            )
            await adapter.export_chat_invite_link("123")
            await adapter.get_chat_member("123", 456)
            await adapter.ban_chat_member(
                "123", 456, until_date=100, revoke_messages=True
            )
            await adapter.unban_chat_member("123", 456, only_if_banned=False)
            await adapter.restrict_chat_member("123", 456, {}, until_date=100)
            await adapter.promote_chat_member(
                "123",
                456,
                is_anonymous=True,
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_manage_topics=True,
                can_post_stories=True,
                can_edit_stories=True,
                can_delete_stories=True,
            )
            await adapter.pin_chat_message("123", 1, disable_notification=True)
            await adapter.unpin_chat_message("123", message_id=1)
            await adapter.forward_message(
                "123", "456", 1, disable_notification=True, protect_content=True
            )

            assert mock_req.call_count == 10

    @pytest.mark.asyncio
    async def test_handle_webhook_full_types(self, adapter):
        msg_handler = AsyncMock()
        adapter.register_message_handler(msg_handler)

        # Test caption message
        webhook_data = {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 456, "first_name": "User"},
                "caption": "capt",
                "photo": [{"file_id": "p1"}],
            },
        }
        result = await adapter.handle_webhook(webhook_data)
        assert result.content == "capt"
        assert result.message_type == MessageType.IMAGE

        # Test error in message handler
        msg_handler.side_effect = Exception("Handler error")
        error_handler = AsyncMock()
        adapter.register_error_handler(error_handler)
        await adapter.handle_webhook(webhook_data)
        error_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_handler_error(self, adapter):
        cb_handler = AsyncMock(side_effect=Exception("CB error"))
        adapter.register_callback_handler(cb_handler)
        webhook_data = {
            "update_id": 2,
            "callback_query": {
                "id": "cb1",
                "from": {"id": 456, "first_name": "User"},
                "data": "data1",
            },
        }
        # Should catch exception and proceed to answer
        with patch.object(
            adapter, "answer_callback_query", new_callable=AsyncMock
        ) as mock_ans:
            await adapter.handle_webhook(webhook_data)
            mock_ans.assert_called_once()

    def test_get_message_type_all(self, adapter):
        assert (
            adapter._get_message_type({"photo": [{"file_id": "1"}]})
            == MessageType.IMAGE
        )
        assert (
            adapter._get_message_type({"video": {"file_id": "1"}}) == MessageType.VIDEO
        )
        assert (
            adapter._get_message_type({"audio": {"file_id": "1"}}) == MessageType.AUDIO
        )
        assert (
            adapter._get_message_type({"document": {"file_id": "1"}})
            == MessageType.DOCUMENT
        )
        assert (
            adapter._get_message_type({"voice": {"file_id": "1"}}) == MessageType.AUDIO
        )
        assert (
            adapter._get_message_type({"location": {"lat": 0}}) == MessageType.LOCATION
        )
        assert (
            adapter._get_message_type({"contact": {"phone": "1"}})
            == MessageType.CONTACT
        )
        assert adapter._get_message_type({"poll": {}}) == MessageType.TEXT
        assert adapter._get_message_type({}) == MessageType.TEXT

    @pytest.mark.asyncio
    async def test_make_request_fail(self, adapter):
        adapter.session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.json = AsyncMock(return_value={"description": "error"})
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()
        adapter.session.post.return_value = mock_context

        assert await adapter._make_request("test") is None

        # Test generic exception in request
        adapter.session.post.side_effect = Exception("Conn error")
        assert await adapter._make_request("test") is None

    def test_generate_id_token(self, adapter):
        assert len(adapter._generate_id()) == 36

    @pytest.mark.asyncio
    async def test_error_handlers(self, adapter):
        # handle_webhook exception
        assert await adapter.handle_webhook(None) is None
        assert await adapter.handle_webhook({}) is None

        # message handler error (already tested, but making sure)
        adapter.register_message_handler(AsyncMock(side_effect=ValueError("Bad value")))
        webhook_data = {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 456, "first_name": "User"},
                "text": "hello",
            },
        }
        # Should not raise
        await adapter.handle_webhook(webhook_data)

    @pytest.mark.asyncio
    async def test_webhook_no_message(self, adapter):
        assert await adapter.handle_webhook({"update_id": 1}) is None

    @pytest.mark.asyncio
    async def test_set_webhook_fail(self, adapter):
        adapter.webhook_url = None
        assert await adapter.set_webhook() is False

    @pytest.mark.asyncio
    async def test_set_webhook_success_payload(self, adapter):
        adapter._generate_secret_token = MagicMock(return_value="secret123")
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"ok": True}
            assert await adapter.set_webhook() is True
            mock_req.assert_awaited_once_with(
                "setWebhook",
                {
                    "url": "https://test.com/webhooks/telegram",
                    "secret_token": "secret123",
                },
            )

    @pytest.mark.asyncio
    async def test_send_methods_errors(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("error")
            assert await adapter.send_message("1", "t") is None
            assert await adapter.send_photo("1", "p") is None
            assert await adapter.send_document("1", "d") is None
            assert await adapter.send_audio("1", "a") is None
            assert await adapter.send_voice("1", "v") is None
            assert await adapter.send_video("1", "vi") is None
            assert await adapter.send_location("1", 0, 0) is None
            assert await adapter.send_contact("1", "p", "f") is None
            assert await adapter.send_poll("1", "q", ["a"]) is None
            assert await adapter.edit_message_text("1", 1, "t") is None
            assert await adapter.delete_message("1", 1) is False
            assert await adapter.create_chat_invite_link("1") is None
            assert await adapter.export_chat_invite_link("1") is None
            assert await adapter.get_chat("1") is None
            assert await adapter.get_chat_administrators("1") == []
            assert await adapter.get_chat_members_count("1") == 0
            assert await adapter.get_chat_member("1", 2) is None
            assert await adapter.ban_chat_member("1", 2) is False
            assert await adapter.unban_chat_member("1", 2) is False
            assert await adapter.restrict_chat_member("1", 2, {}) is False
            assert await adapter.promote_chat_member("1", 2) is False
            assert await adapter.pin_chat_message("1", 1) is False
            assert await adapter.unpin_chat_message("1", 1) is False
            assert await adapter.leave_chat("1") is False
            assert await adapter.forward_message("1", "2", 1) is None
            assert await adapter.answer_callback_query("1") is False

    @pytest.mark.asyncio
    async def test_make_request_success(self, adapter):
        adapter.session = MagicMock()
        response = MagicMock()
        response.status = 200
        response.json = AsyncMock(return_value={"result": {"id": 1}})
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        context.__aexit__ = AsyncMock(return_value=None)
        adapter.session.post.return_value = context
        result = await adapter._make_request("getMe", {"test": 1})
        assert result == {"id": 1}
        adapter.session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_without_session(self, adapter):
        adapter.session = None
        assert await adapter._make_request("anything") is None

    @pytest.mark.asyncio
    async def test_handle_webhook_callback_only_sync_handler(self, adapter):
        captured = {}

        def sync_callback(data):
            captured["id"] = data["id"]

        adapter.register_callback_handler(sync_callback)
        webhook_data = {
            "update_id": 42,
            "callback_query": {
                "id": "cb_sync",
                "from": {"id": 999, "first_name": "Sync"},
                "data": "payload",
            },
        }
        with patch.object(
            adapter, "answer_callback_query", new_callable=AsyncMock
        ) as mock_answer:
            result = await adapter.handle_webhook(webhook_data)
            assert result is None
            assert captured["id"] == "cb_sync"
            mock_answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_webhook_sync_message_handler_and_error(self, adapter):
        sync_called = {}

        def sync_handler(message):
            sync_called["content"] = message.content

        error_called = {}

        def sync_error_handler(exc, message):
            error_called["msg_id"] = message.id
            error_called["error"] = str(exc)

        failing_handler = AsyncMock(side_effect=ValueError("handler boom"))
        adapter.register_message_handler(sync_handler)
        adapter.register_message_handler(failing_handler)
        adapter.register_error_handler(sync_error_handler)

        webhook_data = {
            "update_id": 100,
            "message": {
                "message_id": 55,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 321, "first_name": "Tester"},
                "text": "sync message",
            },
        }
        result = await adapter.handle_webhook(webhook_data)
        assert result.content == "sync message"
        assert adapter.message_cache[result.id]["chat_id"] == "123"
        assert sync_called["content"] == "sync message"
        assert error_called["msg_id"] == result.id
        assert "handler boom" in error_called["error"]

    @pytest.mark.asyncio
    async def test_initialize_make_request_exception(self, adapter):
        """Test initialize method exception handling in _make_request"""
        with patch.object(
            adapter, "_make_request", side_effect=Exception("API failed")
        ):
            result = await adapter.initialize()
            assert result is False

    @pytest.mark.asyncio
    async def test_shutdown_session_close_exception(self, adapter):
        """Test shutdown method exception handling in session.close"""
        adapter.session = MagicMock()
        adapter.session.close = AsyncMock(side_effect=Exception("close failed"))
        await adapter.shutdown()
        assert adapter.session is None
        assert adapter.is_initialized is False

    @pytest.mark.asyncio
    async def test_get_me_request_exception(self, adapter):
        """Test get_me method exception handling"""
        with patch.object(
            adapter, "_make_request", side_effect=Exception("getMe failed")
        ):
            result = await adapter.get_me()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_updates_request_exception(self, adapter):
        """Test get_updates method exception handling"""
        with patch.object(
            adapter, "_make_request", side_effect=Exception("getUpdates failed")
        ):
            result = await adapter.get_updates()
            assert result == []

    @pytest.mark.asyncio
    async def test_delete_webhook_request_exception(self, adapter):
        """Test delete_webhook method exception handling"""
        with patch.object(
            adapter, "_make_request", side_effect=Exception("deleteWebhook failed")
        ):
            result = await adapter.delete_webhook()
            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_request_exception(self, adapter):
        """Test send_message method exception handling"""
        with patch.object(
            adapter, "_make_request", side_effect=Exception("sendMessage failed")
        ):
            result = await adapter.send_message(chat_id="123", text="test")
            assert result is None

    @pytest.mark.asyncio
    async def test_edit_message_text_request_exception(self, adapter):
        """Test edit_message_text method exception handling"""
        with patch.object(
            adapter, "_make_request", side_effect=Exception("editMessageText failed")
        ):
            result = await adapter.edit_message_text(
                chat_id="123", message_id=456, text="edited"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_answer_callback_query_request_exception(self, adapter):
        """Test answer_callback_query method exception handling"""
        with patch.object(
            adapter,
            "_make_request",
            side_effect=Exception("answerCallbackQuery failed"),
        ):
            result = await adapter.answer_callback_query("cb123")
            assert result is False

    @pytest.mark.asyncio
    async def test_create_chat_invite_link_request_exception(self, adapter):
        """Test create_chat_invite_link method exception handling"""
        with patch.object(
            adapter,
            "_make_request",
            side_effect=Exception("createChatInviteLink failed"),
        ):
            result = await adapter.create_chat_invite_link("chat123")
            assert result is None

    @pytest.mark.asyncio
    async def test_promote_chat_member_request_exception(self, adapter):
        """Test promote_chat_member method exception handling"""
        with patch.object(
            adapter, "_make_request", side_effect=Exception("promoteChatMember failed")
        ):
            result = await adapter.promote_chat_member("chat123", 456)
            assert result is False

    @pytest.mark.asyncio
    async def test_handle_webhook_exception_in_callback_handler(self, adapter):
        """Test handle_webhook exception in callback handler"""

        def failing_sync_handler(data):
            raise Exception("callback handler failed")

        adapter.register_callback_handler(failing_sync_handler)
        webhook_data = {
            "update_id": 42,
            "callback_query": {
                "id": "cb_fail",
                "from": {"id": 999, "first_name": "Fail"},
                "data": "payload",
            },
        }
        with patch.object(adapter, "answer_callback_query", new_callable=AsyncMock):
            result = await adapter.handle_webhook(webhook_data)
            assert result is None

    @pytest.mark.asyncio
    async def test_handle_webhook_exception_in_message_handler(self, adapter):
        """Test handle_webhook exception in message handler"""

        def failing_sync_handler(message):
            raise Exception("message handler failed")

        adapter.register_message_handler(failing_sync_handler)
        webhook_data = {
            "update_id": 100,
            "message": {
                "message_id": 55,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 321, "first_name": "Tester"},
                "text": "failing message",
            },
        }
        result = await adapter.handle_webhook(webhook_data)
        assert result is not None  # Message is still processed, handler just fails

    @pytest.mark.asyncio
    async def test_get_message_type_all_cases(self, adapter):
        """Test _get_message_type covers all message types"""
        # Photo
        msg = {"photo": [{"file_id": "photo1"}]}
        assert adapter._get_message_type(msg) == MessageType.IMAGE

        # Video
        msg = {"video": {"file_id": "video1"}}
        assert adapter._get_message_type(msg) == MessageType.VIDEO

        # Audio
        msg = {"audio": {"file_id": "audio1"}}
        assert adapter._get_message_type(msg) == MessageType.AUDIO

        # Document
        msg = {"document": {"file_id": "doc1"}}
        assert adapter._get_message_type(msg) == MessageType.DOCUMENT

        # Voice
        msg = {"voice": {"file_id": "voice1"}}
        assert adapter._get_message_type(msg) == MessageType.AUDIO

        # Location
        msg = {"location": {"latitude": 1.0, "longitude": 2.0}}
        assert adapter._get_message_type(msg) == MessageType.LOCATION

        # Contact
        msg = {"contact": {"phone_number": "123"}}
        assert adapter._get_message_type(msg) == MessageType.CONTACT

        # Poll
        msg = {"poll": {"question": "test"}}
        assert adapter._get_message_type(msg) == MessageType.TEXT

        # Text (default)
        msg = {"text": "hello"}
        assert adapter._get_message_type(msg) == MessageType.TEXT

    @pytest.mark.asyncio
    async def test_get_updates_with_offset(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []
            await adapter.get_updates(
                limit=50, timeout=10, offset=100, allowed_updates=["message"]
            )
            mock_req.assert_called_once()
            call_args = mock_req.call_args[0][1]  # Second positional arg is data
            assert call_args["offset"] == 100

    @pytest.mark.asyncio
    async def test_delete_webhook_success(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = True
            result = await adapter.delete_webhook()
            assert result is True
            mock_req.assert_called_once_with("deleteWebhook")

    @pytest.mark.asyncio
    async def test_answer_callback_query_with_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = True
            result = await adapter.answer_callback_query(
                "cb123",
                text="Processing...",
                show_alert=True,
                url="http://example.com",
                cache_time=30,
            )
            assert result is True
            call_args = mock_req.call_args[0][1]
            assert call_args["text"] == "Processing..."
            assert call_args["show_alert"] is True
            assert call_args["url"] == "http://example.com"
            assert call_args["cache_time"] == 30

    @pytest.mark.asyncio
    async def test_get_chat_administrators_success(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [{"user": {"id": 1}}]
            result = await adapter.get_chat_administrators("chat123")
            assert result == [{"user": {"id": 1}}]

    @pytest.mark.asyncio
    async def test_get_chat_members_count_success(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = 42
            result = await adapter.get_chat_members_count("chat123")
            assert result == 42

    @pytest.mark.asyncio
    async def test_leave_chat_success(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = True
            result = await adapter.leave_chat("chat123")
            assert result is True

    @pytest.mark.asyncio
    async def test_make_request_json_exception_falls_to_text(self, adapter):
        adapter.session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.json = AsyncMock(side_effect=Exception("Invalid JSON"))
        mock_response.text = AsyncMock(return_value="Bad Request")
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()
        adapter.session.post.return_value = mock_context

        result = await adapter._make_request("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_webhook_error_handler_exception(self, adapter):
        """Test handle_webhook with exception in error handler (lines 1234-1235)"""
        # Register a message handler that fails
        adapter.register_message_handler(
            AsyncMock(side_effect=ValueError("Handler failed"))
        )

        # Register an error handler that also fails
        def failing_error_handler(exc, message):
            raise RuntimeError("Error handler failed")

        adapter.register_error_handler(failing_error_handler)

        webhook_data = {
            "update_id": 100,
            "message": {
                "message_id": 55,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 321, "first_name": "Tester"},
                "text": "test error handler failure",
            },
        }

        # Should catch RuntimeError and proceed (line 1235)
        result = await adapter.handle_webhook(webhook_data)
        assert result is not None

    def test_generate_secret_token(self, adapter):
        """Test _generate_secret_token (line 1290)"""
        token = adapter._generate_secret_token()
        assert len(token) == 32
        assert isinstance(token, str)

    @pytest.mark.asyncio
    async def test_main_execution(self):
        """Test main function execution (lines 1301-1313)"""
        with (
            patch("adapters.telegram_adapter.TelegramAdapter") as mock_adapter_class,
            patch("builtins.print") as mock_print,
        ):
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            mock_adapter.initialize.return_value = True
            mock_adapter.me = {"username": "testbot"}

            from adapters.telegram_adapter import main

            await main()

            mock_adapter_class.assert_called_once()
            mock_adapter.initialize.assert_called_once()
            mock_adapter.register_message_handler.assert_called_once()
            mock_adapter.send_message.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
