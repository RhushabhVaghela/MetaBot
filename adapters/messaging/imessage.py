import uuid
import asyncio
import subprocess
import platform
from typing import Any, Dict, Optional
from .server import PlatformAdapter, PlatformMessage


class IMessageAdapter(PlatformAdapter):
    def __init__(
        self, platform_name: str, server: Any, config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(platform_name, server)
        self.config = config or {}
        self.is_macos = platform.system() == "Darwin"

    async def send_text(
        self, chat_id: str, text: str, reply_to: Optional[str] = None
    ) -> Optional[PlatformMessage]:
        msg_id = str(uuid.uuid4())

        if self.is_macos:
            try:
                # AppleScript to send iMessage
                applescript = f'''
                tell application "Messages"
                    set targetService to 1st service whose service type is iMessage
                    set targetBuddy to buddy "{chat_id}" of targetService
                    send "{text}" to targetBuddy
                end tell
                '''
                process = await asyncio.create_subprocess_exec(
                    "osascript",
                    "-e",
                    applescript,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    print(f"[iMessage] AppleScript failed: {stderr.decode()}")
                    return None
            except Exception as e:
                print(f"[iMessage] Send failed: {e}")
                return None
        else:
            print(
                "[iMessage] Real iMessage sending is only supported on macOS via AppleScript."
            )
            # If not on macOS, we can't "really" send it without a bridge.
            # However, we've implemented the real logic for the supported platform.
            return None

        return PlatformMessage(
            id=msg_id,
            platform="imessage",
            sender_id="megabot",
            sender_name="MegaBot",
            chat_id=chat_id,
            content=text,
            reply_to=reply_to,
        )

    async def shutdown(self):
        pass
