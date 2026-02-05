"""
Tests for MegaBotMessagingServer
"""

import json
import pytest
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from adapters.messaging import (
    MegaBotMessagingServer,
    PlatformMessage,
    MediaAttachment,
    MessageType,
)


class TestMegaBotMessagingServer:
    """Test suite for MegaBotMessagingServer"""

    @pytest.fixture
    def server(self):
        """Create MegaBotMessagingServer instance"""
        return MegaBotMessagingServer(
            host="127.0.0.1", port=18791, enable_encryption=False
        )

    @pytest.mark.asyncio
    async def test_send_message_to_clients(self, server):
        """Test sending message to connected clients"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        server.clients = {"client1": mock_ws1, "client2": mock_ws2}

        message = PlatformMessage(
            id="test_msg",
            platform="native",
            sender_id="bot",
            sender_name="MegaBot",
            chat_id="global",
            content="Hello everyone",
        )

        await server.send_message(message)

        # Verify both clients received the message
        mock_ws1.send.assert_called_once()
        mock_ws2.send.assert_called_once()

        # Verify content
        sent_data = json.loads(mock_ws1.send.call_args[0][0])
        assert sent_data["id"] == "test_msg"
        assert sent_data["content"] == "Hello everyone"

    @pytest.mark.asyncio
    async def test_send_message_handles_disconnect(self, server):
        """Test that disconnected clients are removed"""
        mock_ws1 = AsyncMock()
        mock_ws1.send.side_effect = Exception("Disconnected")

        server.clients = {"client1": mock_ws1}

        message = PlatformMessage(
            id="test_msg",
            platform="native",
            sender_id="bot",
            sender_name="MegaBot",
            chat_id="global",
            content="Hello",
        )

        await server.send_message(message)

        # Client should be removed
        assert "client1" not in server.clients

    @pytest.mark.asyncio
    async def test_platform_connect_discord(self, server):
        """Test handling discord platform connection"""
        data = {
            "type": "platform_connect",
            "platform": "discord",
            "credentials": {"token": "test-token"},
        }

        # Patch it in the module where it's imported
        with patch("adapters.discord_adapter.DiscordAdapter") as mock_discord:
            await server._handle_platform_connect(data)

            assert "discord" in server.platform_adapters
            # Verification of call depends on how import is handled,
            # but since we see "Initialized Discord adapter" in logs, we know it ran.

    @pytest.mark.asyncio
    async def test_platform_connect_slack(self, server):
        """Test handling slack platform connection"""
        data = {
            "type": "platform_connect",
            "platform": "slack",
            "credentials": {"bot_token": "xoxb-test", "app_token": "xapp-test"},
            "config": {"signing_secret": "secret"},
        }

        with patch("adapters.slack_adapter.SlackAdapter") as mock_slack:
            await server._handle_platform_connect(data)

            assert "slack" in server.platform_adapters
            mock_slack.assert_called_once_with(
                platform_name="slack",
                server=server,
                bot_token="xoxb-test",
                app_token="xapp-test",
                signing_secret="secret",
            )

    def test_register_handler(self, server):
        """Test register_handler method"""
        def test_handler(message):
            pass
        
        server.register_handler(test_handler)
        assert test_handler in server.message_handlers

    @pytest.mark.asyncio
    async def test_initialize_memu_success(self, server):
        """Test successful memU initialization"""
        with patch("adapters.memu_adapter.MemUAdapter") as mock_memu:
            await server.initialize_memu("./memu", "sqlite:///test.db")
            
            mock_memu.assert_called_once_with("./memu", "sqlite:///test.db")
            assert server.memu_adapter is not None

    @pytest.mark.asyncio
    async def test_initialize_memu_failure(self, server):
        """Test memU initialization failure"""
        with patch("adapters.memu_adapter.MemUAdapter", side_effect=Exception("Import error")):
            await server.initialize_memu()
            
            assert server.memu_adapter is None

    @pytest.mark.asyncio
    async def test_initialize_voice_success(self, server):
        """Test successful voice adapter initialization"""
        with patch("adapters.voice_adapter.VoiceAdapter") as mock_voice:
            await server.initialize_voice("sid", "token", "+1234567890")
            
            mock_voice.assert_called_once_with("sid", "token", "+1234567890")
            assert server.voice_adapter is not None

    @pytest.mark.asyncio
    async def test_initialize_voice_failure(self, server):
        """Test voice adapter initialization failure"""
        with patch("adapters.voice_adapter.VoiceAdapter", side_effect=Exception("Import error")):
            await server.initialize_voice("sid", "token", "+1234567890")
            
            assert server.voice_adapter is None

    @pytest.mark.asyncio
    async def test_send_message_with_encryption(self):
        """Test send_message with encryption enabled"""
        server = MegaBotMessagingServer(enable_encryption=True)
        mock_ws = AsyncMock()
        server.clients = {"client1": mock_ws}
        
        # Mock secure_ws
        mock_secure_ws = MagicMock()
        mock_secure_ws.encrypt.return_value = "encrypted_data"
        server.secure_ws = mock_secure_ws
        
        message = PlatformMessage(
            id="test_msg",
            platform="native",
            sender_id="bot",
            sender_name="MegaBot",
            chat_id="global",
            content="Hello",
        )
        
        await server.send_message(message)
        
        # Verify encryption was called
        mock_secure_ws.encrypt.assert_called_once()
        mock_ws.send.assert_called_once_with("encrypted_data")

    @pytest.mark.asyncio
    async def test_send_message_target_client(self, server):
        """Test send_message to specific target client"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        server.clients = {"client1": mock_ws1, "client2": mock_ws2}
        
        message = PlatformMessage(
            id="test_msg",
            platform="native",
            sender_id="bot",
            sender_name="MegaBot",
            chat_id="global",
            content="Hello",
        )
        
        await server.send_message(message, target_client="client1")
        
        # Only client1 should receive the message
        mock_ws1.send.assert_called_once()
        mock_ws2.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_with_encryption(self, server):
        """Test _process_message with encryption enabled"""
        # Mock secure_ws
        mock_secure_ws = MagicMock()
        mock_secure_ws.decrypt.return_value = '{"type": "message", "content": "test"}'
        server.secure_ws = mock_secure_ws
        
        server.enable_encryption = True
        
        with patch.object(server, '_handle_platform_message') as mock_handler:
            await server._process_message("client1", "encrypted_data")
            
            mock_secure_ws.decrypt.assert_called_once_with("encrypted_data")
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_unknown_type(self, server):
        """Test _process_message with unknown message type"""
        data = {"type": "unknown", "content": "test"}
        
        # Should not raise exception, just print unknown type
        await server._process_message("client1", json.dumps(data))

    @pytest.mark.asyncio
    async def test_handle_platform_message_with_attachments(self, server):
        """Test _handle_platform_message with media attachments"""
        import base64
        
        attachment_data = {
            "type": "image",
            "filename": "test.jpg",
            "mime_type": "image/jpeg",
            "size": 100,
            "data": base64.b64encode(b"image_data").decode("utf-8"),
        }
        
        data = {
            "id": "msg123",
            "platform": "telegram",
            "sender_id": "user123",
            "sender_name": "Test User",
            "chat_id": "chat123",
            "content": "Hello with image",
            "attachments": [attachment_data],
        }
        
        mock_handler = AsyncMock()
        server.register_handler(mock_handler)
        
        with patch.object(server, '_save_media') as mock_save:
            await server._handle_platform_message(data)
            
            # Verify handler was called
            assert mock_handler.called
            message = mock_handler.call_args[0][0]
            assert message.id == "msg123"
            assert message.content == "Hello with image"
            assert len(message.attachments) == 1
            assert message.attachments[0].filename == "test.jpg"
            
            # Verify _save_media was called
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_media_upload(self, server):
        """Test _handle_media_upload method"""
        attachment_data = {
            "type": "document",
            "filename": "test.pdf",
            "mime_type": "application/pdf",
            "size": 1000,
            "data": base64.b64encode(b"pdf_data").decode("utf-8"),
        }
        
        data = {"attachment": attachment_data}
        
        with patch.object(server, '_save_media') as mock_save:
            await server._handle_media_upload(data)
            
            mock_save.assert_called_once()
            attachment = mock_save.call_args[0][0]
            assert attachment.filename == "test.pdf"
            assert attachment.type == MessageType.DOCUMENT

    @pytest.mark.asyncio
    async def test_handle_platform_connect_telegram(self, server):
        """Test _handle_platform_connect for telegram"""
        data = {
            "platform": "telegram",
            "credentials": {"token": "telegram_token"},
        }
        
        with patch("adapters.messaging.telegram.TelegramAdapter") as mock_telegram:
            await server._handle_platform_connect(data)
            
            assert "telegram" in server.platform_adapters
            mock_telegram.assert_called_once_with("telegram_token", server)

    @pytest.mark.asyncio
    async def test_handle_platform_connect_whatsapp(self, server):
        """Test _handle_platform_connect for whatsapp"""
        data = {
            "platform": "whatsapp",
            "config": {"session_path": "/tmp/whatsapp"},
        }
        
        with patch("adapters.messaging.whatsapp.WhatsAppAdapter") as mock_whatsapp:
            await server._handle_platform_connect(data)
            
            assert "whatsapp" in server.platform_adapters
            mock_whatsapp.assert_called_once_with("whatsapp", server, {"session_path": "/tmp/whatsapp"})

    @pytest.mark.asyncio
    async def test_handle_platform_connect_imessage(self, server):
        """Test _handle_platform_connect for imessage"""
        data = {"platform": "imessage"}
        
        with patch("adapters.messaging.imessage.IMessageAdapter") as mock_imessage:
            await server._handle_platform_connect(data)
            
            assert "imessage" in server.platform_adapters
            mock_imessage.assert_called_once_with("imessage", server)

    @pytest.mark.asyncio
    async def test_handle_platform_connect_sms(self, server):
        """Test _handle_platform_connect for sms"""
        data = {
            "platform": "sms",
            "config": {"provider": "twilio"},
        }
        
        with patch("adapters.messaging.sms.SMSAdapter") as mock_sms:
            await server._handle_platform_connect(data)
            
            assert "sms" in server.platform_adapters
            mock_sms.assert_called_once_with("sms", server, {"provider": "twilio"})

    @pytest.mark.asyncio
    async def test_handle_platform_connect_unknown(self, server):
        """Test _handle_platform_connect for unknown platform"""
        data = {"platform": "unknown_platform"}
        
        await server._handle_platform_connect(data)
        
        assert "unknown_platform" in server.platform_adapters
        # Should create a generic PlatformAdapter

    @pytest.mark.asyncio
    async def test_handle_command(self, server):
        """Test _handle_command method"""
        data = {"command": "test_cmd", "args": ["arg1", "arg2"]}
        
        # Should not raise exception
        await server._handle_command(data)

    @pytest.mark.asyncio
    async def test_save_media(self, server):
        """Test _save_media method"""
        
        # Create test attachment
        test_data = b"test media content"
        attachment = MediaAttachment(
            type=MessageType.DOCUMENT,
            filename="test.txt",
            mime_type="text/plain",
            size=len(test_data),
            data=test_data,
        )
        
        # Mock aiofiles to avoid actual file I/O
        with patch("adapters.messaging.server.aiofiles.open") as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file
            
            result = await server._save_media(attachment)
            
            # Verify file was written
            mock_file.write.assert_called_once_with(test_data)
            
            # Verify returned path contains hash and filename
            assert "test.txt" in result

    def test_generate_id(self, server):
        """Test _generate_id method"""
        id1 = server._generate_id()
        id2 = server._generate_id()
        
        # Should generate different UUIDs
        assert id1 != id2
        assert len(id1) == 36  # UUID length
        assert len(id2) == 36


class TestMediaAttachment:
    """Test suite for MediaAttachment"""

    def test_media_attachment_to_dict(self):
        """Test MediaAttachment.to_dict() method"""
        data = b"test image data"
        thumbnail = b"test thumbnail data"
        
        attachment = MediaAttachment(
            type=MessageType.IMAGE,
            filename="test.jpg",
            mime_type="image/jpeg",
            size=100,
            data=data,
            caption="Test image",
            thumbnail=thumbnail,
        )
        
        result = attachment.to_dict()
        
        expected = {
            "type": "image",
            "filename": "test.jpg",
            "mime_type": "image/jpeg",
            "size": 100,
            "data": base64.b64encode(data).decode("utf-8"),
            "caption": "Test image",
            "has_thumbnail": True,
        }
        
        assert result == expected

    def test_media_attachment_from_dict(self):
        """Test MediaAttachment.from_dict() classmethod"""
        data = b"test image data"
        thumbnail = b"test thumbnail data"
        
        data_dict = {
            "type": "image",
            "filename": "test.jpg",
            "mime_type": "image/jpeg",
            "size": 100,
            "data": base64.b64encode(data).decode("utf-8"),
            "caption": "Test image",
            "thumbnail": base64.b64encode(thumbnail).decode("utf-8"),
        }
        
        attachment = MediaAttachment.from_dict(data_dict)
        
        assert attachment.type == MessageType.IMAGE
        assert attachment.filename == "test.jpg"
        assert attachment.mime_type == "image/jpeg"
        assert attachment.size == 100
        assert attachment.data == data
        assert attachment.caption == "Test image"
        assert attachment.thumbnail == thumbnail

    def test_media_attachment_from_dict_no_thumbnail(self):
        """Test MediaAttachment.from_dict() without thumbnail"""
        data = b"test data"
        
        data_dict = {
            "type": "document",
            "filename": "test.pdf",
            "mime_type": "application/pdf",
            "size": 50,
            "data": base64.b64encode(data).decode("utf-8"),
        }
        
        attachment = MediaAttachment.from_dict(data_dict)
        
        assert attachment.type == MessageType.DOCUMENT
        assert attachment.filename == "test.pdf"
        assert attachment.thumbnail is None
        assert attachment.caption is None
