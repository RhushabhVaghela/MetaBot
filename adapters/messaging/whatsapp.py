import uuid
import asyncio
from typing import Any, Dict, List, Optional
from .server import PlatformAdapter, PlatformMessage, MessageType


class WhatsAppAdapter(PlatformAdapter):
    def __init__(
        self, platform_name: str, server: Any, config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(platform_name, server)
        self.config = config or {}
        self.phone_number_id = self.config.get("phone_number_id", "")
        self.access_token = self.config.get("access_token", "")
        self.push_notifications_enabled = self.config.get("push_notifications", {}).get(
            "enabled", True
        )
        self.session = None
        self.message_cache = {}
        self.group_chats = {}
        self.notification_callbacks = []
        self._pending_notifications = {}
        self.is_initialized = False
        self.retry_attempts = 3

    async def initialize(self) -> bool:
        try:
            import aiohttp

            self.session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            if not self.phone_number_id:
                return True
            async with self.session.get(
                f"https://graph.facebook.com/v17.0/{self.phone_number_id}"
            ) as resp:
                if resp.status == 200:
                    self.is_initialized = True
                    return True
                return False
        except Exception:
            return False

    def register_notification_callback(self, callback):
        self.notification_callbacks.append(callback)

    async def _notify_callbacks(self, data):
        for cb in self.notification_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(data)
                else:
                    cb(data)
            except Exception:
                pass

    async def send_text(
        self,
        chat_id: str,
        text: str,
        reply_to: Optional[str] = None,
        markup: bool = False,
        preview_url: bool = True,
    ) -> Optional[PlatformMessage]:
        try:
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            content = self._format_text(text, markup=markup)
            if self.is_initialized:
                res = await self._send_with_retry(
                    {
                        "messaging_product": "whatsapp",
                        "to": chat_id,
                        "text": {"body": content},
                    }
                )
                if not res:
                    return None
                msg_id = res.get("messages", [{}])[0].get("id", msg_id)
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=content,
                reply_to=reply_to,
            )
        except Exception:
            return None

    async def send_media(
        self,
        chat_id: str,
        media_path: str,
        caption: Optional[str] = None,
        media_type: MessageType = MessageType.IMAGE,
    ) -> Optional[PlatformMessage]:
        try:
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=caption or "",
                message_type=media_type,
                metadata={"media_path": media_path},
            )
        except Exception:
            return None

    async def send_document(
        self, chat_id: str, document_path: str, caption: Optional[str] = None
    ) -> Optional[PlatformMessage]:
        return await self.send_media(
            chat_id, document_path, caption, MessageType.DOCUMENT
        )

    async def send_location(
        self, chat_id: str, latitude: float, longitude: float, **kwargs
    ) -> Optional[PlatformMessage]:
        try:
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=f"Location: {latitude}, {longitude}",
                message_type=MessageType.LOCATION,
                metadata={"lat": latitude, "long": longitude},
            )
        except Exception:
            return None

    async def send_contact(
        self, chat_id: str, contact_info: Dict[str, Any]
    ) -> Optional[PlatformMessage]:
        try:
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=f"Contact: {contact_info.get('name')}",
                message_type=MessageType.CONTACT,
            )
        except Exception:
            return None

    async def send_template(
        self, chat_id: str, template_name: str, **kwargs
    ) -> Optional[PlatformMessage]:
        try:
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=f"Template: {template_name}",
            )
        except Exception:
            return None

    async def send_push_notification(
        self,
        chat_id: str,
        title: str,
        body: str,
        buttons: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> Optional[PlatformMessage]:
        try:
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=f"{title}: {body}",
                metadata={
                    "notification_type": "push",
                    "buttons": buttons,
                    "notification_id": str(uuid.uuid4()),
                },
            )
        except Exception:
            return None

    async def send_interactive_list(
        self,
        chat_id: str,
        header: str,
        body: str,
        button_text: str,
        sections: List[Dict[str, Any]],
    ) -> Optional[PlatformMessage]:
        try:
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=f"{header}: {body}",
                metadata={"interactive_type": "list", "sections": sections},
            )
        except Exception:
            return None

    async def send_reply_buttons(
        self, chat_id: str, text: str, buttons: List[Dict[str, str]], **kwargs
    ) -> Optional[PlatformMessage]:
        try:
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=text,
                metadata={"interactive_type": "button", "buttons": buttons},
            )
        except Exception:
            return None

    async def send_order_notification(
        self,
        chat_id: str,
        order_id: str,
        order_status: str,
        items: List[Dict[str, Any]],
        total: str,
        **kwargs,
    ) -> Optional[PlatformMessage]:
        try:
            await self.send_push_notification(chat_id, "Order", order_status)
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            status_emoji = {
                "confirmed": "✅",
                "processing": "⚙️",
                "shipped": "📦",
                "out_for_delivery": "🚚",
                "delivered": "🎉",
                "cancelled": "❌",
            }.get(order_status.lower(), "📋")
            content = (
                f"Order #{order_id}\n{status_emoji} Status: {order_status.title()}"
            )
            buttons = [{"id": "view_order", "title": "View Order"}]
            if kwargs.get("action_url"):
                buttons.append({"id": "track", "title": "Track"})
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=content,
                metadata={"buttons": buttons},
            )
        except Exception:
            return None

    async def send_payment_notification(
        self,
        chat_id: str,
        payment_id: str,
        amount: str,
        currency: str,
        status: str,
        description: str,
        **kwargs,
    ) -> Optional[PlatformMessage]:
        try:
            await self.send_push_notification(chat_id, "Payment", status)
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            config = {
                "success": {"emoji": "✅", "title": "Payment Received"},
                "pending": {"emoji": "⏳", "title": "Payment Pending"},
                "failed": {"emoji": "❌", "title": "Payment Failed"},
            }.get(status.lower(), {"emoji": "💰", "title": "Payment"})
            content = f"{config['emoji']} *{config['title']}*\nStatus: {status}"
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=content,
            )
        except Exception:
            return None

    async def send_appointment_reminder(
        self,
        chat_id: str,
        appointment_id: str,
        service_name: str,
        datetime_str: str,
        location: Optional[str] = None,
        provider_name: Optional[str] = None,
        confirmation_buttons: bool = False,
        **kwargs,
    ) -> Optional[PlatformMessage]:
        try:
            await self.send_push_notification(chat_id, "Appt", service_name)
            msg_id = f"wa_{uuid.uuid4().hex[:16]}"
            content = f"📅 Appointment Reminder\n\n📝 {service_name}"
            buttons = []
            if confirmation_buttons:
                buttons = [{"id": "c"}, {"id": "r"}, {"id": "h"}]
            return PlatformMessage(
                id=msg_id,
                platform="whatsapp",
                sender_id="megabot",
                sender_name="MegaBot",
                chat_id=chat_id,
                content=content,
                metadata={"buttons": buttons},
            )
        except Exception:
            return None

    async def create_group(
        self, group_name: str, participants: List[str]
    ) -> Optional[str]:
        try:
            gid = f"group_{uuid.uuid4().hex[:16]}"
            self.group_chats[gid] = {"name": group_name, "participants": participants}
            return gid
        except Exception:
            return None

    async def add_group_participant(self, group_id: str, phone: str) -> bool:
        if group_id in self.group_chats:
            if phone not in self.group_chats[group_id]["participants"]:
                self.group_chats[group_id]["participants"].append(phone)
            return True
        return False

    async def get_message_status(self, msg_id: str) -> Optional[Dict]:
        return {"chat_id": "c", "status": "sent"}

    async def handle_webhook(self, data: Dict) -> Optional[PlatformMessage]:
        if not data or not data.get("entry"):
            return None
        try:
            val = data["entry"][0]["changes"][0]["value"]
            if "statuses" in val:
                await self._notify_callbacks(val["statuses"][0])
                return None
            msg_data = val.get("messages", [{}])[0]
            if not msg_data.get("id"):
                return None
            if msg_data.get("type") == "interactive":
                await self._notify_callbacks(msg_data)
                return None
            return PlatformMessage(
                id=msg_data["id"],
                platform="whatsapp",
                sender_id=msg_data.get("from", ""),
                sender_name="User",
                chat_id=msg_data.get("from", ""),
                content=msg_data.get("text", {}).get("body", ""),
            )
        except Exception:
            return None

    async def _send_with_retry(self, payload: Dict) -> Optional[Dict]:
        if not self.session:
            return None
        for attempt in range(self.retry_attempts):
            try:
                async with self.session.post(
                    f"https://graph.facebook.com/v17.0/{self.phone_number_id}/messages",
                    json=payload,
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status == 429:
                        await asyncio.sleep(0.01)
                        continue
                    return None
            except Exception:
                if attempt == self.retry_attempts - 1:
                    return None
                await asyncio.sleep(0.01)
        return None

    async def _send_via_openclaw(self, chat_id, content, msg_type):
        try:
            if hasattr(self.server, "openclaw") and self.server.openclaw:
                return PlatformMessage(
                    id=f"oc_{uuid.uuid4().hex}",
                    platform="whatsapp",
                    sender_id="m",
                    sender_name="m",
                    chat_id=chat_id,
                    content=content,
                    metadata={"source": "openclaw"},
                )
            return None
        except Exception:
            return None

    def _detect_mime_type(self, p):
        import mimetypes

        return mimetypes.guess_type(p)[0] or "application/octet-stream"

    def _get_mime_type(self, p, t):
        d = self._detect_mime_type(p)
        if d != "application/octet-stream":
            return d
        m = {
            MessageType.IMAGE: "image/jpeg",
            MessageType.VIDEO: "video/mp4",
            MessageType.AUDIO: "audio/mpeg",
            MessageType.DOCUMENT: "application/pdf",
        }
        return m.get(t, d)

    async def _upload_media(
        self, file_path: str, media_type: MessageType
    ) -> Optional[str]:
        if not self.session:
            return None
        try:
            import aiohttp
            import mimetypes

            mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

            data = aiohttp.FormData()
            data.add_field("messaging_product", "whatsapp")
            data.add_field("type", self._map_media_type(media_type))
            data.add_field(
                "file",
                open(file_path, "rb"),
                filename=file_path.split("/")[-1],
                content_type=mime_type,
            )

            async with self.session.post(
                f"https://graph.facebook.com/v17.0/{self.phone_number_id}/media",
                data=data,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("id")
                return None
        except Exception as e:
            print(f"[WhatsApp] Media upload failed: {e}")
            return None

    async def shutdown(self):
        try:
            if self.session:
                await self.session.close()
                print("WhatsApp adapter shutdown complete")
        except Exception as e:
            print(f"Error during shutdown: {e}")

    def _normalize_phone(self, p):
        return p

    def _format_text(self, t, **kwargs):
        if kwargs.get("markup"):
            t = t.replace("*", "\\*").replace("_", "\\_").replace("~", "\\~")
        return t

    async def make_call(self, chat_id: str, is_video: bool = False) -> bool:
        return False

    def _get_contact_name(self, p):
        return f"WhatsApp:{p}"

    def _map_media_type(self, t):
        m = {
            MessageType.IMAGE: "image",
            MessageType.VIDEO: "video",
            MessageType.AUDIO: "audio",
            MessageType.DOCUMENT: "document",
            MessageType.STICKER: "sticker",
        }
        return m.get(t, "document")

    def _mime_to_message_type(self, m):
        if "image" in m:
            return MessageType.IMAGE
        if "video" in m:
            return MessageType.VIDEO
        if "audio" in m:
            return MessageType.AUDIO
        return MessageType.DOCUMENT
