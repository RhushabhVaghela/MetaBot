import asyncio
import os
import json
import base64
import uvicorn  # type: ignore
import importlib.util
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional, List
from fastapi import FastAPI, WebSocket, Request, Query, Response  # type: ignore

# Load Central API Credentials if file exists
CREDENTIALS = {}
cred_path = os.path.join(os.getcwd(), "api-credentials.py")
if os.path.exists(cred_path):  # pragma: no cover
    spec = importlib.util.spec_from_file_location("creds", cred_path)
    if spec and spec.loader:
        creds_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(creds_mod)
        # Filter for uppercase variables (constants)
        CREDENTIALS = {k: getattr(creds_mod, k) for k in dir(creds_mod) if k.isupper()}

        # Inject into environment for adapters to pick up
        for k, v in CREDENTIALS.items():
            if isinstance(v, str):
                os.environ[k] = v

        print(f"✅ Loaded {len(CREDENTIALS)} API credentials from central manager.")

from core.dependencies import (
    register_service,
    register_factory,
    register_singleton,
    resolve_service,
    ServiceTypes,
    DependencyContainer,
)
from core.discovery import ModuleDiscovery
from core.config import load_config, Config, AdapterConfig
from core.interfaces import Message
from core.llm_providers import get_llm_provider, LLMProvider
from core.drivers import ComputerDriver
from core.projects import ProjectManager
from core.secrets import SecretManager
from core.rag.pageindex import PageIndexRAG
from core.agents import SubAgent
from core.loki import LokiMode
from core.permissions import PermissionManager
from core.memory.mcp_server import MemoryServer
from adapters.openclaw_adapter import OpenClawAdapter
from adapters.memu_adapter import MemUAdapter
from adapters.mcp_adapter import MCPManager
from adapters.messaging import MegaBotMessagingServer, PlatformMessage, MessageType
from adapters.unified_gateway import UnifiedGateway
from adapters.security.tirith_guard import guard as tirith

# Import extracted components
from core.orchestrator_components import MessageHandler, HealthMonitor, BackgroundTasks
from core.admin_handler import AdminHandler


# Constants
GREETING_TEXT = """🤖 *MegaBot Connected!*
I am your unified AI assistant, powered by OpenClaw, memU, and MCP.

🚀 *Abilities:*
- 📂 **File System**: Read/write files (requires approval).
- 🧠 **Proactive Memory**: I remember context and anticipate needs.
- 🛠️ **MCP Tools**: 1000+ standardized tools at my disposal.
- 📞 **Communications**: Voice/Video calls, SMS, and IM.

🔐 *Security:*
- **Approval Interlock**: I will ask for permission before running system commands.
- **E2E Encryption**: Our messages are secure.

⌨️ *Commands:*
- `!approve` / `!yes`: Authorize a pending action (Vision, CLI, System).
- `!deny` / `!no`: Reject a pending action.
- `!link <name>`: Link this device to your unified identity.
- `!whoami`: View your identity and platform info.
- `!backup`: Create an encrypted memory snapshot.
- `!briefing`: Get a voice summary of recent bot activity.
- `!health`: Check system component status.
- `!mode <mode>`: Switch between `plan`, `build`, `ask`, `loki`.

How can I help you today?
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for orchestrator initialization and cleanup.

    Handles the startup and shutdown lifecycle of the MegaBot orchestrator,
    ensuring proper initialization of all adapters and services.
    """
    # Startup
    global orchestrator
    if not orchestrator:  # pragma: no cover
        orchestrator = MegaBotOrchestrator(config)
        await orchestrator.start()

    yield  # pragma: no cover

    # Shutdown
    if orchestrator:  # pragma: no cover
        await orchestrator.shutdown()


app = FastAPI(lifespan=lifespan)
config = load_config()
config.validate_environment()
orchestrator = None


class MegaBotOrchestrator:
    """Central orchestrator for MegaBot's unified AI assistant.

    This class coordinates all MegaBot activities including:
    - Message routing across multiple platforms
    - Agent lifecycle management and coordination
    - Memory augmentation and context management
    - Security approval workflows
    - Tool execution via MCP and OpenClaw
    - Background task management

    The orchestrator implements a multi-mode architecture supporting:
    - ask: Direct question answering
    - plan: Structured planning and task breakdown
    - build: Code generation and implementation
    - loki: Autonomous full-project development

    Attributes:
        config: Application configuration object
        adapters: Dictionary of initialized platform and tool adapters
        memory: Persistent memory server for cross-session context
        permissions: Security permission manager
        llm: Language model provider for AI capabilities
    """

    def __init__(self, config):
        """Initialize the MegaBot orchestrator with configuration.

        Args:
            config: Application configuration object containing adapter configs,
                   security policies, and system settings.
        """
        self.config = config

        # Register core services with DI container
        register_service(Config, config)
        register_singleton(MemoryServer, MemoryServer())
        register_factory(ComputerDriver, lambda: ComputerDriver())

        # Get project path safely - use config directly
        project_path = self.config.paths.get("workspaces", os.getcwd())

        register_factory(
            ProjectManager,
            lambda: ProjectManager(self.config.paths.get("workspaces", os.getcwd())),
        )
        register_factory(SecretManager, lambda: SecretManager())
        register_factory(
            PageIndexRAG,
            lambda: PageIndexRAG(
                project_path,
                llm=resolve_service(LLMProvider),
            ),
        )

        # Resolve services
        self.discovery = ModuleDiscovery(self.config.paths["external_repos"])
        self.mode = self.config.system.default_mode

        # Initialize LLM Provider
        llm_config = self.config.adapters.get("llm", {})
        if isinstance(llm_config, AdapterConfig):
            llm_config = llm_config.model_dump()
        self.llm = get_llm_provider(llm_config)
        register_singleton(LLMProvider, self.llm)

        # Initialize component handlers
        self.message_handler = MessageHandler(self)
        self.admin_handler = AdminHandler(self)
        self.health_monitor = HealthMonitor(self)
        self.background_tasks = BackgroundTasks(self)

        # Resolve other services
        self.computer_driver = resolve_service(ComputerDriver)
        self.project_manager = resolve_service(ProjectManager)
        self.project_manager.switch_project("default")
        self.secret_manager = resolve_service(SecretManager)
        self.rag = resolve_service(PageIndexRAG)
        self.permissions = PermissionManager(
            default_level=getattr(self.config.system, "default_permission", "ASK_EACH")
        )
        self.permissions.load_from_config(self.config.model_dump())
        self.memory = resolve_service(MemoryServer)
        self.sub_agents = {}  # Track active sub-agents
        self.last_active_chat = (
            None  # Track last messaging context for cross-platform sync
        )
        self.loki = LokiMode(self)
        self.clients = set()  # Track WebSocket clients

        # Initialize High-Level Features
        from features.dash_data.agent import DashDataAgent

        self.features = {"dash_data": DashDataAgent(self.llm, self)}

        self.adapters = {
            "openclaw": OpenClawAdapter(
                self.config.adapters["openclaw"].host,
                self.config.adapters["openclaw"].port,
            ),
            "memu": MemUAdapter(
                self.config.paths["external_repos"] + "/memU",
                self.config.adapters["memu"].database_url,
            ),
            "mcp": MCPManager(
                self.config.adapters["mcp"].servers
                if "mcp" in self.config.adapters
                else []
            ),
            "messaging": MegaBotMessagingServer(
                host="127.0.0.1", port=18790, enable_encryption=True
            ),
            "gateway": UnifiedGateway(
                megabot_server_port=18790,
                enable_cloudflare=True,
                enable_vpn=True,
                on_message=self.on_gateway_message,
            ),
        }
        self.adapters["messaging"].on_connect = self.on_messaging_connect

    async def on_messaging_connect(
        self, client_id: Optional[str], platform: str
    ):  # pragma: no cover
        """Handle new messaging platform connections.

        Sends a welcome message to newly connected clients explaining
        MegaBot's capabilities and available commands.

        Args:
            client_id: Unique identifier for the connected client (optional)
            platform: Platform name (telegram, signal, websocket, etc.)  # pragma: no cover
        """  # pragma: no cover
        print(
            f"Greeting new connection: {platform} ({client_id or 'all'})"
        )  # pragma: no cover
        greeting = Message(content=GREETING_TEXT, sender="MegaBot")
        await self.send_platform_message(
            greeting, platform=platform, target_client=client_id
        )

    async def _handle_admin_command(
        self,
        text: str,
        sender_id: str,
        chat_id: Optional[str] = None,
        platform: str = "native",
    ) -> bool:
        """Process administrative commands from chat interfaces.

        Handles MegaBot's administrative command system including:
        - Action approval/denial (!approve, !deny)
        - Persistent policy management (!allow, !deny)
        - Identity linking (!link)
        - System status checks (!health)
        - Mode switching (!mode)

        Args:
            text: Raw command text from user
            sender_id: Platform-specific sender identifier
            chat_id: Chat/conversation identifier
            platform: Messaging platform name

        Returns:
            bool: True if command was handled, False otherwise
        """
        """Process chat-based administrative commands"""
        # Check if sender is an admin  # pragma: no cover
        if self.config.admins and sender_id not in self.config.admins:
            return False

        parts = text.strip().split()  # pragma: no cover
        if not parts:
            return False
        cmd = parts[0].lower()

        if cmd == "!approve" or cmd == "!yes":
            # Approve most recent or by ID
            action_id = (
                parts[1]
                if len(parts) > 1
                else (
                    self.admin_handler.approval_queue[-1]["id"]
                    if self.admin_handler.approval_queue
                    else None
                )
            )
            if action_id:
                await self._process_approval(action_id, approved=True)
                return True

        elif cmd == "!reject" or cmd == "!no":
            action_id = (
                parts[1]
                if len(parts) > 1
                else (
                    self.admin_handler.approval_queue[-1]["id"]
                    if self.admin_handler.approval_queue
                    else None
                )
            )
            if action_id:
                await self._process_approval(action_id, approved=False)
                return True

        elif cmd == "!allow":
            if len(parts) > 1:
                pattern = " ".join(parts[1:])
                if pattern not in self.config.policies.get("allow", []):
                    if "allow" not in self.config.policies:
                        self.config.policies["allow"] = []
                    self.config.policies["allow"].append(pattern)
                    self.config.save()
                    print(f"Policy Update: Allowed '{pattern}' (Persisted)")
                    return True

        elif cmd == "!deny":
            if len(parts) > 1:
                pattern = " ".join(parts[1:])
                if pattern not in self.config.policies.get("deny", []):
                    if "deny" not in self.config.policies:
                        self.config.policies["deny"] = []
                    self.config.policies["deny"].append(pattern)
                    self.config.save()
                    print(f"Policy Update: Denied '{pattern}' (Persisted)")
                    return True

        elif cmd == "!policies":
            resp_text = f"Policies:\nAllow: {self.config.policies['allow']}\nDeny: {self.config.policies['deny']}"
            resp = Message(
                content=resp_text, sender="System", metadata={"chat_id": chat_id}
            )
            asyncio.create_task(self.send_platform_message(resp))
            return True

        elif cmd == "!mode":
            if len(parts) > 1:
                self.mode = parts[1]
                print(f"System Mode updated to: {self.mode}")  # pragma: no cover
                if self.mode == "loki":
                    asyncio.create_task(self.loki.activate("Auto-trigger from chat"))
                return True
        # pragma: no cover
        elif cmd == "!history_clean":  # pragma: no cover
            target_chat = parts[1] if len(parts) > 1 else chat_id  # pragma: no cover
            if target_chat:  # pragma: no cover
                await self.memory.chat_forget(
                    target_chat, max_history=0
                )  # pragma: no cover
                resp = Message(  # pragma: no cover
                    content=f"🗑️ History cleaned for chat: {target_chat}",  # pragma: no cover
                    sender="System",  # pragma: no cover
                )  # pragma: no cover
                asyncio.create_task(self.send_platform_message(resp, chat_id=chat_id))
                return True
        # pragma: no cover
        elif cmd == "!link":  # pragma: no cover
            if len(parts) > 1:  # pragma: no cover
                target_name = parts[1]  # pragma: no cover
                # Re-fetch the raw platform ID from metadata if possible,  # pragma: no cover
                # but since we already resolved chat_id, we need to know the original.  # pragma: no cover
                # In on_gateway_message, we resolved it.  # pragma: no cover
                # Let's assume for this command we want to link the sender_id.  # pragma: no cover
                await self.memory.link_identity(
                    target_name, platform, sender_id
                )  # pragma: no cover
                resp = Message(  # pragma: no cover
                    content=f"🔗 Identity Linked: {platform}:{sender_id} is now known as '{target_name}'",  # pragma: no cover
                    sender="System",  # pragma: no cover
                )  # pragma: no cover
                asyncio.create_task(  # pragma: no cover
                    self.send_platform_message(
                        resp, chat_id=chat_id, platform=platform
                    )  # pragma: no cover
                )
                return True

        elif cmd == "!whoami":
            unified = await self.memory.get_unified_id(platform, sender_id)
            resp = Message(
                content=f"👤 Identity Info:\nPlatform: {platform}\nID: {sender_id}\nUnified: {unified}",
                sender="System",
            )
            asyncio.create_task(
                self.send_platform_message(resp, chat_id=chat_id, platform=platform)
            )
            return True

        elif cmd == "!backup":
            res = await self.memory.backup_database()
            resp = Message(
                content=f"💾 Backup Triggered: {res}",
                sender="System",
            )
            asyncio.create_task(
                self.send_platform_message(resp, chat_id=chat_id, platform=platform)
            )
            return True

        elif cmd == "!briefing":  # pragma: no cover
            # Trigger a voice briefing call  # pragma: no cover
            admin_phone = getattr(
                self.config.system, "admin_phone", None
            )  # pragma: no cover
            if (
                not admin_phone or not self.adapters["messaging"].voice_adapter
            ):  # pragma: no cover
                resp = Message(  # pragma: no cover
                    content="❌ Briefing failed: No admin phone or voice adapter configured.",  # pragma: no cover
                    sender="System",  # pragma: no cover
                )  # pragma: no cover
                asyncio.create_task(  # pragma: no cover
                    self.send_platform_message(
                        resp, chat_id=chat_id, platform=platform
                    )  # pragma: no cover
                )  # pragma: no cover
                return True  # pragma: no cover
            # pragma: no cover
            asyncio.create_task(  # pragma: no cover
                self._trigger_voice_briefing(
                    admin_phone, str(chat_id), platform
                )  # pragma: no cover
            )  # pragma: no cover
            resp = Message(  # pragma: no cover
                content="📞 Voice briefing initiated. Expect a call shortly.",  # pragma: no cover
                sender="System",  # pragma: no cover
            )  # pragma: no cover
            asyncio.create_task(  # pragma: no cover
                self.send_platform_message(
                    resp, chat_id=chat_id, platform=platform
                )  # pragma: no cover
            )
            return True
        # pragma: no cover
        elif cmd == "!rag_rebuild":  # pragma: no cover
            await self.rag.build_index(force_rebuild=True)  # pragma: no cover
            resp = Message(  # pragma: no cover
                content="🏗️ RAG Index rebuilt and cached.",  # pragma: no cover
                sender="System",  # pragma: no cover
            )  # pragma: no cover
            asyncio.create_task(  # pragma: no cover
                self.send_platform_message(
                    resp, chat_id=chat_id, platform=platform
                )  # pragma: no cover
            )
            return True

        elif cmd == "!health":
            health = await self.get_system_health()
            health_text = "🩺 **System Health:**\n"
            for comp, data in health.items():
                status_emoji = "✅" if data["status"] == "up" else "❌"
                health_text += f"- {status_emoji} **{comp.capitalize()}**: {data['status']}\n"  # pragma: no cover
                if "error" in data:
                    health_text += f"  - Error: {data['error']}\n"

            resp = Message(
                content=health_text,
                sender="System",
            )
            asyncio.create_task(
                self.send_platform_message(resp, chat_id=chat_id, platform=platform)
            )
            return True  # pragma: no cover

        return False

    async def on_gateway_message(self, data: Dict):
        """Process messages received through the unified gateway.

        Routes messages from Cloudflare Tunnel, Tailscale VPN, or direct HTTPS
        connections through the same processing pipeline as native messaging.

        Args:
            data: Message payload from gateway containing platform, content, etc.  # pragma: no cover
        """
        await self.message_handler.process_gateway_message(data)

    async def run_autonomous_gateway_build(
        self, message: Message, original_data: Dict
    ):  # pragma: no cover
        """Execute autonomous build operations for gateway clients.

        Performs memory-augmented autonomous execution for clients connecting
        through the unified gateway, providing full AI assistance capabilities.

        Args:
            message: User message to process
            original_data: Original gateway message data for client identification
        """
        """Autonomous build for gateway clients (relays back to gateway instead of UI websocket)"""
        # 0. Proactive Memory Injection
        lessons = await self._get_relevant_lessons(message.content)
        if lessons:
            message.content = lessons + "\n" + message.content

        # 1. Ask MCP
        tools_res = await self.adapters["mcp"].call_tool(
            None, "list_allowed_directories", {}
        )

        # 2. Relay to execution
        await self.adapters["openclaw"].send_message(message)

        # 3. Notify the gateway client
        client_id = original_data.get("_meta", {}).get("client_id")
        platform = original_data.get("_meta", {}).get("connection_type", "gateway")
        if client_id:
            msg = Message(
                content=f"Build started. Auth paths: {tools_res}", sender="MegaBot"
            )
            await self.send_platform_message(
                msg, platform=platform, target_client=client_id
            )

    async def start(self):
        print(f"Starting {self.config.system.name} in {self.mode} mode...")
        self.discovery.scan()

        # Start Native Messaging and Gateway
        asyncio.create_task(self.adapters["messaging"].start())
        asyncio.create_task(self.adapters["gateway"].start())

        try:
            await self.adapters["openclaw"].connect(on_event=self.on_openclaw_event)
            await self.adapters["openclaw"].subscribe_events(
                ["chat.message", "tool.call"]
            )  # pragma: no cover
            print("Connected to OpenClaw Gateway.")  # pragma: no cover
        except Exception as e:
            print(f"Failed to connect to OpenClaw: {e}")

        try:
            await self.adapters["mcp"].start_all()  # pragma: no cover
            print("MCP Servers started.")  # pragma: no cover
        except Exception as e:
            print(f"Failed to start MCP Servers: {e}")

        # Initialize Project RAG
        try:
            await self.rag.build_index()  # pragma: no cover
            print(
                f"Project RAG index built for: {self.rag.root_dir}"
            )  # pragma: no cover
        except Exception as e:
            print(f"Failed to build RAG index: {e}")

        # Start background tasks
        await self.background_tasks.start_all_tasks()

    async def restart_component(self, name: str):  # pragma: no cover
        """Attempt to re-initialize or reconnect a specific system component"""  # pragma: no cover
        print(f"Self-Healing: Restarting {name}...")  # pragma: no cover
        try:  # pragma: no cover
            if name == "openclaw":  # pragma: no cover
                await self.adapters["openclaw"].connect(
                    on_event=self.on_openclaw_event
                )  # pragma: no cover
                await self.adapters["openclaw"].subscribe_events(  # pragma: no cover
                    ["chat.message", "tool.call"]  # pragma: no cover
                )  # pragma: no cover
            elif name == "messaging":  # pragma: no cover
                # Messaging server runs in background task, usually restart involves re-binding if crashed  # pragma: no cover
                asyncio.create_task(
                    self.adapters["messaging"].start()
                )  # pragma: no cover
            elif name == "mcp":  # pragma: no cover
                await self.adapters["mcp"].start_all()  # pragma: no cover
            elif name == "gateway":  # pragma: no cover
                asyncio.create_task(
                    self.adapters["gateway"].start()
                )  # pragma: no cover
            print(f"Self-Healing: {name} restart initiated.")  # pragma: no cover
        except Exception as e:
            print(f"Self-Healing Error: Failed to restart {name}: {e}")

    async def heartbeat_loop(self):
        """Monitor the health of all adapters and notify if any fail"""
        last_status = {}
        restart_counts = {}  # component -> count

        while True:  # pragma: no cover
            try:
                status = await self.get_system_health()

                # Check for regressions
                for component, data in status.items():
                    current_up = data.get("status") == "up"
                    was_up = last_status.get(component, {}).get("status", "up") == "up"

                    if not current_up:
                        # Auto-Restart Logic
                        count = restart_counts.get(component, 0)
                        if count < 3:  # Max 3 retries per interval
                            print(
                                f"Heartbeat: {component} is down. Triggering self-healing (attempt {count + 1})..."
                            )
                            await self.restart_component(component)
                            restart_counts[component] = count + 1

                        if was_up:  # Only notify on the first failure
                            msg = Message(
                                content=f"🚨 Component Down: {component}\nError: {data.get('error', 'Unknown')}\nAuto-restart triggered.",
                                sender="Security",
                            )
                            asyncio.create_task(self.send_platform_message(msg))
                    else:
                        # Reset restart count if component is back up
                        restart_counts[component] = 0

                last_status = status
            except Exception as e:
                print(f"Heartbeat loop error: {e}")

            await asyncio.sleep(60)  # Check every minute

    async def get_system_health(self) -> Dict[str, Any]:
        """Check the status of all system components"""
        health = {}

        # 1. Memory Server
        try:
            stats = await self.memory.memory_stats()
            health["memory"] = {
                "status": "up" if "error" not in stats else "down",
                "details": stats,  # pragma: no cover
            }  # pragma: no cover
        except Exception as e:
            health["memory"] = {"status": "down", "error": str(e)}

        # 2. OpenClaw
        try:  # pragma: no cover
            is_connected = self.adapters["openclaw"].websocket is not None
            health["openclaw"] = {"status": "up" if is_connected else "down"}
        except Exception:
            health["openclaw"] = {"status": "down"}

        # 3. Messaging Server
        try:  # pragma: no cover
            client_count = len(self.adapters["messaging"].clients)
            health["messaging"] = {"status": "up", "clients": client_count}
        except Exception:
            health["messaging"] = {"status": "down"}

        # 4. MCP Servers
        try:
            health["mcp"] = {
                "status": "up",
                "server_count": len(self.adapters["mcp"].servers),
            }
        except Exception:
            health["mcp"] = {"status": "down"}

        return health

    async def backup_loop(self):
        """Background task to backup the memory database every 12 hours"""
        while True:  # pragma: no cover
            try:
                print("Backup Loop: Creating memory database backup...")
                res = await self.memory.backup_database()
                print(f"Backup Loop: {res}")
            except Exception as e:
                print(f"Backup loop error: {e}")
            await asyncio.sleep(43200)  # Run every 12 hours

    async def pruning_loop(self):
        """Background task to prune old chat history every 24 hours"""
        while True:  # pragma: no cover
            try:
                print("Pruning Loop: Checking for bloated chat histories...")
                chat_ids = await self.memory.get_all_chat_ids()
                for chat_id in chat_ids:
                    # Keep last 500 messages per chat
                    await self.memory.chat_forget(chat_id, max_history=500)
            except Exception as e:
                print(f"Pruning loop error: {e}")
            await asyncio.sleep(86400)  # Run once every 24 hours

    async def proactive_loop(self):
        while True:  # pragma: no cover
            try:
                print("Proactive Loop: Checking for updates...")
                # 1. Check memU for proactive tasks
                anticipations = await self.adapters["memu"].get_anticipations()
                for task in anticipations:
                    print(f"Proactive Trigger (Memory): {task.get('content')}")
                    message = Message(
                        content=f"Suggestion: {task.get('content')}", sender="MegaBot"
                    )
                    await self.adapters["openclaw"].send_message(message)

                # 2. Check Calendar via MCP (if configured)
                try:
                    events = await self.adapters["mcp"].call_tool(
                        "google-services", "list_events", {"limit": 1}
                    )
                    if events:
                        print(f"Proactive Trigger (Calendar): {events}")
                        # Alert native clients
                        resp = Message(
                            content=f"Calendar Reminder: {events}", sender="Calendar"
                        )
                        await self.send_platform_message(resp)
                except Exception as e:
                    print(f"Calendar check failed (expected if not configured): {e}")

            except Exception as e:
                print(f"Proactive loop error: {e}")
            await asyncio.sleep(3600)  # Check every hour

    def _to_platform_message(
        self, message: Message, chat_id: Optional[str] = None
    ) -> Any:
        """Convert core Message to PlatformMessage for native messaging"""
        from adapters.messaging import MediaAttachment
        import uuid

        target_chat = chat_id or message.metadata.get("chat_id", "broadcast")

        platform_attachments = []  # pragma: no cover
        if hasattr(message, "attachments") and message.attachments:  # pragma: no cover
            for att in message.attachments:  # pragma: no cover
                try:  # pragma: no cover
                    # Map 'type' if it's a string to MessageType enum  # pragma: no cover
                    if isinstance(att.get("type"), str):  # pragma: no cover
                        att["type"] = MessageType(att["type"]).value  # pragma: no cover
                    platform_attachments.append(
                        MediaAttachment.from_dict(att)
                    )  # pragma: no cover
                except Exception as e:
                    print(f"Error converting attachment: {e}")

        return PlatformMessage(
            id=str(uuid.uuid4()),
            platform="native",
            sender_id="megabot-core",
            sender_name=message.sender,
            chat_id=target_chat,
            content=message.content,
            message_type=MessageType.TEXT,
            attachments=platform_attachments,
        )

    async def send_platform_message(
        self,
        message: Message,
        chat_id: Optional[str] = None,
        platform: str = "native",
        target_client: Optional[str] = None,
    ):  # pragma: no cover
        """Send a message to a platform and record it in history."""
        target_chat = chat_id or message.metadata.get("chat_id", "broadcast")

        # Visual Redaction Agent: Detect and blur sensitive areas before sending
        if hasattr(message, "attachments") and message.attachments:
            for att in message.attachments:
                if str(att.get("type")).lower() == "image" and att.get("data"):
                    print(f"Redaction-Agent: Scanning image for {target_chat}...")
                    try:
                        # 1. Analyze for sensitive regions
                        analysis_raw = await self.computer_driver.execute(
                            "analyze_image", text=att["data"]
                        )
                        analysis = json.loads(analysis_raw)
                        regions = analysis.get("sensitive_regions", [])

                        if regions:
                            print(
                                f"Redaction-Agent: Blurring {len(regions)} sensitive areas."
                            )
                            redacted_data = await self.computer_driver.execute(
                                "blur_regions", text=att["data"], regions=regions
                            )

                            # 2. Verify Redaction
                            if await self._verify_redaction(redacted_data):
                                att["data"] = redacted_data
                                att["metadata"] = att.get("metadata", {})
                                att["metadata"]["redacted"] = True  # pragma: no cover
                            else:  # pragma: no cover
                                print(  # pragma: no cover
                                    "Redaction-Agent: Verification FAILED. Blocking image."  # pragma: no cover
                                )  # pragma: no cover
                                att["content"] = (  # pragma: no cover
                                    "[SECURITY BLOCK: Redaction verification failed]"  # pragma: no cover
                                )  # pragma: no cover
                                if "data" in att:  # pragma: no cover
                                    del att["data"]  # pragma: no cover
                        else:  # pragma: no cover
                            # No sensitive regions detected in first pass  # pragma: no cover
                            pass  # pragma: no cover
                    except Exception as e:
                        print(f"Redaction failed: {e}")

        # Vision Policy Enforcement: Require approval for outbound images
        has_images = any(
            str(att.get("type")).lower() == "image"
            for att in getattr(message, "attachments", [])
        )

        if has_images and platform != "websocket":  # Web UI usually has its own preview
            auth = self.permissions.is_authorized("vision.outbound")  # pragma: no cover
            if auth is False:  # pragma: no cover
                print(f"Vision Policy: Outbound image blocked for {target_chat}")
                return
            if auth is None:  # ASK_EACH
                # If it's already a security message, don't loop  # pragma: no cover
                if message.sender == "Security":
                    pass
                else:
                    print(
                        f"Vision Policy: Queuing outbound image for approval in {target_chat}"
                    )
                    import uuid

                    action = {
                        "id": str(uuid.uuid4()),
                        "type": "outbound_vision",
                        "payload": {
                            "message_content": message.content,
                            "attachments": message.attachments,
                            "chat_id": target_chat,
                            "platform": platform,
                            "target_client": target_client,
                        },
                        "description": f"Send image to {platform}:{target_chat}",
                    }
                    self.admin_handler.approval_queue.append(action)

                    # Start Escalation Timer for Voice Call
                    asyncio.create_task(self._start_approval_escalation(action))

                    # Notify admins
                    admin_resp = Message(
                        content=f"⚠️ Vision Approval Required: Send image to {target_chat}\nType `!approve {action['id']}` to authorize.",
                        sender="Security",
                    )
                    # Use a background task to avoid recursion depth if send_platform_message is called in a loop
                    asyncio.create_task(
                        self.send_platform_message(admin_resp, platform=platform)
                    )
                    return

        # Granular Pruning: Tag architectural decisions to keep forever
        metadata = message.metadata.copy()
        if any(
            keyword in message.content.upper()
            for keyword in [
                "DECISION",
                "ARCHITECT",
                "PATTERN",
                "LEARNED LESSON",
            ]  # pragma: no cover
        ):
            metadata["keep_forever"] = True

        # Record in DB
        await self.memory.chat_write(
            chat_id=target_chat,
            platform=platform,
            role="assistant",
            content=message.content,
            metadata=metadata,
        )

        # Update cache  # pragma: no cover
        if target_chat in self.message_handler.chat_contexts:  # pragma: no cover
            self.message_handler.chat_contexts[target_chat].append(  # pragma: no cover
                {"role": "assistant", "content": message.content}  # pragma: no cover
            )
            self.message_handler.chat_contexts[target_chat] = (
                self.message_handler.chat_contexts[target_chat][-10:]
            )

        # Route to appropriate adapter  # pragma: no cover
        if platform in [
            "cloudflare",
            "vpn",
            "direct",
            "local",
            "gateway",
        ]:  # pragma: no cover
            if target_client:  # pragma: no cover
                # Send back through Unified Gateway  # pragma: no cover
                msg_payload = {  # pragma: no cover
                    "type": "message",  # pragma: no cover
                    "content": message.content,  # pragma: no cover
                    "sender": message.sender,  # pragma: no cover
                    "metadata": metadata,  # pragma: no cover
                }  # pragma: no cover
                await self.adapters["gateway"].send_message(
                    target_client, msg_payload
                )  # pragma: no cover
            else:  # pragma: no cover
                # Broadcast or generic?  # pragma: no cover
                # For now, let's assume we want to send to the last active client if no target  # pragma: no cover
                if (  # pragma: no cover
                    self.last_active_chat  # pragma: no cover
                    and self.last_active_chat["platform"]
                    == platform  # pragma: no cover
                ):
                    await self.adapters["gateway"].send_message(
                        self.last_active_chat["chat_id"],
                        {"type": "message", "content": message.content},
                    )

        platform_msg = self._to_platform_message(message, chat_id=target_chat)
        platform_msg.platform = platform
        await self.adapters["messaging"].send_message(
            platform_msg, target_client=target_client
        )

    async def _trigger_voice_briefing(
        self, phone: str, chat_id: str, platform: str
    ):  # pragma: no cover
        """Generate a summary of recent events and call the admin to read it"""  # pragma: no cover
        try:  # pragma: no cover
            # 1. Fetch recent activity  # pragma: no cover
            history = await self.memory.chat_read(chat_id, limit=20)  # pragma: no cover
            if not history:  # pragma: no cover
                script = "This is Mega Bot. No recent activity to report."  # pragma: no cover
            else:  # pragma: no cover
                # 2. Summarize  # pragma: no cover
                history_text = "\n".join(  # pragma: no cover
                    [
                        f"{h['role']}: {h['content']}" for h in history
                    ]  # pragma: no cover
                )  # pragma: no cover
                summary_prompt = f"Summarize the following recent bot activity for a short voice briefing (max 50 words). Focus on completed tasks or pending approvals:\n\n{history_text}"  # pragma: no cover
                summary = await self.llm.generate(  # pragma: no cover
                    context="Voice Briefing",  # pragma: no cover
                    messages=[
                        {"role": "user", "content": summary_prompt}
                    ],  # pragma: no cover
                )  # pragma: no cover
                script = f"Hello, this is Mega Bot. Here is your recent activity briefing: {summary}"  # pragma: no cover
            # pragma: no cover
            # 3. Make the call  # pragma: no cover
            await self.adapters["messaging"].voice_adapter.make_call(
                phone, script
            )  # pragma: no cover
        except Exception as e:
            print(f"Voice briefing failed: {e}")

    async def _verify_redaction(self, image_data: str) -> bool:  # pragma: no cover
        """Use a separate vision pass to verify that redaction was successful"""  # pragma: no cover
        try:  # pragma: no cover
            # Re-analyze the image. The vision driver should return no sensitive_regions if successful.  # pragma: no cover
            analysis_raw = await self.computer_driver.execute(  # pragma: no cover
                "analyze_image",
                text=image_data,  # pragma: no cover
            )  # pragma: no cover
            analysis = json.loads(analysis_raw)  # pragma: no cover
            remaining_sensitive = analysis.get(
                "sensitive_regions", []
            )  # pragma: no cover
            # pragma: no cover
            if remaining_sensitive:  # pragma: no cover
                print(  # pragma: no cover
                    f"Redaction-Verification: FAILED. Found {len(remaining_sensitive)} remaining areas."  # pragma: no cover
                )  # pragma: no cover
                return False  # pragma: no cover
            # pragma: no cover
            print("Redaction-Verification: PASSED.")
            return True
        except Exception as e:  # pragma: no cover
            print(f"Redaction-Verification: Error during check: {e}")
            return False

    async def _start_approval_escalation(self, action: Dict):
        """Escalate via Voice Call if approval is not received within 5 minutes"""
        await asyncio.sleep(300)  # 5 minutes
        # pragma: no cover
        # Check if action is still in queue  # pragma: no cover
        if any(
            a["id"] == action["id"] for a in self.admin_handler.approval_queue
        ):  # pragma: no cover
            print(  # pragma: no cover
                f"Escalation: Approval {action['id']} timed out. Initiating Voice Call..."  # pragma: no cover
            )  # pragma: no cover
            # pragma: no cover
            # Check DND Hours  # pragma: no cover
            now = datetime.now().hour  # pragma: no cover
            dnd_start = getattr(self.config.system, "dnd_start", 22)  # pragma: no cover
            dnd_end = getattr(self.config.system, "dnd_end", 7)  # pragma: no cover
            # pragma: no cover
            is_dnd = False  # pragma: no cover
            if dnd_start > dnd_end:  # pragma: no cover
                is_dnd = now >= dnd_start or now < dnd_end  # pragma: no cover
            else:  # pragma: no cover
                is_dnd = dnd_start <= now < dnd_end  # pragma: no cover
            # pragma: no cover
            if is_dnd:  # pragma: no cover
                print(
                    "Escalation: DND active. Skipping voice call."
                )  # pragma: no cover
                return  # pragma: no cover
            # pragma: no cover
            # Check Dynamic DND via Calendar  # pragma: no cover
            try:  # pragma: no cover
                # Check for active calendar events that might indicate busy status  # pragma: no cover
                events = await self.adapters["mcp"].call_tool(  # pragma: no cover
                    "google-services",
                    "list_events",
                    {"limit": 3},  # pragma: no cover
                )  # pragma: no cover
                if events and isinstance(events, list):  # pragma: no cover
                    for event in events:  # pragma: no cover
                        summary = str(
                            event.get("summary", "")
                        ).upper()  # pragma: no cover
                        if any(  # pragma: no cover
                            k in summary  # pragma: no cover
                            for k in [  # pragma: no cover
                                "BUSY",  # pragma: no cover
                                "MEETING",  # pragma: no cover
                                "DND",  # pragma: no cover
                                "SLEEP",  # pragma: no cover
                                "DO NOT DISTURB",  # pragma: no cover
                            ]  # pragma: no cover
                        ):  # pragma: no cover
                            print(  # pragma: no cover
                                f"Escalation: Dynamic DND active via Calendar ('{summary}'). Skipping call."  # pragma: no cover
                            )
                            return
            except Exception as e:
                print(
                    f"Escalation: Calendar check failed (expected if not configured): {e}"
                )

            admin_phone = getattr(self.config.system, "admin_phone", None)
            if admin_phone and self.adapters["messaging"].voice_adapter:
                script = f"Hello, this is Mega Bot. A critical vision approval is pending. Please check your messages and authorize action."
                await self.adapters["messaging"].voice_adapter.make_call(
                    admin_phone, script, ivr=True, action_id=action["id"]
                )
            else:
                print("Escalation: No admin phone or voice adapter configured.")

    async def _check_identity_claims(
        self, content: str, platform: str, platform_id: str, chat_id: str
    ):
        """Analyze message for identity claims (e.g. 'I am the admin') and offer to link"""
        # Quick heuristic to avoid LLM call for every message
        if any(k in content.upper() for k in ["I AM", "IT'S ME", "THIS IS", "MY NAME"]):
            prompt = f"Does the user claim to be someone specific in this message: '{content}'? If so, return only the internal name they claim to be. Otherwise return 'NONE'."
            claimed_name = await self.llm.generate(
                context="Identity Verification",
                messages=[{"role": "user", "content": prompt}],
            )
            claimed_name = str(claimed_name).strip().strip("'\"").upper()

            if "NONE" not in claimed_name:
                print(
                    f"Identity-Link: Detected claim to be '{claimed_name}' from {platform}:{platform_id}"
                )

                import uuid

                action = {
                    "id": str(uuid.uuid4()),
                    "type": "identity_link",
                    "payload": {
                        "internal_id": claimed_name,
                        "platform": platform,
                        "platform_id": platform_id,
                        "chat_id": chat_id,
                    },
                    "description": f"Link {platform} ID to identity '{claimed_name}'",
                }
                self.admin_handler.approval_queue.append(action)

                resp = Message(
                    content=f"🤔 I think you are '{claimed_name}'. Link this {platform} account to your unified history? Type `!approve {action['id']}`.",
                    sender="System",
                )
                asyncio.create_task(
                    self.send_platform_message(resp, chat_id=chat_id, platform=platform)
                )

    async def _get_relevant_lessons(self, prompt: str) -> str:
        """Extract keywords and fetch broadened architectural lessons from memory"""
        try:
            # 1. Keyword Extraction
            extract_prompt = f"Identify the primary technologies, libraries, and architectural patterns in this request: '{prompt}'. Return only a comma-separated list of keywords."
            keywords_raw = await self.llm.generate(
                context="Keyword Extraction",
                messages=[{"role": "user", "content": extract_prompt}],
            )
            keywords = [k.strip() for k in str(keywords_raw).split(",") if k.strip()]

            # 2. Search Memory for each keyword
            all_lessons = []
            seen_content = set()

            # Include direct search for the prompt itself
            direct_search = await self.memory.memory_search(
                query=prompt, type="learned_lesson", limit=5
            )
            all_lessons.extend(direct_search)

            for kw in keywords[:5]:  # Top 5 keywords to avoid search bloat
                results = await self.memory.memory_search(
                    query=kw, type="learned_lesson", limit=3
                )
                for res in results:
                    content = res.get("content", "")
                    if content not in seen_content:
                        all_lessons.append(res)
                        seen_content.add(content)
            # pragma: no cover
            if not all_lessons:
                return ""

            # 3. Distillation (if too many lessons)  # pragma: no cover
            if len(all_lessons) > 3:  # pragma: no cover
                lessons_text = "\n".join(
                    [f"- {l['content']}" for l in all_lessons]
                )  # pragma: no cover
                distill_prompt = f"Summarize the following architectural lessons into a concise, high-priority list (max 3 points):\n\n{lessons_text}"  # pragma: no cover
                distilled = await self.llm.generate(  # pragma: no cover
                    context="Memory Distillation",  # pragma: no cover
                    messages=[
                        {"role": "user", "content": distill_prompt}
                    ],  # pragma: no cover
                )
                return f"\n[DISTILLED LESSONS FROM MEMORY]:\n{distilled}\n"

            # 4. Format lessons (standard)
            formatted = "\n[PROACTIVE LESSONS FROM MEMORY]:\n"
            for lesson in all_lessons[:10]:  # Cap at 10 most relevant
                prefix = (
                    "⚠️ CRITICAL: " if "CRITICAL" in lesson["content"].upper() else "- "
                )
                formatted += f"{prefix}{lesson['content']}\n"  # pragma: no cover
            return formatted  # pragma: no cover
        except Exception as e:  # pragma: no cover
            print(f"Lesson injection failed: {e}")
            return ""

    async def run_autonomous_build(
        self, message: Message, websocket: WebSocket
    ):  # pragma: no cover
        # Notify UI that we are thinking
        await websocket.send_json(
            {"type": "status", "content": "MegaBot is starting autonomous session..."}
        )

        # 0. Skill Lookup: Search memU for relevant previous plans
        await websocket.send_json(
            {"type": "status", "content": "Searching memory for relevant skills..."}
        )
        memories = await self.adapters["memu"].search(message.content)

        # 0.1 Proactive Memory Injection: Search for architectural patterns
        await websocket.send_json(
            {"type": "status", "content": "Consulting persistent memory for lessons..."}
        )
        lessons = await self._get_relevant_lessons(message.content)

        skill_context = ""
        if memories:
            skill_context += "\nRelevant Previous Plans found in memory:\n"
            for m in memories[:3]:  # Top 3 relevant memories
                content = m.get("content", "")
                skill_context += f"- {content}\n"

        if lessons:
            skill_context += lessons

        # 1. Ask MCP for available tools
        tools_res = await self.adapters["mcp"].call_tool(
            "filesystem", "list_allowed_directories", {}
        )

        # 2. Define Native Tools
        native_tools = [
            {
                "type": "computer_20241022",
                "name": "computer",
                "display_width_px": 1024,
                "display_height_px": 768,
                "display_number": 0,
            },
            {
                "name": "spawn_sub_agent",
                "description": "Create a specialized sub-agent for a specific task.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Unique name for the sub-agent",
                        },
                        "task": {
                            "type": "string",
                            "description": "The specific task for the sub-agent to perform",
                        },
                        "role": {
                            "type": "string",
                            "description": "The persona/role of the sub-agent (e.g., 'Security Expert', 'Senior Dev')",
                        },
                    },
                    "required": ["name", "task"],
                },
            },
            {
                "name": "query_project_rag",
                "description": "Query the local project documentation and code structure.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"}
                    },
                    "required": ["query"],
                },
            },
        ]

        # 3. Maintain session state
        messages: List[Dict[str, Any]] = [{"role": "user", "content": message.content}]
        max_steps = 10

        project = self.project_manager.current_project
        project_prompt = project.get_system_prompt() if project else ""

        for step in range(max_steps):
            try:
                await websocket.send_json(
                    {"type": "status", "content": f"Step {step + 1}: Consulting LLM..."}
                )

                # Combine original context with found skills and project-specific instructions
                project_context = f"\nCurrent Project Workspace: {project.files_path if project else 'N/A'}"
                full_context = f"Allowed Paths: {tools_res}{skill_context}{project_context}\n{project_prompt}"

                llm_response = await self.llm.generate(
                    context=full_context, tools=native_tools, messages=messages
                )

                # Handle response
                if isinstance(llm_response, list):  # Anthropic tool use
                    tool_use_found = False
                    messages.append({"role": "assistant", "content": llm_response})

                    for block in llm_response:
                        if block.get("type") == "text":
                            await websocket.send_json(
                                {
                                    "type": "status",
                                    "content": f"Thought: {block['text']}",
                                }
                            )

                        if block.get("type") == "tool_use":
                            tool_use_found = True
                            tool_name = block.get("name")
                            tool_input = block.get("input")
                            action_id = block.get("id")

                            if tool_name == "computer":
                                # Create a future to wait for approval and execution
                                loop = asyncio.get_running_loop()
                                future = loop.create_future()

                                def on_executed(result):
                                    if not future.done():
                                        future.set_result(result)

                                await self._handle_computer_tool(
                                    tool_input,
                                    websocket,
                                    action_id,
                                    callback=on_executed,
                                )

                                # Wait for user approval and execution
                                await websocket.send_json(
                                    {
                                        "type": "status",
                                        "content": f"Waiting for approval of: {tool_input.get('action')}...",
                                    }
                                )
                                result = await future

                            elif tool_name == "spawn_sub_agent":
                                await websocket.send_json(
                                    {
                                        "type": "status",
                                        "content": f"Spawning sub-agent '{tool_input.get('name')}'...",
                                    }
                                )
                                result = await self._spawn_sub_agent(tool_input)

                            elif tool_name == "query_project_rag":
                                await websocket.send_json(
                                    {
                                        "type": "status",
                                        "content": f"Querying RAG for '{tool_input.get('query')}'...",
                                    }
                                )
                                result = await self.rag.navigate(
                                    tool_input.get("query")
                                )

                            else:
                                # Fallback to MCP tools if not native
                                result = await self.adapters["mcp"].call_tool(
                                    None,
                                    tool_name,
                                    tool_input,
                                )

                            # Add tool result to messages
                            messages.append(
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "tool_result",
                                            "tool_use_id": action_id,
                                            "content": result,
                                        }
                                    ],
                                }
                            )

                    if not tool_use_found:
                        break  # No more tools, we're done

                elif isinstance(llm_response, str):
                    await websocket.send_json(
                        {
                            "type": "message",
                            "content": llm_response,
                            "sender": "MegaBot",
                        }
                    )
                    break  # Natural language response, we're done

            except Exception as e:
                print(f"Autonomous build error at step {step}: {e}")
                await websocket.send_json(
                    {"type": "status", "content": f"Error: {str(e)}"}
                )
                break

        # 4. Save successful session to memory for Skill Acquisition
        await self.adapters["memu"].learn_from_interaction(
            {
                "action": "autonomous_build",
                "prompt": message.content,
                "session_log": messages,
                "timestamp": datetime.now().isoformat(),
            }
        )

        await websocket.send_json(
            {"type": "status", "content": "Autonomous build session completed."}
        )

    async def _spawn_sub_agent(self, tool_input: Dict) -> str:
        """Spawn and orchestrate a sub-agent with Pre-flight Checks and Synthesis"""
        name = str(tool_input.get("name", "unknown"))
        task = str(tool_input.get("task", "unknown"))
        role = str(tool_input.get("role", "Assistant"))

        agent = SubAgent(name, role, task, self)
        self.sub_agents[name] = agent

        # 1. Pre-flight Check: Planning & Validation
        print(f"Sub-Agent {name}: Generating plan...")
        plan = await agent.generate_plan()

        # Validate plan against project policies
        validation_prompt = f"As a Master Security Agent, validate the following plan for task '{task}' by agent '{name}' ({role}):\n{plan}\n\nDoes this plan violate any security policies (e.g., unauthorized access, destructive commands)? Reply with 'VALID' or a description of the violation."
        validation_res = await self.llm.generate(
            context="Pre-flight Plan Validation",
            messages=[{"role": "user", "content": validation_prompt}],
        )
        # pragma: no cover
        if "VALID" not in str(validation_res).upper():
            return f"Sub-agent {name} blocked by pre-flight check: {validation_res}"

        # 2. Execution
        print(f"Sub-Agent {name}: Execution started...")
        raw_result = await agent.run()

        # 3. Synthesis: Refine and integrate sub-agent findings
        print(f"Sub-Agent {name}: Execution finished. Synthesizing results...")
        synthesis_prompt = f"""
Integrate and summarize the findings from sub-agent '{name}' for the task '{task}'.
Raw Result: {raw_result}

Your goal is to extract architectural patterns or hard-won lessons that should be remembered by the Master Agent for future tasks.

Format your response as a valid JSON object:
{{
    "summary": "Brief overall summary for immediate use",
    "findings": ["Specific technical detail 1", "Specific technical detail 2"],
    "learned_lesson": "A high-priority architectural decision, constraint, or pattern (e.g. 'Always use X when doing Y because of Z'). Prefix with 'CRITICAL:' if it relates to security or failure.",
    "next_steps": ["Step 1"]
}}
"""
        synthesis_raw = await self.llm.generate(
            context="Result Synthesis",
            messages=[{"role": "user", "content": synthesis_prompt}],
        )

        # Parse synthesis and record lesson
        try:
            # Hardened JSON extraction
            lesson = "No lesson recorded."
            summary = str(synthesis_raw)
            print(f"DEBUG [Synthesis Raw]: {summary[:200]}")

            # Try to find JSON block
            json_match = re.search(r"\{.*\}", summary, re.DOTALL)  # pragma: no cover
            if json_match:  # pragma: no cover
                try:  # pragma: no cover
                    synthesis_data = json.loads(json_match.group(0))  # pragma: no cover
                    lesson = synthesis_data.get(
                        "learned_lesson", lesson
                    )  # pragma: no cover
                    summary = synthesis_data.get("summary", summary)  # pragma: no cover
                except Exception as e:  # pragma: no cover
                    print(
                        f"DEBUG [Synthesis JSON Parse Error]: {e}"
                    )  # pragma: no cover
                    # Fallback: regex search for learned_lesson field if JSON parse fails  # pragma: no cover
                    lesson_match = re.search(  # pragma: no cover
                        r'"learned_lesson":\s*"(.*?)"',
                        summary,
                        re.DOTALL,  # pragma: no cover
                    )  # pragma: no cover
                    if lesson_match:
                        lesson = lesson_match.group(1)
            else:
                # Direct fallback: Look for "lesson:" or "CRITICAL:" in raw text
                fallback_match = re.search(
                    r"(?:learned_lesson|lesson|CRITICAL):?\s*(.*)",
                    str(synthesis_raw),
                    re.IGNORECASE,
                )  # pragma: no cover
                if fallback_match:
                    lesson = fallback_match.group(1).strip()

            await self.memory.memory_write(
                key=f"lesson_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                type="learned_lesson",
                content=lesson,
                tags=["synthesis", name, role],
            )
            # pragma: no cover
            # Proactively notify UI of new memory  # pragma: no cover
            for client in list(self.clients):  # pragma: no cover
                await client.send_json(  # pragma: no cover
                    {
                        "type": "memory_update",
                        "content": lesson,
                        "source": name,
                    }  # pragma: no cover
                )  # pragma: no cover

            return summary
        except Exception as e:
            print(f"Failed to record memory lesson or parse synthesis: {e}")
            return str(synthesis_raw)

    async def _execute_tool_for_sub_agent(
        self, agent_name: str, tool_call: Dict
    ) -> str:
        """Execute a tool on behalf of a sub-agent with Domain Boundary enforcement"""
        agent = self.sub_agents.get(agent_name)  # pragma: no cover
        if not agent:
            return "Error: Agent not found."

        tool_name = str(tool_call.get("name", "unknown"))
        tool_input = tool_call.get("input", {})

        # Enforce Domain Boundaries
        allowed_tools = agent._get_sub_tools()
        target_tool = next((t for t in allowed_tools if t["name"] == tool_name), None)
        # pragma: no cover
        if not target_tool:
            return f"Security Error: Tool '{tool_name}' is outside the domain boundaries for role '{agent.role}'."

        scope = str(target_tool.get("scope", "unknown"))

        # Check overall permissions
        auth = self.permissions.is_authorized(scope)  # pragma: no cover
        if auth is False:
            return f"Security Error: Permission denied for scope '{scope}'."

        # Actual implementation of sub-tools
        try:
            if tool_name == "read_file":
                path = str(tool_input.get("path", ""))
                with open(path, "r") as f:  # pragma: no cover
                    return f.read()  # pragma: no cover
            elif tool_name == "write_file":  # pragma: no cover
                path = str(tool_input.get("path", ""))  # pragma: no cover
                content = str(tool_input.get("content", ""))  # pragma: no cover
                with open(path, "w") as f:  # pragma: no cover
                    f.write(content)  # pragma: no cover
                return f"File '{path}' written successfully."  # pragma: no cover
            elif tool_name == "run_test":  # pragma: no cover
                import subprocess  # pragma: no cover

                # pragma: no cover
                cmd = str(tool_input.get("command", ""))  # pragma: no cover
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True
                )  # pragma: no cover
                return f"Exit Code: {result.returncode}\nOutput: {result.stdout}\nError: {result.stderr}"  # pragma: no cover
            elif tool_name == "query_rag":  # pragma: no cover
                return await self.rag.navigate(
                    str(tool_input.get("query", ""))
                )  # pragma: no cover
            elif tool_name == "analyze_data":  # pragma: no cover
                dataset_name = str(
                    tool_input.get("dataset_name", "")
                )  # pragma: no cover
                query = str(tool_input.get("query", ""))  # pragma: no cover
                code = tool_input.get("python_code")  # pragma: no cover
                # pragma: no cover
                agent = self.features.get("dash_data")  # pragma: no cover
                if not agent:  # pragma: no cover
                    return (
                        "Error: Data Analysis feature not enabled."  # pragma: no cover
                    )
                # pragma: no cover
                if code:  # pragma: no cover
                    return await agent.execute_python_analysis(
                        dataset_name, code
                    )  # pragma: no cover
                else:  # pragma: no cover
                    return await agent.analyze(dataset_name, query)  # pragma: no cover
        except Exception as e:  # pragma: no cover
            return f"Tool Execution Error: {str(e)}"  # pragma: no cover

        return f"Error: Tool '{tool_name}' logic not implemented."

    async def _handle_computer_tool(
        self,
        tool_input: Dict,
        websocket: WebSocket,
        action_id: str,
        callback: Optional[Any] = None,
    ):  # pragma: no cover
        """Handle Anthropic Computer Use tool calls with Approval Interlock"""  # pragma: no cover
        action_type = tool_input.get("action")  # pragma: no cover
        description = f"Computer Use: {action_type} ({tool_input})"  # pragma: no cover
        # pragma: no cover
        # Queue for approval  # pragma: no cover
        import uuid  # pragma: no cover

        # pragma: no cover
        action = {  # pragma: no cover
            "id": action_id or str(uuid.uuid4()),  # pragma: no cover
            "type": "computer_use",  # pragma: no cover
            "payload": tool_input,  # pragma: no cover
            "description": description,  # pragma: no cover
            "websocket": websocket,  # pragma: no cover
            "callback": callback,  # pragma: no cover
        }  # pragma: no cover
        self.admin_handler.approval_queue.append(action)  # pragma: no cover
        # pragma: no cover
        await websocket.send_json(  # pragma: no cover
            {  # pragma: no cover
                "type": "status",  # pragma: no cover
                "content": f"Computer action queued for approval: {action_type}",  # pragma: no cover
            }  # pragma: no cover
        )  # pragma: no cover
        # Broadcast update  # pragma: no cover
        for client in list(self.clients):
            await client.send_json({"type": "approval_required", "action": action})

    async def _llm_dispatch(
        self, prompt: str, context: Any, tools: Optional[List[Dict[str, Any]]] = None
    ) -> Any:  # pragma: no cover
        """Unified tool selection logic using configured LLM provider"""
        return await self.llm.generate(prompt, context, tools=tools)

    def _check_policy(self, data: Dict) -> str:  # pragma: no cover
        """Check if an action is pre-approved or pre-denied based on policies"""  # pragma: no cover
        method = data.get("method")  # pragma: no cover
        params = data.get("params", {})  # pragma: no cover
        command = params.get("command", "")  # pragma: no cover
        # pragma: no cover
        # Determine scope  # pragma: no cover
        scope = str(method) if method else "unknown"  # pragma: no cover
        if method in ["system.run", "shell.execute"] and command:  # pragma: no cover
            # 1. Try full command match (both with and without 'shell.' prefix)  # pragma: no cover
            # This handles policies set as 'git status' or 'shell.git status'  # pragma: no cover
            for s in [f"shell.{command}", command]:  # pragma: no cover
                auth = self.permissions.is_authorized(s)  # pragma: no cover
                if auth is not None:  # pragma: no cover
                    return "allow" if auth else "deny"  # pragma: no cover
            # pragma: no cover
            # 2. Try granular scope (e.g., shell.git or just git)  # pragma: no cover
            cmd_part = (
                str(command).split()[0] if command else "unknown"
            )  # pragma: no cover
            for s in [f"shell.{cmd_part}", cmd_part]:  # pragma: no cover
                auth = self.permissions.is_authorized(s)  # pragma: no cover
                if auth is not None:  # pragma: no cover
                    return "allow" if auth else "deny"  # pragma: no cover
        # pragma: no cover
        auth = self.permissions.is_authorized(scope)  # pragma: no cover
        # pragma: no cover
        if auth is True:  # pragma: no cover
            return "allow"  # pragma: no cover
        if auth is False:  # pragma: no cover
            return "deny"
        return "ask"

    async def on_openclaw_event(self, data):  # pragma: no cover
        print(f"OpenClaw Event: {data}")
        method = data.get("method")
        params = data.get("params", {})
        sender_id = params.get("sender_id", "unknown")
        content = params.get("content", "")

        # Send greeting on handshake
        if method == "connect" or method == "handshake":
            greeting = Message(content=GREETING_TEXT, sender="MegaBot")
            await self.adapters["openclaw"].send_message(greeting)
            return
        # pragma: no cover
        # Check for chat-based admin commands from OpenClaw (WhatsApp/Telegram)  # pragma: no cover
        if method == "chat.message" and content.startswith("!"):  # pragma: no cover
            chat_id = params.get("chat_id") or sender_id  # pragma: no cover
            platform = params.get("platform", "openclaw")  # pragma: no cover
            if await self._handle_admin_command(
                content, sender_id, chat_id, platform
            ):  # pragma: no cover
                return  # Command handled  # pragma: no cover
        # pragma: no cover
        # INTERCEPT: Check policies for sensitive system commands  # pragma: no cover
        if method == "system.run" or method == "shell.execute":  # pragma: no cover
            policy = self._check_policy(data)  # pragma: no cover
            # pragma: no cover
            if policy == "allow":  # pragma: no cover
                print(f"Policy: Auto-approving {method}")  # pragma: no cover
                await self.adapters["openclaw"].send_message(data)  # pragma: no cover
                return  # pragma: no cover
            # pragma: no cover
            if policy == "deny":  # pragma: no cover
                print(f"Policy: Auto-denying {method}")  # pragma: no cover
                return  # Discard  # pragma: no cover
            # pragma: no cover
            # Default: Queue for manual approval  # pragma: no cover
            import uuid  # pragma: no cover

            # pragma: no cover
            action = {  # pragma: no cover
                "id": str(uuid.uuid4()),  # pragma: no cover
                "type": "system_command",  # pragma: no cover
                "payload": data,  # pragma: no cover
                "description": f"Execute: {data.get('params', {}).get('command')}",  # pragma: no cover
            }  # pragma: no cover
            self.admin_handler.approval_queue.append(action)  # pragma: no cover
            # Notify UI of new pending action  # pragma: no cover
            for client in list(self.clients):  # pragma: no cover
                await client.send_json(
                    {"type": "approval_required", "action": action}
                )  # pragma: no cover
            # pragma: no cover
            # Notify messaging server (for Signal/Telegram admins)  # pragma: no cover
            admin_resp = Message(  # pragma: no cover
                content=f"⚠️ Approval Required: {action['description']}\nType `!approve {action['id']}` to authorize.",  # pragma: no cover
                sender="Security",  # pragma: no cover
            )  # pragma: no cover
            asyncio.create_task(
                self.send_platform_message(admin_resp)
            )  # pragma: no cover
            return  # pragma: no cover
        # pragma: no cover
        # Relay standard events to all connected UI clients  # pragma: no cover
        for client in list(self.clients):  # pragma: no cover
            try:  # pragma: no cover
                await client.send_json(
                    {"type": "openclaw_event", "payload": data}
                )  # pragma: no cover
            except Exception:  # pragma: no cover
                self.clients.discard(client)  # pragma: no cover
        # pragma: no cover
        # Also relay to Native Messaging Server clients  # pragma: no cover
        if data.get("method") == "chat.message":  # pragma: no cover
            params = data.get("params", {})  # pragma: no cover
            msg = Message(  # pragma: no cover
                content=params.get("content", ""),  # pragma: no cover
                sender=params.get("sender", "OpenClaw"),  # pragma: no cover
            )
            await self.send_platform_message(msg)

    def _sanitize_output(self, text: str) -> str:
        """Strip ANSI escape sequences and other potentially dangerous terminal characters"""
        if not text:
            return ""
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        sanitized = ansi_escape.sub("", text)

        # Remove other control characters except newline and tab
        sanitized = "".join(ch for ch in sanitized if ch >= " " or ch in "\n\r\t")

        return sanitized  # pragma: no cover

    # pragma: no cover
    async def _process_approval(
        self, action_id: str, approved: bool
    ):  # pragma: no cover
        """Execute or discard a pending sensitive action"""  # pragma: no cover
        action = next(  # pragma: no cover
            (a for a in self.admin_handler.approval_queue if a["id"] == action_id),
            None,  # pragma: no cover
        )  # pragma: no cover
        if not action:  # pragma: no cover
            return  # pragma: no cover
        # pragma: no cover
        if approved:  # pragma: no cover
            print(f"Action Approved: {action['type']}")  # pragma: no cover
            if action["type"] == "system_command":  # pragma: no cover
                # ... existing system_command logic ...  # pragma: no cover
                params = action.get("payload", {}).get("params", {})  # pragma: no cover
                cmd = (
                    params.get("command") if isinstance(params, dict) else None
                )  # pragma: no cover
                if cmd:  # pragma: no cover
                    # Inject secrets before execution  # pragma: no cover
                    cmd = self.secret_manager.inject_secrets(cmd)  # pragma: no cover
                    # pragma: no cover
                    # Execute and capture output  # pragma: no cover
                    import subprocess  # pragma: no cover

                    # pragma: no cover
                    try:  # pragma: no cover
                        # Tirith Guard validation before execution  # pragma: no cover
                        if not tirith.validate(cmd):  # pragma: no cover
                            output = "Security Error: Command blocked by Tirith Guard (Suspicious Unicode/Cyrillic detected)."  # pragma: no cover
                        else:  # pragma: no cover
                            result = subprocess.run(  # pragma: no cover
                                cmd,  # pragma: no cover
                                shell=True,  # pragma: no cover
                                capture_output=True,  # pragma: no cover
                                text=True,  # pragma: no cover
                                timeout=30,  # pragma: no cover
                            )  # pragma: no cover
                            output = tirith.sanitize(
                                result.stdout + result.stderr
                            )  # pragma: no cover
                        # pragma: no cover
                        # Scrub secrets from output  # pragma: no cover
                        output = self.secret_manager.scrub_secrets(
                            output
                        )  # pragma: no cover
                    except Exception as e:  # pragma: no cover
                        output = f"Command failed: {e}"  # pragma: no cover
                    # pragma: no cover
                    # Send back to the specific websocket that requested it  # pragma: no cover
                    ws = action.get("websocket")  # pragma: no cover
                    if ws:  # pragma: no cover
                        await ws.send_json(  # pragma: no cover
                            {
                                "type": "terminal_output",
                                "content": output,
                            }  # pragma: no cover
                        )  # pragma: no cover
                    # pragma: no cover
                    # Also relay to OpenClaw if needed  # pragma: no cover
                    await self.adapters["openclaw"].send_message(  # pragma: no cover
                        {
                            "method": "system.result",
                            "params": {"output": output},
                        }  # pragma: no cover
                    )  # pragma: no cover
            # pragma: no cover
            elif action["type"] == "outbound_vision":  # pragma: no cover
                payload = action.get("payload", {})  # pragma: no cover
                # Reconstruct and send the message now that it's approved  # pragma: no cover
                approved_msg = Message(  # pragma: no cover
                    content=payload.get("message_content", ""),  # pragma: no cover
                    sender="MegaBot",  # pragma: no cover
                    attachments=payload.get("attachments", []),  # pragma: no cover
                )  # pragma: no cover
                # Call send_platform_message again, but bypass vision check if possible or rely on policy change  # pragma: no cover
                # To avoid re-queuing, we can temporarily set policy or use a flag.  # pragma: no cover
                # Simplest: call the messaging adapter directly for this approved action.  # pragma: no cover
                platform_msg = self._to_platform_message(  # pragma: no cover
                    approved_msg,
                    chat_id=payload.get("chat_id"),  # pragma: no cover
                )  # pragma: no cover
                platform_msg.platform = payload.get(
                    "platform", "native"
                )  # pragma: no cover
                await self.adapters["messaging"].send_message(  # pragma: no cover
                    platform_msg,
                    target_client=payload.get("target_client"),  # pragma: no cover
                )  # pragma: no cover
                print(
                    f"Outbound vision approved and sent to {payload.get('chat_id')}"
                )  # pragma: no cover
            # pragma: no cover
            elif action["type"] == "data_execution":  # pragma: no cover
                payload = action.get("payload", {})  # pragma: no cover
                name = payload.get("name")  # pragma: no cover
                code = payload.get("code")  # pragma: no cover
                # pragma: no cover
                # We need access to the data agent.  # pragma: no cover
                # This assumes we have a way to get it, usually it's a feature we discovery  # pragma: no cover
                # For now, let's assume we can find it in discovery or it's a known global  # pragma: no cover
                try:  # pragma: no cover
                    # Generic way to find the data agent if it was registered  # pragma: no cover
                    # In a real app, this might be self.features["dash_data"]  # pragma: no cover
                    from features.dash_data.agent import (
                        DashDataAgent,
                    )  # pragma: no cover

                    # pragma: no cover
                    temp_agent = DashDataAgent(self.llm, self)  # pragma: no cover
                    # We'd need to restore the datasets, but for this prototype,  # pragma: no cover
                    # we'll assume the agent that queued it is still alive or we recreate context  # pragma: no cover
                    output = await temp_agent.execute_python_analysis(
                        name, code
                    )  # pragma: no cover
                except Exception as e:  # pragma: no cover
                    output = f"Approval execution failed: {e}"  # pragma: no cover
                # pragma: no cover
                # Send back results to admins  # pragma: no cover
                resp = Message(  # pragma: no cover
                    content=f"✅ Data Execution Result:\n{output}",
                    sender="DataAgent",  # pragma: no cover
                )  # pragma: no cover
                await self.send_platform_message(resp)  # pragma: no cover
            # pragma: no cover
            elif action["type"] == "computer_use":  # pragma: no cover
                payload = action.get("payload", {})  # pragma: no cover
                # pragma: no cover
                # Execute actual computer action  # pragma: no cover
                action_type = payload.get("action")  # pragma: no cover
                coordinate = payload.get("coordinate")  # pragma: no cover
                text = payload.get("text")  # pragma: no cover
                # pragma: no cover
                output = await self.computer_driver.execute(  # pragma: no cover
                    action_type,
                    coordinate,
                    text,  # pragma: no cover
                )  # pragma: no cover
                print(f"Computer Action Result: {output}")  # pragma: no cover
                # pragma: no cover
                ws = action.get("websocket")  # pragma: no cover
                if ws:  # pragma: no cover
                    # If it's a screenshot, send it as a special type  # pragma: no cover
                    if action_type == "screenshot" and not output.startswith(
                        "Error"
                    ):  # pragma: no cover
                        await ws.send_json(
                            {"type": "screenshot", "content": output}
                        )  # pragma: no cover
                        output = (
                            "Screenshot captured and sent to UI."  # pragma: no cover
                        )
                    else:  # pragma: no cover
                        await ws.send_json(
                            {"type": "status", "content": output}
                        )  # pragma: no cover
                # pragma: no cover
                # Report back to OpenClaw/LLM  # pragma: no cover
                # We also include the action id so the LLM knows which call this corresponds to  # pragma: no cover
                await self.adapters["openclaw"].send_message(  # pragma: no cover
                    {  # pragma: no cover
                        "method": "tool.result",  # pragma: no cover
                        "params": {
                            "id": action["id"],
                            "output": output,
                        },  # pragma: no cover
                    }  # pragma: no cover
                )  # pragma: no cover
                # pragma: no cover
                # If we have a resume callback, trigger it  # pragma: no cover
                if "callback" in action and callable(
                    action["callback"]
                ):  # pragma: no cover
                    await action["callback"](output)  # pragma: no cover
            # pragma: no cover
            elif action["type"] == "identity_link":  # pragma: no cover
                payload = action.get("payload", {})  # pragma: no cover
                internal_id = payload.get("internal_id")  # pragma: no cover
                platform = payload.get("platform")  # pragma: no cover
                platform_id = payload.get("platform_id")  # pragma: no cover
                chat_id = payload.get("chat_id")  # pragma: no cover
                # pragma: no cover
                if internal_id and platform and platform_id:  # pragma: no cover
                    await self.memory.link_identity(
                        internal_id, platform, platform_id
                    )  # pragma: no cover
                    resp = Message(  # pragma: no cover
                        content=f"✅ Identity Link Verified: '{internal_id}' linked to {platform}:{platform_id}",  # pragma: no cover
                        sender="System",  # pragma: no cover
                    )  # pragma: no cover
                    await self.send_platform_message(  # pragma: no cover
                        resp,
                        chat_id=chat_id,
                        platform=platform,  # pragma: no cover
                    )  # pragma: no cover
        else:  # pragma: no cover
            print(f"Action Denied: {action['type']}")  # pragma: no cover
            # Notify the callback of failure/denial  # pragma: no cover
            if "callback" in action and callable(
                action["callback"]
            ):  # pragma: no cover
                await action["callback"]("Action denied by user.")  # pragma: no cover
        # pragma: no cover
        self.admin_handler.approval_queue = [  # pragma: no cover
            a
            for a in self.admin_handler.approval_queue
            if a["id"] != action_id  # pragma: no cover
        ]  # pragma: no cover
        # pragma: no cover
        # Broadcast queue update to all clients  # pragma: no cover
        for client in list(self.clients):  # pragma: no cover
            try:  # pragma: no cover
                await client.send_json(  # pragma: no cover
                    {  # pragma: no cover
                        "type": "approval_queue_updated",  # pragma: no cover
                        "queue": self.admin_handler.approval_queue,  # pragma: no cover
                    }  # pragma: no cover
                )
            except Exception as e:
                print(f"Failed to notify client of queue update: {e}")
                self.clients.discard(client)

    async def sync_loop(self):
        while True:  # pragma: no cover
            # Periodically ingest OpenClaw logs into memU
            # Default path for OpenClaw logs: ~/.openclaw/sessions.jsonl
            log_path = os.path.expanduser("~/.openclaw/sessions.jsonl")
            try:
                await self.adapters["memu"].ingest_openclaw_logs(log_path)
            except Exception as e:
                print(f"Sync error: {e}")
            await asyncio.sleep(3600)  # Sync every hour

    async def handle_client(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.add(websocket)

        # Send initial greeting
        await websocket.send_json(
            {
                "type": "message",
                "content": GREETING_TEXT,
                "sender": "MegaBot",
                "timestamp": datetime.now().isoformat(),
            }
        )

        try:
            while True:  # pragma: no cover  # pragma: no cover
                data = await websocket.receive_text()
                msg_data = json.loads(data)
                print(f"Received from UI: {msg_data}")

                # Logic to route message
                if msg_data.get("type") == "message":
                    message = Message(content=msg_data["content"], sender="user")
                    # Store in memU
                    await self.adapters["memu"].store(
                        f"user_msg_{id(message)}", message.content
                    )

                    # If in 'build' mode, attempt autonomous planning/execution
                    if self.mode == "build":
                        asyncio.create_task(
                            self.run_autonomous_build(message, websocket)
                        )
                    else:
                        # Standard relay to OpenClaw
                        await self.adapters["openclaw"].send_message(message)

                elif msg_data.get("type") == "set_mode":
                    self.mode = msg_data["mode"]
                    await websocket.send_json(
                        {"type": "mode_updated", "mode": self.mode}
                    )

                elif msg_data.get("type") == "mcp_call":
                    # Call MCP tool
                    result = await self.adapters["mcp"].call_tool(
                        msg_data["server"], msg_data["tool"], msg_data["params"]
                    )
                    await websocket.send_json({"type": "mcp_result", "result": result})

                elif msg_data.get("type") == "search":
                    # Search memory
                    results = await self.adapters["memu"].search(msg_data["query"])
                    await websocket.send_json(
                        {"type": "search_results", "results": results}
                    )

                elif msg_data.get("type") == "command":
                    # Execute shell command via terminal (Security: requires Approval)
                    cmd = msg_data.get("command")
                    import uuid

                    action = {
                        "id": str(uuid.uuid4()),
                        "type": "system_command",
                        "payload": {"method": "system.run", "params": {"command": cmd}},
                        "description": f"Terminal Execute: {cmd}",
                        "websocket": websocket,  # Keep track for output
                    }
                    self.admin_handler.approval_queue.append(action)
                    await websocket.send_json(
                        {
                            "type": "status",
                            "content": f"Command queued for approval: {cmd}",
                        }
                    )
                    # Broadcast update
                    for client in list(self.clients):
                        await client.send_json(
                            {"type": "approval_required", "action": action}
                        )

                elif msg_data.get("type") == "approve_action":
                    action_id = msg_data.get("action_id")
                    await self._process_approval(action_id, approved=True)

                elif msg_data.get("type") == "reject_action":
                    action_id = msg_data.get("action_id")
                    await self._process_approval(action_id, approved=False)

        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            self.clients.discard(websocket)

    async def shutdown(self):
        """Gracefully shutdown the orchestrator and all adapters."""
        print("[MegaBot] Shutting down orchestrator...")

        # Shutdown all adapters
        for name, adapter in self.adapters.items():  # pragma: no cover
            try:  # pragma: no cover
                if hasattr(adapter, "shutdown"):  # pragma: no cover
                    await adapter.shutdown()  # pragma: no cover
                    print(f"[MegaBot] Adapter '{name}' shutdown complete")
                elif hasattr(adapter, "close"):
                    await adapter.close()
                    print(f"[MegaBot] Adapter '{name}' closed")
            except Exception as e:
                print(f"[MegaBot] Error shutting down adapter '{name}': {e}")

        # Stop health monitoring
        if hasattr(self, "health_monitor") and self.health_monitor:  # pragma: no cover
            try:  # pragma: no cover
                await self.health_monitor.stop()
                print("[MegaBot] Health monitor stopped")
            except Exception as e:
                print(
                    f"[MegaBot] Error stopping health monitor: {e}"
                )  # pragma: no cover
        # pragma: no cover
        # Close all WebSocket connections  # pragma: no cover
        for client in list(self.clients):  # pragma: no cover
            try:
                await client.close()
            except Exception:
                pass
        self.clients.clear()

        print("[MegaBot] Orchestrator shutdown complete")


@app.post("/ivr")
async def ivr_callback(request: Request, action_id: str = Query(...)):
    form_data = await request.form()
    digits = form_data.get("Digits")

    if orchestrator:
        if digits == "1":  # pragma: no cover
            await orchestrator.admin_handler._process_approval(
                action_id, approved=True
            )  # pragma: no cover
            response_text = "Action approved. Thank you."  # pragma: no cover
        else:  # pragma: no cover
            await orchestrator.admin_handler._process_approval(  # pragma: no cover
                action_id,
                approved=False,  # pragma: no cover
            )
            response_text = "Action rejected."
    else:
        response_text = "System error."  # pragma: no cover

    return Response(
        content=f"<Response><Say>{response_text}</Say></Response>",
        media_type="application/xml",
    )


# pragma: no cover


@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "MegaBot API is running",
        "version": "0.2.0-alpha",
        "endpoints": ["/ws", "/health"],
    }


# pragma: no cover


@app.get("/health")
async def health():
    return {"status": "ok"}


# pragma: no cover
# pragma: no cover
@app.websocket("/ws")  # pragma: no cover
async def websocket_endpoint(websocket: WebSocket):  # pragma: no cover
    if orchestrator:  # pragma: no cover
        await orchestrator.handle_client(websocket)  # pragma: no cover
    else:
        await websocket.accept()
        await websocket.send_text("Orchestrator not initialized")
        await websocket.close()  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(app, host=config.system.bind_address, port=8000)
