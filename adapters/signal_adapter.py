"""
Signal Adapter for MegaBot
Provides integration with Signal using signal-cli (JSON-RPC interface)

Features:
- Text messages
- Media sharing (images, videos, documents)
- Group management
- Reactions
- Mentions
- Delivery receipts
- Webhook support for incoming messages

Note: Requires signal-cli to be installed and running in JSON-RPC mode:
    signal-cli daemon --socket /tmp/signal.socket --dbus=system
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

from adapters.messaging import PlatformMessage, MessageType


class SignalMessageType(Enum):
    """Types of Signal messages"""

    TEXT = "text"
    DATA_MESSAGE = "dataMessage"
    TYPING = "typing"
    READ = "read"
    DELIVERED = "delivered"
    SESSION_RESET = "sessionReset"


class SignalGroupType(Enum):
    """Signal group types"""

    MASTER = "MASTER"
    UNKNOWN = "UNKNOWN"


@dataclass
class SignalRecipient:
    """Signal recipient information"""

    uuid: Optional[str] = None
    number: Optional[str] = None
    username: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalRecipient":
        return cls(
            uuid=data.get("uuid"),
            number=data.get("number"),
            username=data.get("username"),
        )


@dataclass
class SignalAttachment:
    """Signal attachment information"""

    id: Optional[str] = None
    content_type: Optional[str] = None
    filename: Optional[str] = None
    size: Optional[int] = None
    url: Optional[str] = None
    thumbnail: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalAttachment":
        return cls(
            id=data.get("id"),
            content_type=data.get("contentType"),
            filename=data.get("filename"),
            size=data.get("size"),
            url=data.get("url"),
            thumbnail=data.get("thumbnail"),
        )


@dataclass
class SignalQuote:
    """Quoted message info"""

    id: int
    author: str
    text: Optional[str] = None
    attachments: List[SignalAttachment] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalQuote":
        return cls(
            id=data.get("id", 0),
            author=data.get("author", ""),
            text=data.get("text"),
            attachments=[
                SignalAttachment.from_dict(a) for a in data.get("attachments", [])
            ],
        )


@dataclass
class SignalReaction:
    """Reaction to a message"""

    emoji: str
    target_author: str
    target_timestamp: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalReaction":
        return cls(
            emoji=data.get("emoji", ""),
            target_author=data.get("targetAuthor", ""),
            target_timestamp=data.get("targetTimestamp", 0),
        )


@dataclass
class SignalMessage:
    """Complete Signal message"""

    id: str
    source: str
    timestamp: int
    message_type: SignalMessageType = SignalMessageType.TEXT
    content: Optional[str] = None
    attachments: List[SignalAttachment] = field(default_factory=list)
    group_info: Optional[Dict[str, Any]] = None
    quote: Optional[SignalQuote] = None
    reaction: Optional[SignalReaction] = None
    is_receipt: bool = False
    is_unidentified: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalMessage":
        msg_type_str = data.get("type", "text")
        if msg_type_str == "typing":
            msg_type = SignalMessageType.TYPING
        elif msg_type_str == "read":
            msg_type = SignalMessageType.READ
        elif msg_type_str == "delivered":
            msg_type = SignalMessageType.DELIVERED
        elif msg_type_str == "sessionReset":
            msg_type = SignalMessageType.SESSION_RESET
        else:
            msg_type = SignalMessageType.DATA_MESSAGE

        return cls(
            id=data.get("envelopeId", str(uuid.uuid4())),
            source=data.get("source", ""),
            timestamp=data.get("timestamp", 0),
            message_type=msg_type,
            content=data.get("dataMessage", {}).get("message")
            if "dataMessage" in data
            else data.get("message"),
            attachments=[
                SignalAttachment.from_dict(a)
                for a in data.get("dataMessage", {}).get(
                    "attachments", data.get("attachments", [])
                )
            ],
            group_info=data.get("dataMessage", {}).get("groupInfo"),
            quote=SignalQuote.from_dict(data.get("dataMessage", {}).get("quote", {})),
            reaction=SignalReaction.from_dict(
                data.get("dataMessage", {}).get("reaction", {})
            )
            if "reaction" in data.get("dataMessage", {})
            else None,
            is_receipt=msg_type
            in [SignalMessageType.READ, SignalMessageType.DELIVERED],
            is_unidentified=data.get("isUnidentified", False),
        )


@dataclass
class SignalGroup:
    """Signal group information"""

    id: str
    name: str
    description: Optional[str] = None
    members: List[str] = field(default_factory=list)
    admins: List[str] = field(default_factory=list)
    group_type: SignalGroupType = SignalGroupType.UNKNOWN
    avatar: Optional[str] = None
    created_at: Optional[int] = None
    is_archived: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalGroup":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description"),
            members=data.get("members", []),
            admins=data.get("admins", []),
            group_type=SignalGroupType(data.get("type", "UNKNOWN")),
            avatar=data.get("avatar"),
            created_at=data.get("createdAt"),
            is_archived=data.get("isArchived", False),
        )


class SignalAdapter:
    """
    Signal Messenger Adapter using signal-cli JSON-RPC interface.

    Provides comprehensive Signal integration:
    - Text and media messaging
    - Group creation and management
    - Reactions and replies
    - Delivery and read receipts
    - Webhook for incoming messages
    - Contact management
    """

    def __init__(
        self,
        phone_number: str,
        socket_path: str = "/tmp/signal.socket",
        config_path: Optional[str] = None,
        signal_cli_path: str = "signal-cli",
        receive_mode: str = "socket",
        webhook_path: str = "/webhooks/signal",
        admin_numbers: Optional[List[str]] = None,
    ):
        """
        Initialize the Signal adapter.

        Args:
            phone_number: Your Signal phone number (with country code)
            socket_path: Path to signal-cli JSON-RPC socket
            config_path: Path to signal-cli configuration directory
            signal_cli_path: Path to signal-cli executable
            receive_mode: 'socket' or 'stdout' for receiving messages
            webhook_path: Webhook endpoint path
            admin_numbers: List of phone numbers with admin privileges
        """
        self.phone_number = phone_number
        self.socket_path = socket_path
        self.config_path = config_path or os.path.expanduser("~/.config/signal")
        self.signal_cli_path = signal_cli_path
        self.receive_mode = receive_mode
        self.webhook_path = webhook_path
        self.admin_numbers = admin_numbers or []

        self.process: Optional[asyncio.subprocess.Process] = None
        self.reader_task: Optional[asyncio.Task] = None
        self.is_initialized = False

        self.registered_numbers: List[str] = []
        self.blocked_numbers: List[str] = []
        self.groups: Dict[str, SignalGroup] = {}

        self.message_cache: Dict[str, Dict[str, Any]] = {}
        self.pending_messages: Dict[str, Dict[str, Any]] = {}

        self.message_handlers: List[Callable] = []
        self.reaction_handlers: List[Callable] = []
        self.receipt_handlers: List[Callable] = []
        self.error_handlers: List[Callable] = []

    async def initialize(self) -> bool:
        """
        Initialize the Signal adapter.

        Returns:
            True if initialization successful
        """
        try:
            if self.receive_mode == "socket":
                await self._start_daemon()
            else:
                await self._start_receive_process()

            self.is_initialized = True
            print(f"[Signal] Adapter initialized for {self.phone_number}")

            # These might fail if no daemon/process is actually running
            try:
                await self._load_groups()
                await self._load_contacts()
            except Exception:
                pass

            return True

        except Exception as e:
            print(f"[Signal] Initialization failed: {e}")
            return False

    async def shutdown(self) -> None:
        """Clean up resources"""
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception:
                pass
            self.process = None

        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
            self.reader_task = None

        self.is_initialized = False
        print("[Signal] Adapter shutdown complete")

    async def _start_daemon(self) -> None:
        """Start signal-cli daemon in JSON-RPC mode"""
        cmd = [
            self.signal_cli_path,
            "daemon",
            "--socket",
            self.socket_path,
            "--dbus",
            "system",
        ]

        env = os.environ.copy()
        env["SIGNAL_CLI_CONFIG"] = self.config_path

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await asyncio.sleep(2)

        if self.process.returncode is not None:
            _, stderr = await self.process.communicate()
            raise Exception(f"signal-cli daemon failed: {stderr.decode()}")

    async def _start_receive_process(self) -> None:
        """Start signal-cli in receive mode for stdout"""
        cmd = [self.signal_cli_path, "receive", "--json"]

        env = os.environ.copy()
        env["SIGNAL_CLI_CONFIG"] = self.config_path

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self.reader_task = asyncio.create_task(self._read_messages())

    async def _read_messages(self) -> None:
        """Read messages from signal-cli stdout"""
        if not self.process or not self.process.stdout:
            return

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode())
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    pass

        except asyncio.CancelledError:
            pass

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming message from signal-cli"""
        try:
            envelope_id = data.get("envelopeId", str(uuid.uuid4()))

            if "dataMessage" in data:
                message = SignalMessage.from_dict(data)
                self.message_cache[envelope_id] = message.__dict__

                platform_msg = await self._to_platform_message(message)

                for handler in self.message_handlers:
                    try:
                        result = handler(platform_msg)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        print(f"[Signal] Message handler error: {e}")

            elif "typing" in data:
                for handler in self.reaction_handlers:
                    try:
                        result = handler(data)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        print(f"[Signal] Typing handler error: {e}")

            elif data.get("type") in ["read", "delivered"]:
                for handler in self.receipt_handlers:
                    try:
                        result = handler(data)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        print(f"[Signal] Receipt handler error: {e}")

        except Exception as e:
            print(f"[Signal] Message handling error: {e}")

    async def _to_platform_message(self, message: SignalMessage) -> PlatformMessage:
        """Convert Signal message to PlatformMessage"""
        chat_id = message.source
        content = message.content or ""

        if message.attachments:
            if any(
                a.content_type and a.content_type.startswith("image/")
                for a in message.attachments
            ):
                msg_type = MessageType.IMAGE
            elif any(
                a.content_type and a.content_type.startswith("video/")
                for a in message.attachments
            ):
                msg_type = MessageType.VIDEO
            elif any(
                a.content_type and a.content_type.startswith("audio/")
                for a in message.attachments
            ):
                msg_type = MessageType.AUDIO
            else:
                msg_type = MessageType.DOCUMENT
        elif message.group_info:
            msg_type = MessageType.TEXT
            chat_id = f"group_{message.group_info.get('id', '')}"
            content = f"[Group] {content}"
        else:
            msg_type = MessageType.TEXT

        return PlatformMessage(
            id=f"signal_{message.id}",
            platform="signal",
            sender_id=message.source,
            sender_name=message.source,
            chat_id=chat_id,
            content=content,
            message_type=msg_type,
            metadata={
                "signal_message_id": message.id,
                "signal_timestamp": message.timestamp,
                "signal_source": message.source,
                "signal_group_id": message.group_info.get("id")
                if message.group_info
                else None,
                "attachments": [a.__dict__ for a in message.attachments],
                "is_unidentified": message.is_unidentified,
            },
        )

    async def _send_json_rpc(self, method: str, params: Dict[str, Any]) -> Any:
        """Send JSON-RPC request to signal-cli"""
        if self.receive_mode == "socket":
            return await self._send_socket_rpc(method, params)
        else:
            return await self._send_stdout_rpc(method, params)

    async def _send_socket_rpc(self, method: str, params: Dict[str, Any]) -> Any:
        """Send JSON-RPC request via socket"""
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)

            request = (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": str(uuid.uuid4()),
                        "method": method,
                        "params": params,
                    }
                )
                + "\n"
            )

            writer.write(request.encode())
            await writer.drain()

            line = await reader.readline()
            writer.close()
            await writer.wait_closed()

            if line:
                result = json.loads(line.decode())
                return result.get("result")
            return None

        except Exception as e:
            print(f"[Signal] RPC error: {e}")
            return None

    async def _send_stdout_rpc(self, method: str, params: Dict[str, Any]) -> Any:
        """Send JSON-RPC request via stdin/stdout"""
        request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": method,
                    "params": params,
                }
            )
            + "\n"
        )

        if self.process and self.process.stdin:
            self.process.stdin.write(request.encode())
            await self.process.stdin.drain()

            await asyncio.sleep(0.5)

            if self.process.stdout:
                line = await self.process.stdout.readline()
                if line:
                    result = json.loads(line.decode())
                    return result.get("result")

        return None

    async def send_message(
        self,
        recipient: str,
        message: str,
        quote_message_id: Optional[str] = None,
        mentions: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Send a text message to a recipient.

        Args:
            recipient: Phone number or group ID
            message: Message text
            quote_message_id: ID of message to quote
            mentions: List of mentioned phone numbers
            attachments: List of file paths to attach

        Returns:
            Message ID or None on failure
        """
        try:
            params: Dict[str, Any] = {"message": message, "recipient": recipient}

            if quote_message_id:
                try:
                    quote_id = int(quote_message_id.split("_")[-1])
                    params["quote"] = {"id": quote_id}
                except (ValueError, IndexError):
                    pass
            if mentions:
                params["mentions"] = mentions
            if attachments:
                params["attachments"] = attachments

            result = await self._send_json_rpc("send", params)

            if result:
                message_id = result.get("envelopeId", str(uuid.uuid4()))
                self.pending_messages[message_id] = {
                    "recipient": recipient,
                    "content": message,
                }
                return message_id

            return None

        except Exception as e:
            print(f"[Signal] Send message error: {e}")
            return None

    async def send_reaction(
        self, recipient: str, emoji: str, target_author: str, target_timestamp: int
    ) -> bool:
        """
        Send a reaction to a message.

        Args:
            recipient: Phone number or group ID
            emoji: Reaction emoji
            target_author: Author of the message to react to
            target_timestamp: Timestamp of message to react to

        Returns:
            True on success
        """
        try:
            params = {
                "recipient": recipient,
                "emoji": emoji,
                "targetAuthor": target_author,
                "targetTimestamp": target_timestamp,
            }

            result = await self._send_json_rpc("react", params)
            return bool(result)

        except Exception as e:
            print(f"[Signal] Send reaction error: {e}")
            return False

    async def send_receipt(
        self, recipient: str, message_ids: List[str], receipt_type: str = "read"
    ) -> bool:
        """
        Send a delivery or read receipt.

        Args:
            recipient: Phone number
            message_ids: List of message IDs
            receipt_type: 'delivered' or 'read'

        Returns:
            True on success
        """
        try:
            timestamps = []
            for m in message_ids:
                try:
                    timestamps.append(int(m.split("_")[-1]))
                except (ValueError, IndexError):
                    pass

            params = {
                "recipient": recipient,
                "type": receipt_type,
                "timestamps": timestamps,
            }

            result = await self._send_json_rpc("sendReceipt", params)
            return bool(result)

        except Exception as e:
            print(f"[Signal] Send receipt error: {e}")
            return False

    async def create_group(
        self,
        name: str,
        members: List[str],
        description: Optional[str] = None,
        avatar_path: Optional[str] = None,
    ) -> Optional[SignalGroup]:
        """
        Create a new Signal group.

        Args:
            name: Group name
            members: List of member phone numbers
            description: Group description
            avatar_path: Path to avatar image

        Returns:
            Created group or None on failure
        """
        try:
            params: Dict[str, Any] = {"name": name, "members": members}

            if description:
                params["description"] = description
            if avatar_path:
                params["avatar"] = avatar_path

            result = await self._send_json_rpc("createGroup", params)

            if result:
                group = SignalGroup(
                    id=result.get("id", ""),
                    name=name,
                    members=members,
                    description=description,
                    created_at=int(datetime.now().timestamp() * 1000),
                )
                self.groups[group.id] = group
                return group

            return None

        except Exception as e:
            print(f"[Signal] Create group error: {e}")
            return None

    async def update_group(
        self,
        group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        avatar_path: Optional[str] = None,
        members_to_add: Optional[List[str]] = None,
        members_to_remove: Optional[List[str]] = None,
        set_admin: Optional[List[str]] = None,
        remove_admin: Optional[List[str]] = None,
    ) -> bool:
        """
        Update group settings.

        Args:
            group_id: Group ID
            name: New group name
            description: New group description
            avatar_path: Path to avatar image
            members_to_add: Members to add
            members_to_remove: Members to remove
            set_admin: Members to promote to admin
            remove_admin: Members to demote from admin

        Returns:
            True on success
        """
        try:
            params: Dict[str, Any] = {"groupId": group_id}

            if name:
                params["name"] = name
            if description:
                params["description"] = description
            if avatar_path:
                params["avatar"] = avatar_path
            if members_to_add:
                params["addMembers"] = members_to_add
            if members_to_remove:
                params["removeMembers"] = members_to_remove
            if set_admin:
                params["setAdmin"] = set_admin
            if remove_admin:
                params["removeAdmin"] = remove_admin

            result = await self._send_json_rpc("updateGroup", params)
            return bool(result)

        except Exception as e:
            print(f"[Signal] Update group error: {e}")
            return False

    async def leave_group(self, group_id: str) -> bool:
        """
        Leave a group.

        Args:
            group_id: Group ID to leave

        Returns:
            True on success
        """
        try:
            params = {"groupId": group_id}
            result = await self._send_json_rpc("leaveGroup", params)
            return bool(result)
        except Exception as e:
            print(f"[Signal] Leave group error: {e}")
            return False

    async def get_groups(self) -> List[SignalGroup]:
        """Get list of all groups"""
        await self._load_groups()
        return list(self.groups.values())

    async def get_group(self, group_id: str) -> Optional[SignalGroup]:
        """Get information about a specific group"""
        if group_id in self.groups:
            return self.groups[group_id]
        try:
            params = {"groupId": group_id}
            result = await self._send_json_rpc("getGroup", params)
            if result:
                group = SignalGroup.from_dict(result)
                self.groups[group.id] = group
                return group
        except Exception as e:
            print(f"[Signal] Get group error: {e}")
        return None

    async def _load_groups(self) -> None:
        """Load groups from signal-cli"""
        try:
            result = await self._send_json_rpc("listGroups", {})
            if result:
                for group_data in result:
                    group = SignalGroup.from_dict(group_data)
                    self.groups[group.id] = group
        except Exception as e:
            print(f"[Signal] Load groups error: {e}")

    async def _load_contacts(self) -> None:
        """Load contacts from signal-cli"""
        try:
            result = await self._send_json_rpc("listContacts", {})
            if result:
                self.registered_numbers = [
                    c.get("number") for c in result if c.get("number")
                ]
        except Exception as e:
            print(f"[Signal] Load contacts error: {e}")

    async def add_contact(self, number: str, name: Optional[str] = None) -> bool:
        """
        Add a contact.

        Args:
            number: Phone number
            name: Contact name

        Returns:
            True on success
        """
        try:
            params: Dict[str, Any] = {"number": number}
            if name:
                params["name"] = name
            result = await self._send_json_rpc("addContact", params)
            if result:
                self.registered_numbers.append(number)
            return bool(result)
        except Exception as e:
            print(f"[Signal] Add contact error: {e}")
            return False

    async def block_contact(self, number: str) -> bool:
        """
        Block a contact.

        Args:
            number: Phone number to block

        Returns:
            True on success
        """
        try:
            params = {"recipient": number}
            result = await self._send_json_rpc("block", params)
            if result:
                if number not in self.blocked_numbers:
                    self.blocked_numbers.append(number)
            return bool(result)
        except Exception as e:
            print(f"[Signal] Block contact error: {e}")
            return False

    async def unblock_contact(self, number: str) -> bool:
        """
        Unblock a contact.

        Args:
            number: Phone number to unblock

        Returns:
            True on success
        """
        try:
            params = {"recipient": number}
            result = await self._send_json_rpc("unblock", params)
            if result and number in self.blocked_numbers:
                self.blocked_numbers.remove(number)
            return bool(result)
        except Exception as e:
            print(f"[Signal] Unblock contact error: {e}")
            return False

    async def register(self, voice: bool = False) -> bool:
        """
        Register this number with Signal.

        Args:
            voice: Use voice call instead of SMS

        Returns:
            True if verification code sent
        """
        try:
            params: Dict[str, Any] = {"number": self.phone_number}
            if voice:
                params["voice"] = True
            result = await self._send_json_rpc("register", params)
            return bool(result)
        except Exception as e:
            print(f"[Signal] Register error: {e}")
            return False

    async def verify(self, code: str) -> bool:
        """
        Verify registration with code.

        Args:
            code: Verification code

        Returns:
            True on success
        """
        try:
            params = {"number": self.phone_number, "code": code}
            result = await self._send_json_rpc("verify", params)
            return bool(result)
        except Exception as e:
            print(f"[Signal] Verify error: {e}")
            return False

    async def send_profile(
        self,
        name: Optional[str] = None,
        avatar_path: Optional[str] = None,
        about: Optional[str] = None,
    ) -> bool:
        """
        Update and send profile.

        Args:
            name: Profile name
            avatar_path: Path to avatar image
            about: About text

        Returns:
            True on success
        """
        try:
            params: Dict[str, Any] = {"number": self.phone_number}

            if name:
                params["name"] = name
            if avatar_path:
                params["avatar"] = avatar_path
            if about:
                params["about"] = about

            result = await self._send_json_rpc("updateProfile", params)
            return bool(result)
        except Exception as e:
            print(f"[Signal] Update profile error: {e}")
            return False

    async def upload_attachment(self, file_path: str) -> Optional[str]:
        """
        Upload an attachment to Signal.

        Args:
            file_path: Path to file

        Returns:
            Attachment ID or None
        """
        try:
            params = {"file": file_path}
            result = await self._send_json_rpc("uploadAttachment", params)
            return result
        except Exception as e:
            print(f"[Signal] Upload attachment error: {e}")
            return None

    async def send_note_to_self(self, message: str) -> Optional[str]:
        """
        Send a note to yourself (Saved Messages).

        Args:
            message: Message text

        Returns:
            Message ID or None
        """
        return await self.send_message(recipient=self.phone_number, message=message)

    async def mark_read(self, message_ids: List[str]) -> bool:
        """
        Mark messages as read.

        Args:
            message_ids: List of message IDs

        Returns:
            True on success
        """
        return await self.send_receipt(
            recipient=self.phone_number, message_ids=message_ids, receipt_type="read"
        )

    def register_message_handler(self, handler: Callable) -> None:
        """Register a message handler"""
        self.message_handlers.append(handler)

    def register_reaction_handler(self, handler: Callable) -> None:
        """Register a reaction/typing handler"""
        self.reaction_handlers.append(handler)

    def register_receipt_handler(self, handler: Callable) -> None:
        """Register a receipt handler"""
        self.receipt_handlers.append(handler)

    def register_error_handler(self, handler: Callable) -> None:
        """Register an error handler"""
        self.error_handlers.append(handler)

    async def handle_webhook(
        self, webhook_data: Dict[str, Any]
    ) -> Optional[PlatformMessage]:
        """
        Handle incoming webhook from signal-cli-http-gateway.

        Args:
            webhook_data: Raw webhook payload

        Returns:
            Processed PlatformMessage or None
        """
        try:
            envelope_id = webhook_data.get("envelopeId", str(uuid.uuid4()))

            if "dataMessage" in webhook_data:
                message = SignalMessage.from_dict(webhook_data)
                self.message_cache[envelope_id] = message.__dict__
                return await self._to_platform_message(message)

            return None

        except Exception as e:
            print(f"[Signal] Webhook error: {e}")
            return None

    def _generate_id(self) -> str:
        """Generate unique message ID"""
        return str(uuid.uuid4())


async def main():
    """Example usage of Signal adapter"""
    adapter = SignalAdapter(
        phone_number="+1234567890", socket_path="/tmp/signal.socket"
    )

    if await adapter.initialize():
        print(f"Signal adapter ready for {adapter.phone_number}")

        adapter.register_message_handler(lambda msg: print(f"Received: {msg.content}"))

        await adapter.send_message(
            recipient="+0987654321", message="Hello from MegaBot Signal Adapter!"
        )


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
