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
if os.path.exists(cred_path):
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
    if not orchestrator:
        orchestrator = MegaBotOrchestrator(config)
        await orchestrator.start()

    yield

    # Shutdown (if needed)
    pass


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

    async def on_messaging_connect(self, client_id: Optional[str], platform: str):
        """Handle new messaging platform connections.

        Sends a welcome message to newly connected clients explaining
        MegaBot's capabilities and available commands.

        Args:
            client_id: Unique identifier for the connected client (optional)
            platform: Platform name (telegram, signal, websocket, etc.)
        """
        print(f"Greeting new connection: {platform} ({client_id or 'all'})")
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
        # Check if sender is an admin
        if self.config.admins and sender_id not in self.config.admins:
            return False

        parts = text.strip().split()
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
                print(f"System Mode updated to: {self.mode}")
                if self.mode == "loki":
                    asyncio.create_task(self.loki.activate("Auto-trigger from chat"))
                return True

        elif cmd == "!history_clean":
            target_chat = parts[1] if len(parts) > 1 else chat_id
            if target_chat:
                await self.memory.chat_forget(target_chat, max_history=0)
                resp = Message(
                    content=f"🗑️ History cleaned for chat: {target_chat}",
                    sender="System",
                )
                asyncio.create_task(self.send_platform_message(resp, chat_id=chat_id))
                return True

        elif cmd == "!link":
            if len(parts) > 1:
                target_name = parts[1]
                # Re-fetch the raw platform ID from metadata if possible,
                # but since we already resolved chat_id, we need to know the original.
                # In on_gateway_message, we resolved it.
                # Let's assume for this command we want to link the sender_id.
                await self.memory.link_identity(target_name, platform, sender_id)
                resp = Message(
                    content=f"🔗 Identity Linked: {platform}:{sender_id} is now known as '{target_name}'",
                    sender="System",
                )
                asyncio.create_task(
                    self.send_platform_message(resp, chat_id=chat_id, platform=platform)
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

        elif cmd == "!briefing":
            # Trigger a voice briefing call
            admin_phone = getattr(self.config.system, "admin_phone", None)
            if not admin_phone or not self.adapters["messaging"].voice_adapter:
                resp = Message(
                    content="❌ Briefing failed: No admin phone or voice adapter configured.",
                    sender="System",
                )
                asyncio.create_task(
                    self.send_platform_message(resp, chat_id=chat_id, platform=platform)
                )
                return True

            asyncio.create_task(
                self._trigger_voice_briefing(admin_phone, str(chat_id), platform)
            )
            resp = Message(
                content="📞 Voice briefing initiated. Expect a call shortly.",
                sender="System",
            )
            asyncio.create_task(
                self.send_platform_message(resp, chat_id=chat_id, platform=platform)
            )
            return True

        elif cmd == "!rag_rebuild":
            await self.rag.build_index(force_rebuild=True)
            resp = Message(
                content="🏗️ RAG Index rebuilt and cached.",
                sender="System",
            )
            asyncio.create_task(
                self.send_platform_message(resp, chat_id=chat_id, platform=platform)
            )
            return True

        elif cmd == "!health":
            health = await self.get_system_health()
            health_text = "🩺 **System Health:**\n"
            for comp, data in health.items():
                status_emoji = "✅" if data["status"] == "up" else "❌"
                health_text += (
                    f"- {status_emoji} **{comp.capitalize()}**: {data['status']}\n"
                )
                if "error" in data:
                    health_text += f"  - Error: {data['error']}\n"

            resp = Message(
                content=health_text,
                sender="System",
            )
            asyncio.create_task(
                self.send_platform_message(resp, chat_id=chat_id, platform=platform)
            )
            return True

        return False

    async def on_gateway_message(self, data: Dict):
        """Process messages received through the unified gateway.

        Routes messages from Cloudflare Tunnel, Tailscale VPN, or direct HTTPS
        connections through the same processing pipeline as native messaging.

        Args:
            data: Message payload from gateway containing platform, content, etc.
        """
        await self.message_handler.process_gateway_message(data)

    async def run_autonomous_gateway_build(self, message: Message, original_data: Dict):
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
            )
            print("Connected to OpenClaw Gateway.")
        except Exception as e:
            print(f"Failed to connect to OpenClaw: {e}")

        try:
            await self.adapters["mcp"].start_all()
            print("MCP Servers started.")
        except Exception as e:
            print(f"Failed to start MCP Servers: {e}")

        # Initialize Project RAG
        try:
            await self.rag.build_index()
            print(f"Project RAG index built for: {self.rag.root_dir}")
        except Exception as e:
            print(f"Failed to build RAG index: {e}")

        # Start background tasks
        await self.background_tasks.start_all_tasks()

    async def restart_component(self, name: str):
        """Attempt to re-initialize or reconnect a specific system component"""
        print(f"Self-Healing: Restarting {name}...")
        try:
            if name == "openclaw":
                await self.adapters["openclaw"].connect(on_event=self.on_openclaw_event)
                await self.adapters["openclaw"].subscribe_events(
                    ["chat.message", "tool.call"]
                )
            elif name == "messaging":
                # Messaging server runs in background task, usually restart involves re-binding if crashed
                asyncio.create_task(self.adapters["messaging"].start())
            elif name == "mcp":
                await self.adapters["mcp"].start_all()
            elif name == "gateway":
                asyncio.create_task(self.adapters["gateway"].start())
            print(f"Self-Healing: {name} restart initiated.")
        except Exception as e:
            print(f"Self-Healing Error: Failed to restart {name}: {e}")

    async def heartbeat_loop(self):
        """Monitor the health of all adapters and notify if any fail"""
        last_status = {}
        restart_counts = {}  # component -> count

        while True:
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
                "details": stats,
            }
        except Exception as e:
            health["memory"] = {"status": "down", "error": str(e)}

        # 2. OpenClaw
        try:
            is_connected = self.adapters["openclaw"].websocket is not None
            health["openclaw"] = {"status": "up" if is_connected else "down"}
        except Exception:
            health["openclaw"] = {"status": "down"}

        # 3. Messaging Server
        try:
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
        while True:
            try:
                print("Backup Loop: Creating memory database backup...")
                res = await self.memory.backup_database()
                print(f"Backup Loop: {res}")
            except Exception as e:
                print(f"Backup loop error: {e}")
            await asyncio.sleep(43200)  # Run every 12 hours

    async def pruning_loop(self):
        """Background task to prune old chat history every 24 hours"""
        while True:
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
        while True:
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

        platform_attachments = []
        if hasattr(message, "attachments") and message.attachments:
            for att in message.attachments:
                try:
                    # Map 'type' if it's a string to MessageType enum
                    if isinstance(att.get("type"), str):
                        att["type"] = MessageType(att["type"]).value
                    platform_attachments.append(MediaAttachment.from_dict(att))
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
    ):
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
                                att["metadata"]["redacted"] = True
                            else:
                                print(
                                    "Redaction-Agent: Verification FAILED. Blocking image."
                                )
                                att["content"] = (
                                    "[SECURITY BLOCK: Redaction verification failed]"
                                )
                                if "data" in att:
                                    del att["data"]
                        else:
                            # No sensitive regions detected in first pass
                            pass
                    except Exception as e:
                        print(f"Redaction failed: {e}")

        # Vision Policy Enforcement: Require approval for outbound images
        has_images = any(
            str(att.get("type")).lower() == "image"
            for att in getattr(message, "attachments", [])
        )

        if has_images and platform != "websocket":  # Web UI usually has its own preview
            auth = self.permissions.is_authorized("vision.outbound")
            if auth is False:
                print(f"Vision Policy: Outbound image blocked for {target_chat}")
                return
            if auth is None:  # ASK_EACH
                # If it's already a security message, don't loop
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
            for keyword in ["DECISION", "ARCHITECT", "PATTERN", "LEARNED LESSON"]
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

        # Update cache
        if target_chat in self.message_handler.chat_contexts:
            self.message_handler.chat_contexts[target_chat].append(
                {"role": "assistant", "content": message.content}
            )
            self.message_handler.chat_contexts[target_chat] = (
                self.message_handler.chat_contexts[target_chat][-10:]
            )

        # Route to appropriate adapter
        if platform in ["cloudflare", "vpn", "direct", "local", "gateway"]:
            if target_client:
                # Send back through Unified Gateway
                msg_payload = {
                    "type": "message",
                    "content": message.content,
                    "sender": message.sender,
                    "metadata": metadata,
                }
                await self.adapters["gateway"].send_message(target_client, msg_payload)
            else:
                # Broadcast or generic?
                # For now, let's assume we want to send to the last active client if no target
                if (
                    self.last_active_chat
                    and self.last_active_chat["platform"] == platform
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

    async def _trigger_voice_briefing(self, phone: str, chat_id: str, platform: str):
        """Generate a summary of recent events and call the admin to read it"""
        try:
            # 1. Fetch recent activity
            history = await self.memory.chat_read(chat_id, limit=20)
            if not history:
                script = "This is Mega Bot. No recent activity to report."
            else:
                # 2. Summarize
                history_text = "\n".join(
                    [f"{h['role']}: {h['content']}" for h in history]
                )
                summary_prompt = f"Summarize the following recent bot activity for a short voice briefing (max 50 words). Focus on completed tasks or pending approvals:\n\n{history_text}"
                summary = await self.llm.generate(
                    context="Voice Briefing",
                    messages=[{"role": "user", "content": summary_prompt}],
                )
                script = f"Hello, this is Mega Bot. Here is your recent activity briefing: {summary}"

            # 3. Make the call
            await self.adapters["messaging"].voice_adapter.make_call(phone, script)
        except Exception as e:
            print(f"Voice briefing failed: {e}")

    async def _verify_redaction(self, image_data: str) -> bool:
        """Use a separate vision pass to verify that redaction was successful"""
        try:
            # Re-analyze the image. The vision driver should return no sensitive_regions if successful.
            analysis_raw = await self.computer_driver.execute(
                "analyze_image", text=image_data
            )
            analysis = json.loads(analysis_raw)
            remaining_sensitive = analysis.get("sensitive_regions", [])

            if remaining_sensitive:
                print(
                    f"Redaction-Verification: FAILED. Found {len(remaining_sensitive)} remaining areas."
                )
                return False

            print("Redaction-Verification: PASSED.")
            return True
        except Exception as e:
            print(f"Redaction-Verification: Error during check: {e}")
            return False

    async def _start_approval_escalation(self, action: Dict):
        """Escalate via Voice Call if approval is not received within 5 minutes"""
        await asyncio.sleep(300)  # 5 minutes

        # Check if action is still in queue
        if any(a["id"] == action["id"] for a in self.admin_handler.approval_queue):
            print(
                f"Escalation: Approval {action['id']} timed out. Initiating Voice Call..."
            )

            # Check DND Hours
            now = datetime.now().hour
            dnd_start = getattr(self.config.system, "dnd_start", 22)
            dnd_end = getattr(self.config.system, "dnd_end", 7)

            is_dnd = False
            if dnd_start > dnd_end:
                is_dnd = now >= dnd_start or now < dnd_end
            else:
                is_dnd = dnd_start <= now < dnd_end

            if is_dnd:
                print("Escalation: DND active. Skipping voice call.")
                return

            # Check Dynamic DND via Calendar
            try:
                # Check for active calendar events that might indicate busy status
                events = await self.adapters["mcp"].call_tool(
                    "google-services", "list_events", {"limit": 3}
                )
                if events and isinstance(events, list):
                    for event in events:
                        summary = str(event.get("summary", "")).upper()
                        if any(
                            k in summary
                            for k in [
                                "BUSY",
                                "MEETING",
                                "DND",
                                "SLEEP",
                                "DO NOT DISTURB",
                            ]
                        ):
                            print(
                                f"Escalation: Dynamic DND active via Calendar ('{summary}'). Skipping call."
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

            if not all_lessons:
                return ""

            # 3. Distillation (if too many lessons)
            if len(all_lessons) > 3:
                lessons_text = "\n".join([f"- {l['content']}" for l in all_lessons])
                distill_prompt = f"Summarize the following architectural lessons into a concise, high-priority list (max 3 points):\n\n{lessons_text}"
                distilled = await self.llm.generate(
                    context="Memory Distillation",
                    messages=[{"role": "user", "content": distill_prompt}],
                )
                return f"\n[DISTILLED LESSONS FROM MEMORY]:\n{distilled}\n"

            # 4. Format lessons (standard)
            formatted = "\n[PROACTIVE LESSONS FROM MEMORY]:\n"
            for lesson in all_lessons[:10]:  # Cap at 10 most relevant
                prefix = (
                    "⚠️ CRITICAL: " if "CRITICAL" in lesson["content"].upper() else "- "
                )
                formatted += f"{prefix}{lesson['content']}\n"
            return formatted
        except Exception as e:
            print(f"Lesson injection failed: {e}")
            return ""

    async def run_autonomous_build(self, message: Message, websocket: WebSocket):
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
            json_match = re.search(r"\{.*\}", summary, re.DOTALL)
            if json_match:
                try:
                    synthesis_data = json.loads(json_match.group(0))
                    lesson = synthesis_data.get("learned_lesson", lesson)
                    summary = synthesis_data.get("summary", summary)
                except Exception as e:
                    print(f"DEBUG [Synthesis JSON Parse Error]: {e}")
                    # Fallback: regex search for learned_lesson field if JSON parse fails
                    lesson_match = re.search(
                        r'"learned_lesson":\s*"(.*?)"', summary, re.DOTALL
                    )
                    if lesson_match:
                        lesson = lesson_match.group(1)
            else:
                # Direct fallback: Look for "lesson:" or "CRITICAL:" in raw text
                fallback_match = re.search(
                    r"(?:learned_lesson|lesson|CRITICAL):?\s*(.*)",
                    str(synthesis_raw),
                    re.IGNORECASE,
                )
                if fallback_match:
                    lesson = fallback_match.group(1).strip()

            await self.memory.memory_write(
                key=f"lesson_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                type="learned_lesson",
                content=lesson,
                tags=["synthesis", name, role],
            )

            # Proactively notify UI of new memory
            for client in list(self.clients):
                await client.send_json(
                    {"type": "memory_update", "content": lesson, "source": name}
                )

            return summary
        except Exception as e:
            print(f"Failed to record memory lesson or parse synthesis: {e}")
            return str(synthesis_raw)

    async def _execute_tool_for_sub_agent(
        self, agent_name: str, tool_call: Dict
    ) -> str:
        """Execute a tool on behalf of a sub-agent with Domain Boundary enforcement"""
        agent = self.sub_agents.get(agent_name)
        if not agent:
            return "Error: Agent not found."

        tool_name = str(tool_call.get("name", "unknown"))
        tool_input = tool_call.get("input", {})

        # Enforce Domain Boundaries
        allowed_tools = agent._get_sub_tools()
        target_tool = next((t for t in allowed_tools if t["name"] == tool_name), None)

        if not target_tool:
            return f"Security Error: Tool '{tool_name}' is outside the domain boundaries for role '{agent.role}'."

        scope = str(target_tool.get("scope", "unknown"))

        # Check overall permissions
        auth = self.permissions.is_authorized(scope)
        if auth is False:
            return f"Security Error: Permission denied for scope '{scope}'."

        # Actual implementation of sub-tools
        try:
            if tool_name == "read_file":
                path = str(tool_input.get("path", ""))
                with open(path, "r") as f:
                    return f.read()
            elif tool_name == "write_file":
                path = str(tool_input.get("path", ""))
                content = str(tool_input.get("content", ""))
                with open(path, "w") as f:
                    f.write(content)
                return f"File '{path}' written successfully."
            elif tool_name == "run_test":
                import subprocess

                cmd = str(tool_input.get("command", ""))
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return f"Exit Code: {result.returncode}\nOutput: {result.stdout}\nError: {result.stderr}"
            elif tool_name == "query_rag":
                return await self.rag.navigate(str(tool_input.get("query", "")))
            elif tool_name == "analyze_data":
                dataset_name = str(tool_input.get("dataset_name", ""))
                query = str(tool_input.get("query", ""))
                code = tool_input.get("python_code")

                agent = self.features.get("dash_data")
                if not agent:
                    return "Error: Data Analysis feature not enabled."

                if code:
                    return await agent.execute_python_analysis(dataset_name, code)
                else:
                    return await agent.analyze(dataset_name, query)
        except Exception as e:
            return f"Tool Execution Error: {str(e)}"

        return f"Error: Tool '{tool_name}' logic not implemented."

    async def _handle_computer_tool(
        self,
        tool_input: Dict,
        websocket: WebSocket,
        action_id: str,
        callback: Optional[Any] = None,
    ):
        """Handle Anthropic Computer Use tool calls with Approval Interlock"""
        action_type = tool_input.get("action")
        description = f"Computer Use: {action_type} ({tool_input})"

        # Queue for approval
        import uuid

        action = {
            "id": action_id or str(uuid.uuid4()),
            "type": "computer_use",
            "payload": tool_input,
            "description": description,
            "websocket": websocket,
            "callback": callback,
        }
        self.admin_handler.approval_queue.append(action)

        await websocket.send_json(
            {
                "type": "status",
                "content": f"Computer action queued for approval: {action_type}",
            }
        )
        # Broadcast update
        for client in list(self.clients):
            await client.send_json({"type": "approval_required", "action": action})

    async def _llm_dispatch(
        self, prompt: str, context: Any, tools: Optional[List[Dict[str, Any]]] = None
    ) -> Any:
        """Unified tool selection logic using configured LLM provider"""
        return await self.llm.generate(prompt, context, tools=tools)

    def _check_policy(self, data: Dict) -> str:
        """Check if an action is pre-approved or pre-denied based on policies"""
        method = data.get("method")
        params = data.get("params", {})
        command = params.get("command", "")

        # Determine scope
        scope = str(method) if method else "unknown"
        if method in ["system.run", "shell.execute"] and command:
            # 1. Try full command match (both with and without 'shell.' prefix)
            # This handles policies set as 'git status' or 'shell.git status'
            for s in [f"shell.{command}", command]:
                auth = self.permissions.is_authorized(s)
                if auth is not None:
                    return "allow" if auth else "deny"

            # 2. Try granular scope (e.g., shell.git or just git)
            cmd_part = str(command).split()[0] if command else "unknown"
            for s in [f"shell.{cmd_part}", cmd_part]:
                auth = self.permissions.is_authorized(s)
                if auth is not None:
                    return "allow" if auth else "deny"

        auth = self.permissions.is_authorized(scope)

        if auth is True:
            return "allow"
        if auth is False:
            return "deny"
        return "ask"

    async def on_openclaw_event(self, data):
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

        # Check for chat-based admin commands from OpenClaw (WhatsApp/Telegram)
        if method == "chat.message" and content.startswith("!"):
            chat_id = params.get("chat_id") or sender_id
            platform = params.get("platform", "openclaw")
            if await self._handle_admin_command(content, sender_id, chat_id, platform):
                return  # Command handled

        # INTERCEPT: Check policies for sensitive system commands
        if method == "system.run" or method == "shell.execute":
            policy = self._check_policy(data)

            if policy == "allow":
                print(f"Policy: Auto-approving {method}")
                await self.adapters["openclaw"].send_message(data)
                return

            if policy == "deny":
                print(f"Policy: Auto-denying {method}")
                return  # Discard

            # Default: Queue for manual approval
            import uuid

            action = {
                "id": str(uuid.uuid4()),
                "type": "system_command",
                "payload": data,
                "description": f"Execute: {data.get('params', {}).get('command')}",
            }
            self.admin_handler.approval_queue.append(action)
            # Notify UI of new pending action
            for client in list(self.clients):
                await client.send_json({"type": "approval_required", "action": action})

            # Notify messaging server (for Signal/Telegram admins)
            admin_resp = Message(
                content=f"⚠️ Approval Required: {action['description']}\nType `!approve {action['id']}` to authorize.",
                sender="Security",
            )
            asyncio.create_task(self.send_platform_message(admin_resp))
            return

        # Relay standard events to all connected UI clients
        for client in list(self.clients):
            try:
                await client.send_json({"type": "openclaw_event", "payload": data})
            except Exception:
                self.clients.discard(client)

        # Also relay to Native Messaging Server clients
        if data.get("method") == "chat.message":
            params = data.get("params", {})
            msg = Message(
                content=params.get("content", ""),
                sender=params.get("sender", "OpenClaw"),
            )
            await self.send_platform_message(msg)

    def _sanitize_output(self, text: str) -> str:
        """Strip ANSI escape sequences and other potentially dangerous terminal characters"""
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        sanitized = ansi_escape.sub("", text)

        # Remove other control characters except newline and tab
        sanitized = "".join(ch for ch in sanitized if ch >= " " or ch in "\n\r\t")

        return sanitized

    async def _process_approval(self, action_id: str, approved: bool):
        """Execute or discard a pending sensitive action"""
        action = next(
            (a for a in self.admin_handler.approval_queue if a["id"] == action_id), None
        )
        if not action:
            return

        if approved:
            print(f"Action Approved: {action['type']}")
            if action["type"] == "system_command":
                # ... existing system_command logic ...
                params = action.get("payload", {}).get("params", {})
                cmd = params.get("command") if isinstance(params, dict) else None
                if cmd:
                    # Inject secrets before execution
                    cmd = self.secret_manager.inject_secrets(cmd)

                    # Execute and capture output
                    import subprocess

                    try:
                        # Tirith Guard validation before execution
                        if not tirith.validate(cmd):
                            output = "Security Error: Command blocked by Tirith Guard (Suspicious Unicode/Cyrillic detected)."
                        else:
                            result = subprocess.run(
                                cmd,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=30,
                            )
                            output = tirith.sanitize(result.stdout + result.stderr)

                        # Scrub secrets from output
                        output = self.secret_manager.scrub_secrets(output)
                    except Exception as e:
                        output = f"Command failed: {e}"

                    # Send back to the specific websocket that requested it
                    ws = action.get("websocket")
                    if ws:
                        await ws.send_json(
                            {"type": "terminal_output", "content": output}
                        )

                    # Also relay to OpenClaw if needed
                    await self.adapters["openclaw"].send_message(
                        {"method": "system.result", "params": {"output": output}}
                    )

            elif action["type"] == "outbound_vision":
                payload = action.get("payload", {})
                # Reconstruct and send the message now that it's approved
                approved_msg = Message(
                    content=payload.get("message_content", ""),
                    sender="MegaBot",
                    attachments=payload.get("attachments", []),
                )
                # Call send_platform_message again, but bypass vision check if possible or rely on policy change
                # To avoid re-queuing, we can temporarily set policy or use a flag.
                # Simplest: call the messaging adapter directly for this approved action.
                platform_msg = self._to_platform_message(
                    approved_msg, chat_id=payload.get("chat_id")
                )
                platform_msg.platform = payload.get("platform", "native")
                await self.adapters["messaging"].send_message(
                    platform_msg, target_client=payload.get("target_client")
                )
                print(f"Outbound vision approved and sent to {payload.get('chat_id')}")

            elif action["type"] == "data_execution":
                payload = action.get("payload", {})
                name = payload.get("name")
                code = payload.get("code")

                # We need access to the data agent.
                # This assumes we have a way to get it, usually it's a feature we discovery
                # For now, let's assume we can find it in discovery or it's a known global
                try:
                    # Generic way to find the data agent if it was registered
                    # In a real app, this might be self.features["dash_data"]
                    from features.dash_data.agent import DashDataAgent

                    temp_agent = DashDataAgent(self.llm, self)
                    # We'd need to restore the datasets, but for this prototype,
                    # we'll assume the agent that queued it is still alive or we recreate context
                    output = await temp_agent.execute_python_analysis(name, code)
                except Exception as e:
                    output = f"Approval execution failed: {e}"

                # Send back results to admins
                resp = Message(
                    content=f"✅ Data Execution Result:\n{output}", sender="DataAgent"
                )
                await self.send_platform_message(resp)

            elif action["type"] == "computer_use":
                payload = action.get("payload", {})

                # Execute actual computer action
                action_type = payload.get("action")
                coordinate = payload.get("coordinate")
                text = payload.get("text")

                output = await self.computer_driver.execute(
                    action_type, coordinate, text
                )
                print(f"Computer Action Result: {output}")

                ws = action.get("websocket")
                if ws:
                    # If it's a screenshot, send it as a special type
                    if action_type == "screenshot" and not output.startswith("Error"):
                        await ws.send_json({"type": "screenshot", "content": output})
                        output = "Screenshot captured and sent to UI."
                    else:
                        await ws.send_json({"type": "status", "content": output})

                # Report back to OpenClaw/LLM
                # We also include the action id so the LLM knows which call this corresponds to
                await self.adapters["openclaw"].send_message(
                    {
                        "method": "tool.result",
                        "params": {"id": action["id"], "output": output},
                    }
                )

                # If we have a resume callback, trigger it
                if "callback" in action and callable(action["callback"]):
                    await action["callback"](output)

            elif action["type"] == "identity_link":
                payload = action.get("payload", {})
                internal_id = payload.get("internal_id")
                platform = payload.get("platform")
                platform_id = payload.get("platform_id")
                chat_id = payload.get("chat_id")

                if internal_id and platform and platform_id:
                    await self.memory.link_identity(internal_id, platform, platform_id)
                    resp = Message(
                        content=f"✅ Identity Link Verified: '{internal_id}' linked to {platform}:{platform_id}",
                        sender="System",
                    )
                    await self.send_platform_message(
                        resp, chat_id=chat_id, platform=platform
                    )
        else:
            print(f"Action Denied: {action['type']}")
            # Notify the callback of failure/denial
            if "callback" in action and callable(action["callback"]):
                await action["callback"]("Action denied by user.")

        self.admin_handler.approval_queue = [
            a for a in self.admin_handler.approval_queue if a["id"] != action_id
        ]

        # Broadcast queue update to all clients
        for client in list(self.clients):
            try:
                await client.send_json(
                    {
                        "type": "approval_queue_updated",
                        "queue": self.admin_handler.approval_queue,
                    }
                )
            except Exception as e:
                print(f"Failed to notify client of queue update: {e}")
                self.clients.discard(client)

    async def sync_loop(self):
        while True:
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
            while True:
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


@app.post("/ivr")
async def ivr_callback(request: Request, action_id: str = Query(...)):
    form_data = await request.form()
    digits = form_data.get("Digits")

    if orchestrator:
        if digits == "1":
            await orchestrator.admin_handler._process_approval(action_id, approved=True)
            response_text = "Action approved. Thank you."
        else:
            await orchestrator.admin_handler._process_approval(
                action_id, approved=False
            )
            response_text = "Action rejected."
    else:
        response_text = "System error."

    return Response(
        content=f"<Response><Say>{response_text}</Say></Response>",
        media_type="application/xml",
    )


@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "MegaBot API is running",
        "version": "0.2.0-alpha",
        "endpoints": ["/ws", "/health"],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if orchestrator:
        await orchestrator.handle_client(websocket)
    else:
        await websocket.accept()
        await websocket.send_text("Orchestrator not initialized")
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run(app, host=config.system.bind_address, port=8000)
