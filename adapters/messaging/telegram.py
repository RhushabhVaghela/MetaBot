import uuid
import aiohttp
from typing import Any, Dict, List, Optional
from .server import PlatformAdapter, PlatformMessage, MessageType


class TelegramAdapter(PlatformAdapter):
    def __init__(self, bot_token: str, server: Any):
        super().__init__("telegram", server)
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.session = None

    async def _ensure_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def _make_request(self, method: str, data: Optional[Dict] = None) -> Any:
        await self._ensure_session()
        try:
            async with self.session.post(f"{self.api_url}/{method}", json=data) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    return res.get("result")
        except Exception:
            pass
        return None

    async def send_text(
        self, chat_id: str, text: str, reply_to: Optional[str] = None
    ) -> Optional[PlatformMessage]:
        res = await self._make_request(
            "sendMessage", {"chat_id": chat_id, "text": text}
        )
        return PlatformMessage(
            id=str(res.get("message_id") if res else uuid.uuid4()),
            platform="telegram",
            sender_id="megabot",
            sender_name="MegaBot",
            chat_id=chat_id,
            content=text,
            reply_to=reply_to,
        )

    async def send_media(
        self,
        chat_id: str,
        media_path: str,
        caption: Optional[str] = None,
        media_type: MessageType = MessageType.IMAGE,
    ) -> Optional[PlatformMessage]:
        return PlatformMessage(
            id=str(uuid.uuid4()),
            platform="telegram",
            sender_id="megabot",
            sender_name="MegaBot",
            chat_id=chat_id,
            content=caption or "",
            message_type=media_type,
        )

    async def send_photo(self, chat_id: str, photo: str, **kwargs):
        return await self._make_request(
            "sendPhoto", {"chat_id": chat_id, "photo": photo, **kwargs}
        )

    async def send_document(self, chat_id: str, document: str, **kwargs):
        return await self._make_request(
            "sendDocument", {"chat_id": chat_id, "document": document, **kwargs}
        )

    async def send_audio(self, chat_id: str, audio: str, **kwargs):
        return await self._make_request(
            "sendAudio", {"chat_id": chat_id, "audio": audio, **kwargs}
        )

    async def send_voice(self, chat_id: str, voice: str, **kwargs):
        return await self._make_request(
            "sendVoice", {"chat_id": chat_id, "voice": voice, **kwargs}
        )

    async def send_video(self, chat_id: str, video: str, **kwargs):
        return await self._make_request(
            "sendVideo", {"chat_id": chat_id, "video": video, **kwargs}
        )

    async def send_location(
        self, chat_id: str, latitude: float, longitude: float, **kwargs
    ):
        return await self._make_request(
            "sendLocation",
            {
                "chat_id": chat_id,
                "latitude": latitude,
                "longitude": longitude,
                **kwargs,
            },
        )

    async def send_contact(
        self, chat_id: str, phone_number: str, first_name: str, **kwargs
    ):
        return await self._make_request(
            "sendContact",
            {
                "chat_id": chat_id,
                "phone_number": phone_number,
                "first_name": first_name,
                **kwargs,
            },
        )

    async def send_poll(
        self, chat_id: str, question: str, options: List[str], **kwargs
    ):
        return await self._make_request(
            "sendPoll",
            {"chat_id": chat_id, "question": question, "options": options, **kwargs},
        )

    async def edit_message_text(
        self, chat_id: str, message_id: int, text: str, **kwargs
    ):
        return await self._make_request(
            "editMessageText",
            {"chat_id": chat_id, "message_id": message_id, "text": text, **kwargs},
        )

    async def delete_message(self, chat_id: str, message_id: int):
        return bool(
            await self._make_request(
                "deleteMessage", {"chat_id": chat_id, "message_id": message_id}
            )
        )

    async def answer_callback_query(self, callback_query_id: str, **kwargs):
        return bool(
            await self._make_request(
                "answerCallbackQuery",
                {"callback_query_id": callback_query_id, **kwargs},
            )
        )

    async def create_chat_invite_link(self, chat_id: str, **kwargs):
        return await self._make_request(
            "createChatInviteLink", {"chat_id": chat_id, **kwargs}
        )

    async def export_chat_invite_link(self, chat_id: str):
        return await self._make_request("exportChatInviteLink", {"chat_id": chat_id})

    async def get_chat(self, chat_id: str):
        return await self._make_request("getChat", {"chat_id": chat_id})

    async def get_chat_administrators(self, chat_id: str):
        return (
            await self._make_request("getChatAdministrators", {"chat_id": chat_id})
            or []
        )

    async def get_chat_members_count(self, chat_id: str):
        return (
            await self._make_request("getChatMembersCount", {"chat_id": chat_id}) or 0
        )

    async def get_chat_member(self, chat_id: str, user_id: int):
        return await self._make_request(
            "getChatMember", {"chat_id": chat_id, "user_id": user_id}
        )

    async def ban_chat_member(self, chat_id: str, user_id: int, **kwargs):
        return bool(
            await self._make_request(
                "banChatMember", {"chat_id": chat_id, "user_id": user_id, **kwargs}
            )
        )

    async def unban_chat_member(self, chat_id: str, user_id: int, **kwargs):
        return bool(
            await self._make_request(
                "unbanChatMember", {"chat_id": chat_id, "user_id": user_id, **kwargs}
            )
        )

    async def restrict_chat_member(
        self, chat_id: str, user_id: int, permissions: Dict, **kwargs
    ):
        return bool(
            await self._make_request(
                "restrictChatMember",
                {
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "permissions": permissions,
                    **kwargs,
                },
            )
        )

    async def promote_chat_member(self, chat_id: str, user_id: int, **kwargs):
        return bool(
            await self._make_request(
                "promoteChatMember", {"chat_id": chat_id, "user_id": user_id, **kwargs}
            )
        )

    async def pin_chat_message(self, chat_id: str, message_id: int, **kwargs):
        return bool(
            await self._make_request(
                "pinChatMessage",
                {"chat_id": chat_id, "message_id": message_id, **kwargs},
            )
        )

    async def unpin_chat_message(self, chat_id: str, **kwargs):
        return bool(
            await self._make_request("unpinChatMessage", {"chat_id": chat_id, **kwargs})
        )

    async def leave_chat(self, chat_id: str):
        return bool(await self._make_request("leaveChat", {"chat_id": chat_id}))

    async def forward_message(
        self, chat_id: str, from_chat_id: str, message_id: int, **kwargs
    ):
        return await self._make_request(
            "forwardMessage",
            {
                "chat_id": chat_id,
                "from_chat_id": from_chat_id,
                "message_id": message_id,
                **kwargs,
            },
        )

    async def get_me(self):
        try:
            return await self._make_request("getMe")
        except Exception:
            return None

    async def get_updates(self, **kwargs):
        try:
            return await self._make_request("getUpdates", kwargs) or []
        except Exception:
            return []

    async def delete_webhook(self):
        try:
            return bool(await self._make_request("deleteWebhook"))
        except Exception:
            return False

    async def handle_webhook(self, data: Dict) -> Optional[PlatformMessage]:
        if not data or not data.get("update_id"):
            return None
        msg_data = data.get("message") or data.get("callback_query", {}).get("message")
        if not msg_data:
            return None
        return PlatformMessage(
            id=f"tg_{msg_data.get('message_id')}",
            platform="telegram",
            sender_id=str(msg_data.get("from", {}).get("id")),
            sender_name="User",
            chat_id=str(msg_data.get("chat", {}).get("id")),
            content=msg_data.get("text", ""),
        )

    async def shutdown(self):
        if self.session:
            await self.session.close()
