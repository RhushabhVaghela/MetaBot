"""
Voice Adapter for MegaBot
Provides integration with telephony services (Twilio) for voice calls.
"""

import asyncio
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.interfaces import VoiceInterface

try:
    from twilio.rest import Client
except ImportError:
    # Fallback mock
    class Client:
        def __init__(self, *args, **kwargs):
            pass

        class Calls:
            def create(self, *args, **kwargs):
                class MockCall:
                    sid = "CA" + uuid.uuid4().hex

                return MockCall()

        calls = Calls()


class VoiceAdapter(VoiceInterface):
    """
    Voice platform adapter using Twilio.

    Features:
    - Outbound phone calls with scripts (TwiML)
    - Audio transcription (simulated/API)
    - Text-to-Speech (simulated/API)
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        callback_url: Optional[str] = None,
    ):
        """
        Initialize the Voice adapter.

        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: Twilio phone number
            callback_url: Webhook URL for call status/events
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.callback_url = callback_url

        try:
            self.client = Client(account_sid, auth_token)
            self.is_connected = True
        except Exception as e:
            print(f"[Voice] Failed to initialize Twilio client: {e}")
            self.client = None
            self.is_connected = False

    async def make_call(
        self,
        recipient_phone: str,
        script: str,
        ivr: bool = False,
        action_id: Optional[str] = None,
    ) -> str:
        """
        Initiate a phone call.

        Args:
            recipient_phone: Phone number to call
            script: Text to speak or URL to TwiML
            ivr: If True, set up an IVR flow to collect input
            action_id: The ID of the action being approved (required for IVR)

        Returns:
            Call SID
        """
        try:
            # If script doesn't look like a URL, treat it as text to speak
            if not script.startswith("http"):
                if ivr and action_id and self.callback_url:
                    # TwiML for IVR: Say script, then wait for digit 1
                    # Append action_id to the callback URL
                    action_url = f"{self.callback_url}/ivr?action_id={action_id}"
                    twiml = f"""
                    <Response>
                        <Gather numDigits="1" timeout="10" action="{action_url}">
                            <Say>{script} Press 1 to authorize this action, or any other key to reject.</Say>
                        </Gather>
                        <Say>We did not receive any input. Goodbye.</Say>
                    </Response>
                    """
                else:
                    twiml = f"<Response><Say>{script}</Say></Response>"
            else:
                twiml = None

            kwargs = {
                "to": recipient_phone,
                "from_": self.from_number,
            }

            if twiml:
                kwargs["twiml"] = twiml
            else:
                kwargs["url"] = script

            if self.callback_url:
                kwargs["status_callback"] = self.callback_url
                kwargs["status_callback_event"] = [
                    "initiated",
                    "ringing",
                    "answered",
                    "completed",
                ]

            # Run in executor because twilio-python is synchronous
            if not self.client:
                print("[Voice] Cannot make call: Twilio client not initialized.")
                return f"error_no_client"

            call = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.client.calls.create(**kwargs)
            )

            print(
                f"[Voice] Call initiated to {recipient_phone}: {call.sid} (IVR={ivr})"
            )
            return call.sid

        except Exception as e:
            print(f"[Voice] Make call error: {e}")
            return f"error_{uuid.uuid4().hex[:8]}"

    async def transcribe_audio(self, audio_data: bytes) -> str:
        """
        Transcribe audio data to text.
        (Implementation would use Whisper or Twilio Transcription)

        Args:
            audio_data: Raw audio bytes

        Returns:
            Transcribed text
        """
        # Simulated transcription
        print(f"[Voice] Transcribing {len(audio_data)} bytes of audio...")
        await asyncio.sleep(1)
        return "This is a simulated transcription of the audio input."

    async def speak(self, text: str) -> bytes:
        """
        Convert text to speech.
        (Implementation would use OpenAI TTS or Google TTS)

        Args:
            text: Text to speak

        Returns:
            Audio data bytes
        """
        # Simulated TTS
        print(f"[Voice] Converting text to speech: {text[:50]}...")
        await asyncio.sleep(1)
        # Return dummy bytes
        return b"RIFF" + b"\x00" * 100

    async def get_call_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent call logs"""
        try:
            # Simulated call logs
            return [
                {
                    "sid": "CA" + uuid.uuid4().hex,
                    "to": "+1234567890",
                    "from": self.from_number,
                    "status": "completed",
                    "start_time": datetime.now().isoformat(),
                    "duration": "45s",
                }
                for _ in range(limit)
            ]
        except Exception as e:
            print(f"[Voice] Get logs error: {e}")
            return []

    async def shutdown(self):
        """Clean up resources"""
        self.is_connected = False
        print("[Voice] Adapter shutdown complete")
