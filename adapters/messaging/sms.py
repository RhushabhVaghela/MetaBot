import uuid
import asyncio
from typing import Any, Dict, Optional
from .server import PlatformAdapter, PlatformMessage


class SMSAdapter(PlatformAdapter):
    def __init__(
        self, platform: str, server: Any, config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(platform, server)
        self.config = config or {}
        self.account_sid = self.config.get("twilio_account_sid")
        self.auth_token = self.config.get("twilio_auth_token")
        self.from_number = self.config.get("twilio_from_number")
        self.client = None

    async def initialize(self) -> bool:
        if not self.account_sid or not self.auth_token:
            return False
        try:
            from twilio.rest import Client

            self.client = Client(self.account_sid, self.auth_token)
            return True
        except Exception as e:
            print(f"[SMS] Initialization failed: {e}")
            return False

    async def send_text(
        self, chat_id: str, text: str, reply_to: Optional[str] = None
    ) -> Optional[PlatformMessage]:
        msg_id = str(uuid.uuid4())

        if self.client and self.from_number:
            try:
                # Twilio send is blocking, wrap in executor
                loop = asyncio.get_event_loop()
                message = await loop.run_in_executor(
                    None,
                    lambda: self.client.messages.create(
                        body=text, from_=self.from_number, to=chat_id
                    ),
                )
                msg_id = message.sid
            except Exception as e:
                print(f"[SMS] Send failed: {e}")
                return None

        return PlatformMessage(
            id=msg_id,
            platform="sms",
            sender_id="megabot",
            sender_name="MegaBot",
            chat_id=chat_id,
            content=text,
            reply_to=reply_to,
        )

    async def shutdown(self):
        pass
