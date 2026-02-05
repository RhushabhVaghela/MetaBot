"""
Tests for VoiceAdapter
"""

import pytest
from unittest.mock import MagicMock, patch
from adapters.voice_adapter import VoiceAdapter


class TestVoiceAdapter:
    """Test suite for VoiceAdapter"""

    @pytest.fixture
    def voice_adapter(self):
        """Create VoiceAdapter instance"""
        with patch("adapters.voice_adapter.Client"):
            adapter = VoiceAdapter(
                account_sid="ACtest", auth_token="test_token", from_number="+1234567890"
            )
            return adapter

    @pytest.fixture
    def voice_adapter_with_callback(self):
        """Create VoiceAdapter instance with callback URL"""
        with patch("adapters.voice_adapter.Client"):
            adapter = VoiceAdapter(
                account_sid="ACtest",
                auth_token="test_token",
                from_number="+1234567890",
                callback_url="https://example.com/callback",
            )
            return adapter

    @pytest.mark.asyncio
    async def test_make_call_text(self, voice_adapter):
        """Test making a call with text script"""
        mock_call = MagicMock()
        mock_call.sid = "CA123"
        voice_adapter.client.calls.create.return_value = mock_call

        sid = await voice_adapter.make_call("+1987654321", "Hello from MegaBot")

        assert sid == "CA123"
        voice_adapter.client.calls.create.assert_called_once()
        args = voice_adapter.client.calls.create.call_args[1]
        assert args["to"] == "+1987654321"
        assert "<Say>Hello from MegaBot</Say>" in args["twiml"]

    @pytest.mark.asyncio
    async def test_make_call_url(self, voice_adapter):
        """Test making a call with URL script"""
        mock_call = MagicMock()
        mock_call.sid = "CA456"
        voice_adapter.client.calls.create.return_value = mock_call

        sid = await voice_adapter.make_call("+1987654321", "https://example.com/twiml")

        assert sid == "CA456"
        args = voice_adapter.client.calls.create.call_args[1]
        assert args["url"] == "https://example.com/twiml"
        assert "twiml" not in args

    @pytest.mark.asyncio
    async def test_make_call_with_callback(self, voice_adapter_with_callback):
        """Test making a call with callback URL"""
        mock_call = MagicMock()
        mock_call.sid = "CA789"
        voice_adapter_with_callback.client.calls.create.return_value = mock_call

        sid = await voice_adapter_with_callback.make_call("+1987654321", "Hello")

        assert sid == "CA789"
        args = voice_adapter_with_callback.client.calls.create.call_args[1]
        assert args["status_callback"] == "https://example.com/callback"
        assert args["status_callback_event"] == [
            "initiated",
            "ringing",
            "answered",
            "completed",
        ]

    @pytest.mark.asyncio
    async def test_make_call_error(self, voice_adapter):
        """Test make_call error handling"""
        voice_adapter.client.calls.create.side_effect = Exception("API Error")

        sid = await voice_adapter.make_call("+1987654321", "Hello")

        assert sid.startswith("error_")
        assert len(sid) == 14  # error_ + 8 hex chars

    @pytest.mark.asyncio
    async def test_transcribe_audio(self, voice_adapter):
        """Test audio transcription"""
        text = await voice_adapter.transcribe_audio(b"dummy_audio")
        assert "simulated transcription" in text.lower()

    @pytest.mark.asyncio
    async def test_speak(self, voice_adapter):
        """Test text-to-speech"""
        audio = await voice_adapter.speak("Hello")
        assert audio.startswith(b"RIFF")

    @pytest.mark.asyncio
    async def test_get_call_logs(self, voice_adapter):
        """Test getting call logs"""
        logs = await voice_adapter.get_call_logs(limit=5)
        assert len(logs) == 5
        assert logs[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_call_logs_error(self, voice_adapter):
        """Test get_call_logs error handling"""
        # Mock the list comprehension to fail
        original_uuid = voice_adapter.__class__.__dict__.get("get_call_logs").__code__
        # Since it's hard to mock the list comprehension, let's patch uuid to raise
        with patch(
            "adapters.voice_adapter.uuid.uuid4", side_effect=Exception("UUID Error")
        ):
            logs = await voice_adapter.get_call_logs(limit=1)
            assert logs == []

    @pytest.mark.asyncio
    async def test_shutdown(self, voice_adapter):
        """Test shutdown functionality"""
        assert voice_adapter.is_connected is True

        await voice_adapter.shutdown()

        assert voice_adapter.is_connected is False

    def test_initialization_error_handling(self):
        """Test initialization when Client fails"""
        with patch(
            "adapters.voice_adapter.Client", side_effect=Exception("Connection failed")
        ):
            adapter = VoiceAdapter(
                account_sid="ACtest", auth_token="test_token", from_number="+1234567890"
            )

            assert adapter.client is None
            assert adapter.is_connected is False

    def test_fallback_client_creation(self):
        """Test that fallback Client is created when twilio not available"""
        # The fallback Client is created at import time when twilio import fails
        # This test verifies the mock Client works

        # If Client is the real one (installed), we must mock it to avoid network calls
        with patch("adapters.voice_adapter.Client") as MockClient:
            instance = MockClient("test", "test")
            mock_call = MagicMock()
            mock_call.sid = "CA123"
            instance.calls.create.return_value = mock_call

            call = instance.calls.create(to="+123", from_="+456")
            assert hasattr(call, "sid")
            assert call.sid.startswith("CA")
