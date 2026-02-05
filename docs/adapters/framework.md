# Adapter Framework Guide

Complete guide to building and integrating adapters in MegaBot.

## Table of Contents

- [Overview](#overview)
- [Adapter Types](#adapter-types)
- [Base Classes](#base-classes)
- [Messaging Adapters](#messaging-adapters)
- [Tool Adapters](#tool-adapters)
- [Implementation Guide](#implementation-guide)
- [Testing Adapters](#testing-adapters)
- [Best Practices](#best-practices)

## Overview

Adapters are the bridge between MegaBot's core and external services. They provide a standardized interface for integrating different platforms and tools while maintaining security and reliability.

### Key Principles

- **Standardization**: All adapters implement common interfaces
- **Isolation**: Adapters run in separate processes/threads
- **Security**: All adapter inputs/outputs are validated
- **Monitoring**: Health checks and error reporting
- **Configuration**: Environment-based configuration
- **Async**: All operations are asynchronous

## Adapter Types

### 1. Messaging Adapters
Handle communication with chat platforms and messaging services.

**Examples:**
- Telegram, Signal, Discord, Slack, WhatsApp
- WebSocket, SMS, Push Notifications

### 2. Tool Adapters
Provide access to external tools and services.

**Examples:**
- MCP servers, OpenClaw, File system tools
- API integrations, Database connectors

### 3. Infrastructure Adapters
Manage infrastructure components.

**Examples:**
- Database adapters, Cache systems
- Monitoring and logging services

## Base Classes

### MessagingAdapter Base Class

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from dataclasses import dataclass

@dataclass
class AdapterHealth:
    status: str  # "up", "down", "degraded"
    message: str
    last_check: datetime
    metadata: dict = None

@dataclass
class PlatformMessage:
    id: str
    platform: str
    sender_id: str
    sender_name: str
    chat_id: str
    content: str
    message_type: str  # "text", "image", "file", etc.
    timestamp: datetime
    attachments: list = None
    metadata: dict = None

class MessagingAdapter(ABC):
    """Base class for all messaging platform adapters"""

    def __init__(self, config: dict):
        self.config = config
        self._running = False

    @abstractmethod
    async def start(self) -> bool:
        """Initialize and start the adapter"""
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """Gracefully stop the adapter"""
        pass

    @abstractmethod
    async def send_message(self, message: PlatformMessage) -> bool:
        """Send a message to the platform"""
        pass

    @abstractmethod
    async def receive_messages(self) -> AsyncGenerator[PlatformMessage, None]:
        """Yield incoming messages from the platform"""
        pass

    @abstractmethod
    async def get_health(self) -> AdapterHealth:
        """Return current adapter health status"""
        pass

    @property
    def is_running(self) -> bool:
        return self._running
```

### ToolAdapter Base Class

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class ToolResult:
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: dict = None

@dataclass
class ToolInfo:
    name: str
    description: str
    input_schema: dict
    output_schema: dict = None

class ToolAdapter(ABC):
    """Base class for tool integration adapters"""

    def __init__(self, config: dict):
        self.config = config
        self._tools = {}

    @abstractmethod
    async def initialize(self) -> bool:
        """Set up tool connections and discover available tools"""
        pass

    @abstractmethod
    async def cleanup(self) -> bool:
        """Clean up tool connections"""
        pass

    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolResult:
        """Execute a specific tool with given parameters"""
        pass

    @abstractmethod
    async def list_tools(self) -> Dict[str, ToolInfo]:
        """Return information about available tools"""
        pass

    @abstractmethod
    async def get_tool_health(self, tool_name: str) -> AdapterHealth:
        """Check health of a specific tool"""
        pass
```

## Messaging Adapters

### Telegram Adapter Example

```python
import asyncio
import logging
from typing import AsyncGenerator
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters

from .base import MessagingAdapter, PlatformMessage, AdapterHealth

class TelegramAdapter(MessagingAdapter):
    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get('bot_token')
        self.application = None
        self.message_queue = asyncio.Queue()

    async def start(self) -> bool:
        try:
            self.application = Application.builder().token(self.bot_token).build()

            # Add message handler
            self.application.add_handler(
                MessageHandler(filters.TEXT, self._handle_message)
            )

            # Start polling in background
            await self.application.initialize()
            await self.application.start()
            asyncio.create_task(self.application.updater.start_polling())

            self._running = True
            logging.info("Telegram adapter started successfully")
            return True
        except Exception as e:
            logging.error(f"Failed to start Telegram adapter: {e}")
            return False

    async def stop(self) -> bool:
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
        self._running = False
        return True

    async def send_message(self, message: PlatformMessage) -> bool:
        try:
            bot = Bot(token=self.bot_token)
            await bot.send_message(
                chat_id=message.chat_id,
                text=message.content
            )
            return True
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")
            return False

    async def receive_messages(self) -> AsyncGenerator[PlatformMessage, None]:
        while self._running:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                yield message
            except asyncio.TimeoutError:
                continue

    async def get_health(self) -> AdapterHealth:
        try:
            bot = Bot(token=self.bot_token)
            bot_info = await bot.get_me()
            return AdapterHealth(
                status="up",
                message=f"Connected as @{bot_info.username}",
                last_check=datetime.now()
            )
        except Exception as e:
            return AdapterHealth(
                status="down",
                message=str(e),
                last_check=datetime.now()
            )

    async def _handle_message(self, update: Update, context):
        """Handle incoming Telegram messages"""
        message = PlatformMessage(
            id=str(update.message.message_id),
            platform="telegram",
            sender_id=str(update.message.from_user.id),
            sender_name=update.message.from_user.username or update.message.from_user.first_name,
            chat_id=str(update.message.chat_id),
            content=update.message.text,
            message_type="text",
            timestamp=update.message.date
        )

        await self.message_queue.put(message)
```

### WebSocket Adapter Example

```python
import asyncio
import json
import logging
from typing import Dict, Set
import websockets
from websockets.exceptions import ConnectionClosedError

from .base import MessagingAdapter, PlatformMessage, AdapterHealth

class WebSocketAdapter(MessagingAdapter):
    def __init__(self, config: dict):
        super().__init__(config)
        self.host = config.get('host', 'localhost')
        self.port = config.get('port', 18790)
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.message_queue = asyncio.Queue()

    async def start(self) -> bool:
        try:
            server = await websockets.serve(
                self._handle_connection,
                self.host,
                self.port
            )
            logging.info(f"WebSocket server started on {self.host}:{self.port}")
            self._running = True
            return True
        except Exception as e:
            logging.error(f"Failed to start WebSocket adapter: {e}")
            return False

    async def stop(self) -> bool:
        # Close all client connections
        for client in list(self.clients.values()):
            await client.close()

        self.clients.clear()
        self._running = False
        return True

    async def send_message(self, message: PlatformMessage) -> bool:
        target_client = self.clients.get(message.chat_id)
        if not target_client:
            return False

        try:
            payload = {
                "type": "message",
                "content": message.content,
                "sender": message.sender_name,
                "timestamp": message.timestamp.isoformat()
            }
            await target_client.send(json.dumps(payload))
            return True
        except Exception as e:
            logging.error(f"Failed to send WebSocket message: {e}")
            return False

    async def receive_messages(self) -> AsyncGenerator[PlatformMessage, None]:
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                yield message
            except asyncio.TimeoutError:
                continue

    async def get_health(self) -> AdapterHealth:
        client_count = len(self.clients)
        return AdapterHealth(
            status="up" if self._running else "down",
            message=f"Server running with {client_count} clients",
            last_check=datetime.now(),
            metadata={"client_count": client_count}
        )

    async def _handle_connection(self, websocket, path):
        """Handle individual WebSocket connections"""
        client_id = str(id(websocket))
        self.clients[client_id] = websocket

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    platform_message = PlatformMessage(
                        id=data.get('id', str(uuid.uuid4())),
                        platform="websocket",
                        sender_id=client_id,
                        sender_name=data.get('sender', 'WebClient'),
                        chat_id=client_id,
                        content=data.get('content', ''),
                        message_type=data.get('type', 'text'),
                        timestamp=datetime.now(),
                        metadata=data
                    )
                    await self.message_queue.put(platform_message)
                except json.JSONDecodeError:
                    logging.warning("Received invalid JSON message")
        except ConnectionClosedError:
            pass
        finally:
            # Clean up disconnected client
            self.clients.pop(client_id, None)
```

## Tool Adapters

### MCP Adapter Implementation

```python
import asyncio
import json
import logging
from typing import Dict, List
from pathlib import Path
import subprocess
import aiofiles

from .base import ToolAdapter, ToolResult, ToolInfo, AdapterHealth

class MCPAdapter(ToolAdapter):
    def __init__(self, config: dict):
        super().__init__(config)
        self.servers_config = config.get('servers', [])
        self.running_servers: Dict[str, subprocess.Popen] = {}
        self.server_ports: Dict[str, int] = {}

    async def initialize(self) -> bool:
        """Start all configured MCP servers"""
        success = True
        for server_config in self.servers_config:
            if not await self._start_server(server_config):
                success = False
        return success

    async def cleanup(self) -> bool:
        """Stop all running MCP servers"""
        for server_name, process in self.running_servers.items():
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except Exception as e:
                logging.error(f"Failed to stop MCP server {server_name}: {e}")

        self.running_servers.clear()
        self.server_ports.clear()
        return True

    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolResult:
        """Execute a tool via MCP protocol"""
        # Find which server provides this tool
        server_name = self._find_tool_server(tool_name)
        if not server_name:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{tool_name}' not found"
            )

        port = self.server_ports.get(server_name)
        if not port:
            return ToolResult(
                success=False,
                output=None,
                error=f"Server '{server_name}' not running"
            )

        try:
            # Send tool execution request to MCP server
            result = await self._call_mcp_server(port, tool_name, parameters)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )

    async def list_tools(self) -> Dict[str, ToolInfo]:
        """List all available tools from all servers"""
        tools = {}
        for server_name in self.running_servers.keys():
            port = self.server_ports.get(server_name)
            if port:
                try:
                    server_tools = await self._list_server_tools(port)
                    tools.update(server_tools)
                except Exception as e:
                    logging.error(f"Failed to list tools for {server_name}: {e}")
        return tools

    async def get_tool_health(self, tool_name: str) -> AdapterHealth:
        server_name = self._find_tool_server(tool_name)
        if not server_name:
            return AdapterHealth(
                status="down",
                message=f"Tool '{tool_name}' not found",
                last_check=datetime.now()
            )

        process = self.running_servers.get(server_name)
        if not process or process.poll() is not None:
            return AdapterHealth(
                status="down",
                message=f"Server '{server_name}' not running",
                last_check=datetime.now()
            )

        return AdapterHealth(
            status="up",
            message=f"Tool '{tool_name}' available",
            last_check=datetime.now()
        )

    async def _start_server(self, config: dict) -> bool:
        """Start a single MCP server"""
        server_name = config['name']
        command = config['command']
        args = config.get('args', [])
        env = config.get('env', {})

        try:
            # Find available port
            port = self._find_free_port()

            # Start server process
            full_env = os.environ.copy()
            full_env.update(env)
            full_env['MCP_PORT'] = str(port)

            process = subprocess.Popen(
                [command] + args,
                env=full_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait for server to be ready
            await asyncio.sleep(2)

            if process.poll() is None:
                self.running_servers[server_name] = process
                self.server_ports[server_name] = port
                logging.info(f"MCP server '{server_name}' started on port {port}")
                return True
            else:
                stdout, stderr = process.communicate()
                logging.error(f"Failed to start MCP server '{server_name}': {stderr.decode()}")
                return False

        except Exception as e:
            logging.error(f"Error starting MCP server '{server_name}': {e}")
            return False

    def _find_free_port(self) -> int:
        """Find an available port"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    async def _call_mcp_server(self, port: int, tool_name: str, params: dict) -> Any:
        """Make HTTP call to MCP server"""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://localhost:{port}/tools/{tool_name}/execute",
                json=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('output')
                else:
                    error = await response.text()
                    raise Exception(f"MCP server error: {error}")

    async def _list_server_tools(self, port: int) -> Dict[str, ToolInfo]:
        """Get tool list from MCP server"""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:{port}/tools",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    tools_data = await response.json()
                    return {
                        name: ToolInfo(**info)
                        for name, info in tools_data.items()
                    }
                else:
                    raise Exception(f"Failed to list tools: {response.status}")

    def _find_tool_server(self, tool_name: str) -> Optional[str]:
        """Find which server provides a specific tool"""
        # This would need to be implemented based on your tool registry
        # For simplicity, assume tools are prefixed with server name
        for server_name in self.running_servers.keys():
            if tool_name.startswith(f"{server_name}_"):
                return server_name
        return None
```

## Implementation Guide

### Step 1: Define Adapter Requirements

```python
# adapter_requirements.py
class AdapterRequirements:
    def __init__(self):
        self.name = "telegram"
        self.version = "1.0.0"
        self.dependencies = [
            "python-telegram-bot>=20.0",
            "aiohttp>=3.8.0"
        ]
        self.environment_variables = [
            "TELEGRAM_BOT_TOKEN"
        ]
        self.configuration_schema = {
            "type": "object",
            "properties": {
                "bot_token": {"type": "string"},
                "webhook_url": {"type": "string"},
                "max_connections": {"type": "integer", "default": 100}
            },
            "required": ["bot_token"]
        }
```

### Step 2: Implement Adapter Class

```python
# adapters/my_adapter.py
from .base import MessagingAdapter

class MyCustomAdapter(MessagingAdapter):
    def __init__(self, config: dict):
        super().__init__(config)
        self.validate_config(config)
        # Initialize adapter-specific components

    def validate_config(self, config: dict):
        """Validate adapter configuration"""
        required_keys = ['api_key', 'endpoint']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")

    async def start(self) -> bool:
        # Implementation
        pass

    async def stop(self) -> bool:
        # Implementation
        pass

    async def send_message(self, message: PlatformMessage) -> bool:
        # Implementation
        pass

    async def receive_messages(self):
        # Implementation
        pass

    async def get_health(self) -> AdapterHealth:
        # Implementation
        pass
```

### Step 3: Register Adapter

```python
# adapters/__init__.py
from .my_adapter import MyCustomAdapter

ADAPTER_REGISTRY = {
    'my_adapter': MyCustomAdapter
}

def create_adapter(adapter_type: str, config: dict):
    """Factory function to create adapters"""
    adapter_class = ADAPTER_REGISTRY.get(adapter_type)
    if not adapter_class:
        raise ValueError(f"Unknown adapter type: {adapter_type}")
    return adapter_class(config)
```

### Step 4: Configuration Integration

```yaml
# mega-config.yaml
adapters:
  my_adapter:
    enabled: true
    api_key: "${MY_ADAPTER_API_KEY}"
    endpoint: "https://api.example.com"
    timeout: 30
    retry_attempts: 3
```

## Testing Adapters

### Unit Test Template

```python
# tests/test_my_adapter.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from adapters.my_adapter import MyCustomAdapter

class TestMyCustomAdapter:
    @pytest.fixture
    def adapter_config(self):
        return {
            'api_key': 'test_key',
            'endpoint': 'https://test.example.com'
        }

    @pytest.fixture
    def adapter(self, adapter_config):
        return MyCustomAdapter(adapter_config)

    @pytest.mark.asyncio
    async def test_start_success(self, adapter):
        # Mock external dependencies
        with patch('my_adapter.ExternalAPI') as mock_api:
            mock_api.return_value.connect.return_value = True

            result = await adapter.start()
            assert result is True
            assert adapter.is_running is True

    @pytest.mark.asyncio
    async def test_send_message_success(self, adapter):
        message = PlatformMessage(
            id="test_123",
            platform="my_adapter",
            sender_id="user_456",
            sender_name="Test User",
            chat_id="chat_789",
            content="Hello World",
            message_type="text",
            timestamp=datetime.now()
        )

        with patch.object(adapter, '_send_to_api') as mock_send:
            mock_send.return_value = True

            result = await adapter.send_message(message)
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_up(self, adapter):
        adapter._running = True

        health = await adapter.get_health()
        assert health.status == "up"
        assert "running" in health.message.lower()
```

### Integration Test Template

```python
# tests/integration/test_my_adapter_integration.py
import pytest
import asyncio
from adapters.my_adapter import MyCustomAdapter

@pytest.mark.integration
class TestMyCustomAdapterIntegration:
    @pytest.fixture(scope="class")
    def adapter_config(self):
        return {
            'api_key': os.getenv('TEST_API_KEY'),
            'endpoint': 'https://test.example.com'
        }

    @pytest.fixture(scope="class")
    async def adapter(self, adapter_config):
        adapter = MyCustomAdapter(adapter_config)
        await adapter.start()
        yield adapter
        await adapter.stop()

    @pytest.mark.asyncio
    async def test_full_message_flow(self, adapter):
        # Send test message
        test_message = PlatformMessage(
            id="integration_test_123",
            platform="my_adapter",
            sender_id="test_user",
            sender_name="Integration Test",
            chat_id="test_chat",
            content="Integration test message",
            message_type="text",
            timestamp=datetime.now()
        )

        # Send message
        send_result = await adapter.send_message(test_message)
        assert send_result is True

        # Receive messages (this might take time in real implementation)
        messages = []
        async for message in adapter.receive_messages():
            messages.append(message)
            if len(messages) >= 1:  # Expect at least our test message
                break

        assert len(messages) > 0
        # Verify message content
```

## Best Practices

### 1. Error Handling
- Always catch and log exceptions
- Return meaningful error messages
- Implement retry logic for transient failures
- Use exponential backoff for retries

### 2. Resource Management
- Properly clean up connections in `stop()`
- Implement connection pooling where appropriate
- Monitor resource usage (memory, connections)
- Handle rate limits gracefully

### 3. Security
- Validate all inputs and outputs
- Use secure credential storage
- Implement timeouts for all operations
- Log security events appropriately

### 4. Performance
- Use async/await for all I/O operations
- Implement connection reuse
- Batch operations where possible
- Monitor and optimize slow operations

### 5. Monitoring
- Implement comprehensive health checks
- Log important events and metrics
- Provide debugging information
- Alert on critical failures

### 6. Configuration
- Use environment variables for secrets
- Provide sensible defaults
- Validate configuration on startup
- Support runtime configuration updates

### 7. Testing
- Write comprehensive unit tests
- Mock external dependencies
- Test error conditions
- Include integration tests for critical paths

### 8. Documentation
- Document all public methods
- Provide configuration examples
- Include troubleshooting guides
- Update docs with API changes