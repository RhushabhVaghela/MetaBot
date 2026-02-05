# MegaBot Adapter Development Guide

This guide explains how to create custom adapters for MegaBot to extend its capabilities.

## Overview

MegaBot uses a **Modular Adapter Architecture** where adapters are thin wrappers that implement standardized interfaces. This allows you to integrate new messaging platforms, memory systems, and tools without modifying the core orchestrator.

## Adapter Types

### 1. Messaging Adapters (`MessagingInterface`)

Used for communication platforms (WhatsApp, Telegram, custom WebSocket, etc.)

```python
from core.interfaces import MessagingInterface, Message

class MyPlatformAdapter(MessagingInterface):
    async def send_message(self, message: Message) -> None:
        # Send message to your platform
        pass
    
    async def receive_message(self) -> Message:
        # Receive message from your platform
        pass
```

**Example:** See `adapters/openclaw_adapter.py` for a complete WebSocket-based implementation.

### 2. Memory Adapters (`MemoryInterface`)

Used for storing and retrieving context/data.

```python
from core.interfaces import MemoryInterface

class MyMemoryAdapter(MemoryInterface):
    async def store(self, key: str, value: Any) -> None:
        # Store data
        pass
    
    async def retrieve(self, key: str) -> Any:
        # Retrieve data
        pass
    
    async def search(self, query: str) -> list[Any]:
        # Search memory
        pass
```

**Example:** See `adapters/memu_adapter.py` for the memU integration.

### 3. Tool Adapters (`ToolInterface`)

Used for executing tools and commands.

```python
from core.interfaces import ToolInterface

class MyToolAdapter(ToolInterface):
    async def execute(self, **kwargs) -> Any:
        # Execute tool
        pass
```

**Example:** See `adapters/mcp_adapter.py` for MCP server integration.

## Creating a New Adapter

### Step 1: Choose Your Interface

Decide which interface your adapter will implement based on its purpose.

### Step 2: Create the Adapter File

Create a new file in `adapters/`:

```python
# adapters/my_adapter.py
from core.interfaces import MessagingInterface, Message
from typing import Any, Optional

class MyAdapter(MessagingInterface):
    def __init__(self, config: dict):
        self.config = config
        self.connection = None
    
    async def connect(self):
        # Initialize connection
        pass
    
    async def send_message(self, message: Message) -> None:
        # Implementation
        pass
    
    async def receive_message(self) -> Message:
        # Implementation
        pass
```

### Step 3: Register in Orchestrator

Add your adapter to `core/orchestrator.py`:

```python
from adapters.my_adapter import MyAdapter

class MegaBotOrchestrator:
    def __init__(self, config):
        self.adapters = {
            # ... existing adapters
            "my_adapter": MyAdapter(config.adapters['my_adapter']),
        }
```

### Step 4: Add Configuration

Update `mega-config.yaml`:

```yaml
adapters:
  my_adapter:
    host: "127.0.0.1"
    port: 12345
    auth_token: "your-token"
```

### Step 5: Write Tests

Create tests in `tests/test_my_adapter.py`:

```python
import pytest
from adapters.my_adapter import MyAdapter

@pytest.mark.asyncio
async def test_my_adapter():
    adapter = MyAdapter({"host": "localhost"})
    # Add tests
```

## Best Practices

### Error Handling

Always handle errors gracefully:

```python
async def send_message(self, message: Message) -> None:
    try:
        await self.connection.send(message.content)
    except ConnectionError as e:
        print(f"Failed to send message: {e}")
        # Optionally retry or queue for later
```

### Async/Await

All adapter methods should be async:

```python
# Good
async def store(self, key: str, value: Any) -> None:
    await self.db.write(key, value)

# Bad
def store(self, key: str, value: Any) -> None:
    self.db.write(key, value)
```

### Type Hints

Use type hints for better code clarity:

```python
from typing import Any, Optional, Dict

async def execute(self, method: str, params: Dict[str, Any]) -> Optional[Any]:
    pass
```

### Fallback Behavior

Implement graceful fallbacks for external dependencies:

```python
def __init__(self, path: str):
    try:
        from external_lib import Service
        self.service = Service(path)
    except ImportError:
        print("Warning: External service not found, using mock")
        self.service = MockService()
```

## Available Adapters Reference

### Built-in Adapters

| Adapter | Interface | Purpose | Status |
|---------|-----------|---------|--------|
| `OpenClawAdapter` | `MessagingInterface` | WebSocket gateway to OpenClaw | ✅ Production |
| `MemUAdapter` | `MemoryInterface` | Hierarchical memory with proactive retrieval | ✅ Production |
| `MCPAdapter` | `ToolInterface` | Model Context Protocol server bridge | ✅ Production |
| `MegaBotMessagingServer` | Native | Encrypted WebSocket messaging | ✅ Production |
| `UnifiedGateway` | Native | Multi-access gateway (Cloudflare, VPN, HTTPS) | ✅ Production |

### Platform Adapters

| Adapter | Interface | Purpose | Status |
|---------|-----------|---------|--------|
| `WhatsAppAdapter` | `PlatformAdapter` | WhatsApp Business API with push notifications | ✅ Implemented |
| `TelegramAdapter` | `PlatformAdapter` | Telegram Bot API | ✅ Fully Implemented |
| `SignalAdapter` | `PlatformAdapter` | Signal via signal-cli | ✅ Fully Implemented |
| `PushNotificationAdapter` | `PlatformAdapter` | FCM/APNS Push Notifications | ✅ Fully Implemented |
| `IMessageAdapter` | `PlatformAdapter` | iMessage (macOS) | ⚠️ Basic Implementation |
| `SMSAdapter` | `PlatformAdapter` | SMS via Twilio | ⚠️ Basic Implementation |
| `DiscordAdapter` | `PlatformAdapter` | Discord Bot API with embeds & media | ✅ Fully Implemented |
| `SlackAdapter` | `PlatformAdapter` | Slack SDK with Socket Mode & media | ✅ Fully Implemented |
| `NanobotAdapter` | `MessagingInterface` | Telegram/WhatsApp with market analysis & routines | ✅ New Implementation |


#### WhatsApp Adapter Features

The `WhatsAppAdapter` provides full WhatsApp Business API integration:

**Messaging:**
- Text messages with WhatsApp markup formatting (bold, italic, code)
- Media sharing (images, videos, documents, audio)
- Location sharing
- Contact cards

**Push Notifications:**
- Interactive buttons (quick reply, URL, call buttons)
- Interactive lists (menu-based flows)
- Reply buttons for simple selections
- Catalog messages for product sharing

**Business Notifications:**
- Order notifications with tracking buttons
- Payment confirmations with receipts
- Appointment reminders with confirmations

**Group Features:**
- Create groups
- Add/remove participants
- Group participant management

**Webhook Support:**
- Process incoming messages
- Handle button replies
- Message status updates

## Testing Adapters

Run adapter tests:

```bash
pytest tests/test_megabot_messaging.py -v
```

Run all tests with coverage:

```bash
pytest --cov --cov-report=term-missing -q
```

**Current Coverage**: 96% overall, 226 tests passing

## Troubleshooting

### Adapter Not Loading

1. Check that the adapter class implements the correct interface
2. Verify configuration in `mega-config.yaml`
3. Check for import errors in logs

### Connection Issues

1. Verify network connectivity
2. Check authentication credentials
3. Ensure ports are not blocked by firewall

### Memory Leaks

1. Ensure proper cleanup in adapter shutdown
2. Close connections when done
3. Use context managers where possible

## Contributing

When contributing a new adapter:

1. Follow the existing code style
2. Add comprehensive tests
3. Update this documentation
4. Add example configuration to README
5. Ensure 90%+ test coverage

## Example: Complete Custom Adapter

```python
# adapters/custom_platform.py
import asyncio
import websockets
from typing import Any, Optional
from core.interfaces import MessagingInterface, Message

class CustomPlatformAdapter(MessagingInterface):
    """
    Example adapter for a custom messaging platform.
    """
    
    def __init__(self, host: str, port: int, api_key: str):
        self.host = host
        self.port = port
        self.api_key = api_key
        self.websocket = None
        self.on_message = None
    
    async def connect(self, on_message=None):
        """Connect to the platform's WebSocket."""
        self.on_message = on_message
        uri = f"ws://{self.host}:{self.port}?token={self.api_key}"
        self.websocket = await websockets.connect(uri)
        asyncio.create_task(self._listen())
    
    async def _listen(self):
        """Background listener for incoming messages."""
        try:
            async for message in self.websocket:
                if self.on_message:
                    await self.on_message(message)
        except Exception as e:
            print(f"Connection error: {e}")
    
    async def send_message(self, message: Message) -> None:
        """Send a message to the platform."""
        if not self.websocket:
            await self.connect()
        
        payload = {
            "type": "message",
            "content": message.content,
            "sender": message.sender
        }
        await self.websocket.send(json.dumps(payload))
    
    async def receive_message(self) -> Message:
        """Receive a message (for polling mode)."""
        # Implementation for polling mode
        pass
    
    async def disconnect(self):
        """Clean up resources."""
        if self.websocket:
            await self.websocket.close()
```

## Security Considerations

When developing adapters:

1. **Never hardcode credentials** - Use environment variables or config files
2. **Validate all inputs** - Sanitize data before processing
3. **Use encryption** - Enable TLS/SSL for all connections
4. **Implement rate limiting** - Prevent abuse
5. **Log security events** - Track authentication failures

---

For questions or support, refer to the main README or open an issue on GitHub.
