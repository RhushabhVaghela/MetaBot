"""
Telegram Adapter for MegaBot
Provides full integration with Telegram Bot API including:
- Text messages
- Media (images, videos, documents, audio)
- Inline keyboards and reply keyboards
- Location sharing
- Contact sharing
- Groups and supergroups
- Message edits and deletions
- Webhooks for incoming messages
"""

import asyncio
import hashlib
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

import aiohttp

from adapters.messaging import PlatformMessage, MessageType


class ParseMode(Enum):
    """Telegram parse modes"""

    MARKDOWN = "Markdown"
    MARKDOWN_V2 = "MarkdownV2"
    HTML = "HTML"


class ChatType(Enum):
    """Telegram chat types"""

    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


class UpdateType(Enum):
    """Telegram webhook update types"""

    MESSAGE = "message"
    EDITED_MESSAGE = "edited_message"
    CHANNEL_POST = "channel_post"
    EDITED_CHANNEL_POST = "edited_channel_post"
    INLINE_QUERY = "inline_query"
    CHOOSEN_RESULT = "chosen_inline_result"
    CALLBACK_QUERY = "callback_query"
    SHIPPING_QUERY = "shipping_query"
    PRE_CHECKOUT_QUERY = "pre_checkout_query"
    POLL = "poll"
    POLL_ANSWER = "poll_answer"


@dataclass
class TelegramUser:
    """Telegram user information"""

    id: int
    is_bot: bool = False
    first_name: str = ""
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelegramUser":
        return cls(
            id=data.get("id", 0),
            is_bot=data.get("is_bot", False),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name"),
            username=data.get("username"),
            language_code=data.get("language_code"),
        )


@dataclass
class TelegramChat:
    """Telegram chat information"""

    id: int
    type: ChatType = ChatType.PRIVATE
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelegramChat":
        return cls(
            id=data.get("id", 0),
            type=ChatType(data.get("type", "private")),
            title=data.get("title"),
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
        )


@dataclass
class TelegramMessage:
    """Telegram message object"""

    message_id: int
    chat: TelegramChat
    from_user: Optional[TelegramUser] = None
    date: int = 0
    text: Optional[str] = None
    caption: Optional[str] = None
    photo: List[Dict[str, Any]] = field(default_factory=list)
    document: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    voice: Optional[Dict[str, Any]] = None
    video: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    reply_to_message: Optional["TelegramMessage"] = None
    entities: List[Dict[str, Any]] = field(default_factory=list)
    callback_query: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelegramMessage":
        chat_data = data.get("chat", {})
        chat = TelegramChat.from_dict(chat_data)

        from_data = data.get("from")
        from_user = TelegramUser.from_dict(from_data) if from_data else None

        reply_data = data.get("reply_to_message")
        reply_to_message = TelegramMessage.from_dict(reply_data) if reply_data else None

        return cls(
            message_id=data.get("message_id", 0),
            chat=chat,
            from_user=from_user,
            date=data.get("date", 0),
            text=data.get("text"),
            caption=data.get("caption"),
            photo=data.get("photo", []),
            document=data.get("document"),
            audio=data.get("audio"),
            voice=data.get("voice"),
            video=data.get("video"),
            location=data.get("location"),
            contact=data.get("contact"),
            reply_to_message=reply_to_message,
            entities=data.get("entities", []),
            callback_query=data.get("callback_query"),
        )


@dataclass
class InlineKeyboardButton:
    """Inline keyboard button"""

    text: str
    callback_data: Optional[str] = None
    url: Optional[str] = None
    login_url: Optional[Dict[str, Any]] = None
    switch_inline_query: Optional[str] = None
    switch_inline_query_current_chat: Optional[str] = None
    callback_game: Optional[Dict[str, Any]] = None
    pay: bool = False

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"text": self.text}
        if self.callback_data is not None:
            result["callback_data"] = self.callback_data
        if self.url is not None:
            result["url"] = self.url
        if self.login_url is not None:
            result["login_url"] = self.login_url
        if self.switch_inline_query is not None:
            result["switch_inline_query"] = self.switch_inline_query
        if self.switch_inline_query_current_chat is not None:
            result["switch_inline_query_current_chat"] = (
                self.switch_inline_query_current_chat
            )
        if self.callback_game is not None:
            result["callback_game"] = self.callback_game
        if self.pay:
            result["pay"] = self.pay
        return result


@dataclass
class InlineKeyboardMarkup:
    """Inline keyboard markup"""

    inline_keyboard: List[List[InlineKeyboardButton]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [btn.to_dict() for btn in row] for row in self.inline_keyboard
            ]
        }


@dataclass
class ReplyKeyboardButton:
    """Reply keyboard button"""

    text: str
    request_contact: bool = False
    request_location: bool = False
    request_poll: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"text": self.text}
        if self.request_contact:
            result["request_contact"] = True
        if self.request_location:
            result["request_location"] = True
        if self.request_poll is not None:
            result["request_poll"] = self.request_poll
        return result


@dataclass
class ReplyKeyboardMarkup:
    """Reply keyboard markup"""

    keyboard: List[List[ReplyKeyboardButton]] = field(default_factory=list)
    resize_keyboard: bool = False
    one_time_keyboard: bool = False
    selective: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyboard": [[btn.to_dict() for btn in row] for row in self.keyboard],
            "resize_keyboard": self.resize_keyboard,
            "one_time_keyboard": self.one_time_keyboard,
            "selective": self.selective,
        }


@dataclass
class ForceReplyMarkup:
    """Force reply markup"""

    selective: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"selective": self.selective}


class TelegramAdapter:
    """
    Telegram Bot API Adapter

    Provides comprehensive integration with Telegram's Bot API including:
    - Text, media, and document messaging
    - Inline and reply keyboards
    - Location and contact sharing
    - Group management
    - Message editing and deletion
    - Webhook handling
    - Callback query processing
    """

    def __init__(
        self,
        bot_token: str,
        webhook_url: Optional[str] = None,
        webhook_path: str = "/webhooks/telegram",
        parse_mode: ParseMode = ParseMode.MARKDOWN,
        admin_ids: Optional[List[int]] = None,
    ):
        """
        Initialize the Telegram adapter.

        Args:
            bot_token: Telegram Bot Token from @BotFather
            webhook_url: Base URL for webhooks (optional)
            webhook_path: Webhook endpoint path
            parse_mode: Default parse mode for messages
            admin_ids: List of user IDs with admin privileges
        """
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self.webhook_path = webhook_path
        self.parse_mode = parse_mode
        self.admin_ids = admin_ids or []

        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_initialized = False

        self.me: Optional[Dict[str, Any]] = None
        self.message_cache: Dict[str, Dict[str, Any]] = {}
        self.pending_callbacks: Dict[str, Callable] = {}

        self.message_handlers: List[Callable] = []
        self.callback_handlers: List[Callable] = []
        self.error_handlers: List[Callable] = []

    async def initialize(self) -> bool:
        """
        Initialize the bot by fetching bot info and setting up session.

        Returns:
            True if initialization successful
        """
        try:
            import aiohttp

            self.session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"}
            )

            self.me = await self.get_me()
            if self.me:
                self.is_initialized = True
                print(
                    f"[Telegram] Bot @{self.me.get('username', 'unknown')} initialized"
                )

                if self.webhook_url:
                    await self.set_webhook()

                return True
            return False

        except Exception as e:
            print(f"[Telegram] Initialization failed: {e}")
            if self.session:
                await self.session.close()
                self.session = None
            return False

    async def shutdown(self) -> None:
        """Clean up resources"""
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
            self.session = None
        self.is_initialized = False
        print("[Telegram] Adapter shutdown complete")

    async def get_me(self) -> Optional[Dict[str, Any]]:
        """Get bot information"""
        try:
            return await self._make_request("getMe")
        except Exception:
            return None

    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 0,
        allowed_updates: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get updates via long polling.

        Args:
            offset: Offset from which to start fetching updates
            limit: Number of updates to fetch (1-100)
            timeout: Timeout for long polling
            allowed_updates: List of update types to fetch

        Returns:
            List of updates
        """
        payload: Dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        if allowed_updates:
            payload["allowed_updates"] = allowed_updates

        try:
            return await self._make_request("getUpdates", payload) or []
        except Exception:
            return []

    async def set_webhook(self) -> bool:
        """Set webhook URL"""
        if not self.webhook_url:
            return False

        webhook_url = f"{self.webhook_url}{self.webhook_path}"
        payload = {"url": webhook_url, "secret_token": self._generate_secret_token()}
        result = await self._make_request("setWebhook", payload)
        if result:
            print(f"[Telegram] Webhook set to {webhook_url}")
        return bool(result)

    async def delete_webhook(self) -> bool:
        """Delete current webhook"""
        try:
            result = await self._make_request("deleteWebhook")
            return bool(result)
        except Exception:
            return False

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: Optional[ParseMode] = None,
        entities: Optional[List[Dict[str, Any]]] = None,
        disable_web_page_preview: bool = False,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        allow_sending_without_reply: bool = False,
        reply_markup: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a text message to a chat.

        Args:
            chat_id: Unique identifier for the target chat
            text: Text of the message
            parse_mode: Parse mode (Markdown, MarkdownV2, HTML)
            entities: List of special entities in the message
            disable_web_page_preview: Disable link previews
            disable_notification: Send silently
            protect_content: Protect from forwarding
            reply_to_message_id: Reply to specific message
            allow_sending_without_reply: Allow sending without reply
            reply_markup: Inline keyboard or reply keyboard

        Returns:
            Sent message or None on failure
        """
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": disable_web_page_preview,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
                "allow_sending_without_reply": allow_sending_without_reply,
            }

            mode = parse_mode or self.parse_mode
            payload["parse_mode"] = mode.value

            if entities:
                payload["entities"] = entities
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendMessage", payload)

        except Exception as e:
            print(f"[Telegram] Send message error: {e}")
            return None

    async def edit_message_text(
        self,
        chat_id: str,
        message_id: int,
        text: str,
        parse_mode: Optional[ParseMode] = None,
        entities: Optional[List[Dict[str, Any]]] = None,
        disable_web_page_preview: bool = False,
        inline_message_id: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Edit a message's text"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "disable_web_page_preview": disable_web_page_preview,
            }

            if parse_mode:
                payload["parse_mode"] = parse_mode.value
            if entities:
                payload["entities"] = entities
            if inline_message_id:
                payload["inline_message_id"] = inline_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("editMessageText", payload)

        except Exception as e:
            print(f"[Telegram] Edit message error: {e}")
            return None

    async def delete_message(self, chat_id: str, message_id: int) -> bool:
        """Delete a message"""
        try:
            payload = {"chat_id": chat_id, "message_id": message_id}
            result = await self._make_request("deleteMessage", payload)
            return bool(result)
        except Exception as e:
            print(f"[Telegram] Delete message error: {e}")
            return False

    async def send_photo(
        self,
        chat_id: str,
        photo: str,
        caption: Optional[str] = None,
        parse_mode: Optional[ParseMode] = None,
        has_spoiler: bool = False,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a photo"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "photo": photo,
                "has_spoiler": has_spoiler,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }

            if caption:
                payload["caption"] = caption
                if parse_mode:
                    payload["parse_mode"] = parse_mode.value
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendPhoto", payload)

        except Exception as e:
            print(f"[Telegram] Send photo error: {e}")
            return None

    async def send_document(
        self,
        chat_id: str,
        document: str,
        thumbnail: Optional[str] = None,
        caption: Optional[str] = None,
        parse_mode: Optional[ParseMode] = None,
        disable_content_type_detection: bool = False,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a document"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "document": document,
                "disable_content_type_detection": disable_content_type_detection,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }

            if thumbnail:
                payload["thumbnail"] = thumbnail
            if caption:
                payload["caption"] = caption
                if parse_mode:
                    payload["parse_mode"] = parse_mode.value
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendDocument", payload)

        except Exception as e:
            print(f"[Telegram] Send document error: {e}")
            return None

    async def send_audio(
        self,
        chat_id: str,
        audio: str,
        caption: Optional[str] = None,
        parse_mode: Optional[ParseMode] = None,
        duration: Optional[int] = None,
        performer: Optional[str] = None,
        title: Optional[str] = None,
        thumb: Optional[str] = None,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send an audio file"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "audio": audio,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }

            if caption:
                payload["caption"] = caption
                if parse_mode:
                    payload["parse_mode"] = parse_mode.value
            if duration:
                payload["duration"] = duration
            if performer:
                payload["performer"] = performer
            if title:
                payload["title"] = title
            if thumb:
                payload["thumb"] = thumb
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendAudio", payload)

        except Exception as e:
            print(f"[Telegram] Send audio error: {e}")
            return None

    async def send_voice(
        self,
        chat_id: str,
        voice: str,
        caption: Optional[str] = None,
        parse_mode: Optional[ParseMode] = None,
        duration: Optional[int] = None,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a voice note"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "voice": voice,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }

            if caption:
                payload["caption"] = caption
                if parse_mode:
                    payload["parse_mode"] = parse_mode.value
            if duration:
                payload["duration"] = duration
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendVoice", payload)

        except Exception as e:
            print(f"[Telegram] Send voice error: {e}")
            return None

    async def send_video(
        self,
        chat_id: str,
        video: str,
        thumbnail: Optional[str] = None,
        caption: Optional[str] = None,
        parse_mode: Optional[ParseMode] = None,
        has_spoiler: bool = False,
        duration: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        supports_streaming: bool = False,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a video"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "video": video,
                "has_spoiler": has_spoiler,
                "supports_streaming": supports_streaming,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }

            if thumbnail:
                payload["thumbnail"] = thumbnail
            if caption:
                payload["caption"] = caption
                if parse_mode:
                    payload["parse_mode"] = parse_mode.value
            if duration:
                payload["duration"] = duration
            if width:
                payload["width"] = width
            if height:
                payload["height"] = height
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendVideo", payload)

        except Exception as e:
            print(f"[Telegram] Send video error: {e}")
            return None

    async def send_location(
        self,
        chat_id: str,
        latitude: float,
        longitude: float,
        horizontal_accuracy: Optional[float] = None,
        live_period: Optional[int] = None,
        heading: Optional[int] = None,
        proximity_alert_radius: Optional[int] = None,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a location"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "latitude": latitude,
                "longitude": longitude,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }

            if horizontal_accuracy is not None:
                payload["horizontal_accuracy"] = horizontal_accuracy
            if live_period:
                payload["live_period"] = live_period
            if heading:
                payload["heading"] = heading
            if proximity_alert_radius:
                payload["proximity_alert_radius"] = proximity_alert_radius
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendLocation", payload)

        except Exception as e:
            print(f"[Telegram] Send location error: {e}")
            return None

    async def send_contact(
        self,
        chat_id: str,
        phone_number: str,
        first_name: str,
        last_name: Optional[str] = None,
        vcard: Optional[str] = None,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a contact"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "phone_number": phone_number,
                "first_name": first_name,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }

            if last_name:
                payload["last_name"] = last_name
            if vcard:
                payload["vcard"] = vcard
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendContact", payload)

        except Exception as e:
            print(f"[Telegram] Send contact error: {e}")
            return None

    async def send_poll(
        self,
        chat_id: str,
        question: str,
        options: List[str],
        is_anonymous: bool = True,
        type_poll: str = "regular",
        allows_multiple_answers: bool = False,
        correct_option_id: Optional[int] = None,
        explanation: Optional[str] = None,
        explanation_parse_mode: Optional[ParseMode] = None,
        open_period: Optional[int] = None,
        close_date: Optional[int] = None,
        is_closed: bool = False,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a poll"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "question": question,
                "options": options,
                "is_anonymous": is_anonymous,
                "type": type_poll,
                "allows_multiple_answers": allows_multiple_answers,
                "is_closed": is_closed,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }

            if correct_option_id is not None:
                payload["correct_option_id"] = correct_option_id
            if explanation:
                payload["explanation"] = explanation
                if explanation_parse_mode:
                    payload["explanation_parse_mode"] = explanation_parse_mode.value
            if open_period:
                payload["open_period"] = open_period
            if close_date:
                payload["close_date"] = close_date
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup.to_dict()

            return await self._make_request("sendPoll", payload)

        except Exception as e:
            print(f"[Telegram] Send poll error: {e}")
            return None

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
        url: Optional[str] = None,
        cache_time: int = 0,
    ) -> bool:
        """Answer a callback query"""
        try:
            payload: Dict[str, Any] = {
                "callback_query_id": callback_query_id,
                "cache_time": cache_time,
            }

            if text:
                payload["text"] = text
            if show_alert:
                payload["show_alert"] = show_alert
            if url:
                payload["url"] = url

            result = await self._make_request("answerCallbackQuery", payload)
            return bool(result)

        except Exception as e:
            print(f"[Telegram] Answer callback error: {e}")
            return False

    async def create_chat_invite_link(
        self,
        chat_id: str,
        name: Optional[str] = None,
        expire_date: Optional[int] = None,
        member_limit: Optional[int] = None,
        creates_join_request: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Create an invite link for a chat"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "creates_join_request": creates_join_request,
            }

            if name:
                payload["name"] = name
            if expire_date:
                payload["expire_date"] = expire_date
            if member_limit:
                payload["member_limit"] = member_limit

            return await self._make_request("createChatInviteLink", payload)

        except Exception as e:
            print(f"[Telegram] Create invite link error: {e}")
            return None

    async def export_chat_invite_link(self, chat_id: str) -> Optional[str]:
        """Export an invite link for a chat"""
        try:
            payload = {"chat_id": chat_id}
            result = await self._make_request("exportChatInviteLink", payload)
            return result
        except Exception as e:
            print(f"[Telegram] Export invite link error: {e}")
            return None

    async def get_chat(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get chat information"""
        try:
            payload = {"chat_id": chat_id}
            return await self._make_request("getChat", payload)
        except Exception as e:
            print(f"[Telegram] Get chat error: {e}")
            return None

    async def get_chat_administrators(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get list of administrators in a chat"""
        try:
            payload = {"chat_id": chat_id}
            result = await self._make_request("getChatAdministrators", payload)
            return result or []
        except Exception as e:
            print(f"[Telegram] Get administrators error: {e}")
            return []

    async def get_chat_members_count(self, chat_id: str) -> int:
        """Get the number of members in a chat"""
        try:
            payload = {"chat_id": chat_id}
            result = await self._make_request("getChatMembersCount", payload)
            return result or 0
        except Exception as e:
            print(f"[Telegram] Get members count error: {e}")
            return 0

    async def get_chat_member(
        self, chat_id: str, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get information about a chat member"""
        try:
            payload = {"chat_id": chat_id, "user_id": user_id}
            return await self._make_request("getChatMember", payload)
        except Exception as e:
            print(f"[Telegram] Get chat member error: {e}")
            return None

    async def ban_chat_member(
        self,
        chat_id: str,
        user_id: int,
        until_date: Optional[int] = None,
        revoke_messages: bool = False,
    ) -> bool:
        """Ban a user from a chat"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "user_id": user_id,
                "revoke_messages": revoke_messages,
            }
            if until_date:
                payload["until_date"] = until_date
            result = await self._make_request("banChatMember", payload)
            return bool(result)
        except Exception as e:
            print(f"[Telegram] Ban member error: {e}")
            return False

    async def unban_chat_member(
        self, chat_id: str, user_id: int, only_if_banned: bool = True
    ) -> bool:
        """Unban a user from a chat"""
        try:
            payload = {
                "chat_id": chat_id,
                "user_id": user_id,
                "only_if_banned": only_if_banned,
            }
            result = await self._make_request("unbanChatMember", payload)
            return bool(result)
        except Exception as e:
            print(f"[Telegram] Unban member error: {e}")
            return False

    async def restrict_chat_member(
        self,
        chat_id: str,
        user_id: int,
        permissions: Dict[str, Any],
        until_date: Optional[int] = None,
    ) -> bool:
        """Restrict a user in a supergroup"""
        try:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "user_id": user_id,
                "permissions": permissions,
            }
            if until_date:
                payload["until_date"] = until_date
            result = await self._make_request("restrictChatMember", payload)
            return bool(result)
        except Exception as e:
            print(f"[Telegram] Restrict member error: {e}")
            return False

    async def promote_chat_member(
        self,
        chat_id: str,
        user_id: int,
        is_anonymous: Optional[bool] = None,
        can_manage_chat: Optional[bool] = None,
        can_delete_messages: Optional[bool] = None,
        can_manage_video_chats: Optional[bool] = None,
        can_restrict_members: Optional[bool] = None,
        can_promote_members: Optional[bool] = None,
        can_change_info: Optional[bool] = None,
        can_invite_users: Optional[bool] = None,
        can_pin_messages: Optional[bool] = None,
        can_manage_topics: Optional[bool] = None,
        can_post_stories: Optional[bool] = None,
        can_edit_stories: Optional[bool] = None,
        can_delete_stories: Optional[bool] = None,
    ) -> bool:
        """Promote or demote a user in a supergroup"""
        try:
            payload: Dict[str, Any] = {"chat_id": chat_id, "user_id": user_id}

            if is_anonymous is not None:
                payload["is_anonymous"] = is_anonymous
            if can_manage_chat is not None:
                payload["can_manage_chat"] = can_manage_chat
            if can_delete_messages is not None:
                payload["can_delete_messages"] = can_delete_messages
            if can_manage_video_chats is not None:
                payload["can_manage_video_chats"] = can_manage_video_chats
            if can_restrict_members is not None:
                payload["can_restrict_members"] = can_restrict_members
            if can_promote_members is not None:
                payload["can_promote_members"] = can_promote_members
            if can_change_info is not None:
                payload["can_change_info"] = can_change_info
            if can_invite_users is not None:
                payload["can_invite_users"] = can_invite_users
            if can_pin_messages is not None:
                payload["can_pin_messages"] = can_pin_messages
            if can_manage_topics is not None:
                payload["can_manage_topics"] = can_manage_topics
            if can_post_stories is not None:
                payload["can_post_stories"] = can_post_stories
            if can_edit_stories is not None:
                payload["can_edit_stories"] = can_edit_stories
            if can_delete_stories is not None:
                payload["can_delete_stories"] = can_delete_stories

            result = await self._make_request("promoteChatMember", payload)
            return bool(result)

        except Exception as e:
            print(f"[Telegram] Promote member error: {e}")
            return False

    async def pin_chat_message(
        self, chat_id: str, message_id: int, disable_notification: bool = False
    ) -> bool:
        """Pin a message in a chat"""
        try:
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "disable_notification": disable_notification,
            }
            result = await self._make_request("pinChatMessage", payload)
            return bool(result)
        except Exception as e:
            print(f"[Telegram] Pin message error: {e}")
            return False

    async def unpin_chat_message(
        self, chat_id: str, message_id: Optional[int] = None
    ) -> bool:
        """Unpin a message in a chat"""
        try:
            payload: Dict[str, Any] = {"chat_id": chat_id}
            if message_id:
                payload["message_id"] = message_id
            result = await self._make_request("unpinChatMessage", payload)
            return bool(result)
        except Exception as e:
            print(f"[Telegram] Unpin message error: {e}")
            return False

    async def leave_chat(self, chat_id: str) -> bool:
        """Leave a chat"""
        try:
            payload = {"chat_id": chat_id}
            result = await self._make_request("leaveChat", payload)
            return bool(result)
        except Exception as e:
            print(f"[Telegram] Leave chat error: {e}")
            return False

    async def forward_message(
        self,
        chat_id: str,
        from_chat_id: str,
        message_id: int,
        disable_notification: bool = False,
        protect_content: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Forward a message"""
        try:
            payload = {
                "chat_id": chat_id,
                "from_chat_id": from_chat_id,
                "message_id": message_id,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
            }
            return await self._make_request("forwardMessage", payload)
        except Exception as e:
            print(f"[Telegram] Forward message error: {e}")
            return None

    def register_message_handler(self, handler: Callable) -> None:
        """Register a message handler"""
        self.message_handlers.append(handler)

    def register_callback_handler(self, handler: Callable) -> None:
        """Register a callback query handler"""
        self.callback_handlers.append(handler)

    def register_error_handler(self, handler: Callable) -> None:
        """Register an error handler"""
        self.error_handlers.append(handler)

    async def handle_webhook(
        self, webhook_data: Dict[str, Any]
    ) -> Optional[PlatformMessage]:
        """
        Handle incoming webhook updates.

        Args:
            webhook_data: Raw webhook payload from Telegram

        Returns:
            Processed PlatformMessage or None
        """
        try:
            update = webhook_data.get("update_id")
            if not update:
                return None

            message_data = webhook_data.get("message") or webhook_data.get(
                "callback_query"
            )
            if not message_data:
                return None

            callback_query = webhook_data.get("callback_query")
            if callback_query:
                for handler in self.callback_handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(callback_query)
                        else:
                            handler(callback_query)
                    except Exception as e:
                        print(f"[Telegram] Callback handler error: {e}")

                await self.answer_callback_query(
                    callback_query.get("id", ""), text="Processing..."
                )

            if "message" in webhook_data:
                chat_id = str(message_data.get("chat", {}).get("id", 0))
                text = message_data.get("text") or message_data.get("caption") or ""

                platform_message = PlatformMessage(
                    id=f"tg_{message_data.get('message_id', 0)}",
                    platform="telegram",
                    sender_id=str(message_data.get("from", {}).get("id", 0)),
                    sender_name=message_data.get("from", {}).get(
                        "first_name", "Unknown"
                    ),
                    chat_id=chat_id,
                    content=text,
                    message_type=self._get_message_type(message_data),
                    metadata={
                        "tg_message_id": message_data.get("message_id"),
                        "tg_chat_id": chat_id,
                        "tg_date": message_data.get("date"),
                        "tg_chat_type": message_data.get("chat", {}).get("type"),
                        "entities": message_data.get("entities", []),
                        "callback_data": callback_query.get("data")
                        if callback_query
                        else None,
                    },
                )

                self.message_cache[platform_message.id] = {
                    "chat_id": chat_id,
                    "content": text,
                }

                for handler in self.message_handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(platform_message)
                        else:
                            handler(platform_message)
                    except Exception as e:
                        print(f"[Telegram] Message handler error: {e}")
                        for err_handler in self.error_handlers:
                            try:
                                if asyncio.iscoroutinefunction(err_handler):
                                    await err_handler(e, platform_message)
                                else:
                                    err_handler(e, platform_message)
                            except Exception:
                                pass

                return platform_message

        except Exception as e:
            print(f"[Telegram] Webhook error: {e}")

        return None

    def _get_message_type(self, message_data: Dict[str, Any]) -> MessageType:
        """Determine message type from Telegram message data"""
        if message_data.get("photo"):
            return MessageType.IMAGE
        if message_data.get("video"):
            return MessageType.VIDEO
        if message_data.get("audio"):
            return MessageType.AUDIO
        if message_data.get("document"):
            return MessageType.DOCUMENT
        if message_data.get("voice"):
            return MessageType.AUDIO
        if message_data.get("location"):
            return MessageType.LOCATION
        if message_data.get("contact"):
            return MessageType.CONTACT
        if message_data.get("poll"):
            return MessageType.TEXT
        return MessageType.TEXT

    async def _make_request(
        self, method: str, data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make an API request to Telegram"""
        if not self.session:
            return None

        url = f"{self.base_url}/{method}"
        try:
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("result")
                else:
                    try:
                        error = await response.json()
                    except Exception:
                        error = await response.text()
                    print(f"[Telegram] API error {response.status}: {error}")
                    return None
        except Exception as e:
            print(f"[Telegram] Request error: {e}")
            return None

    def _generate_secret_token(self) -> str:
        """Generate a secret token for webhook verification"""
        return hashlib.sha256(
            f"{self.bot_token}:{uuid.uuid4().hex}".encode()
        ).hexdigest()[:32]

    def _generate_id(self) -> str:
        """Generate unique message ID"""
        return str(uuid.uuid4())


async def main():
    """Example usage of Telegram adapter"""
    adapter = TelegramAdapter(
        bot_token="YOUR_BOT_TOKEN",
        webhook_url="https://your-domain.com",
        admin_ids=[123456789],
    )

    if await adapter.initialize():
        bot_name = adapter.me.get("username") if adapter.me else "unknown"
        print(f"Bot @{bot_name} is ready!")

        adapter.register_message_handler(lambda msg: print(f"Received: {msg.content}"))

        await adapter.send_message(
            chat_id="123456789", text="Hello from MegaBot Telegram Adapter!"
        )


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
