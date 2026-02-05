# Approval Workflow Documentation

MegaBot implements a sophisticated approval workflow system that provides human oversight for sensitive AI operations, ensuring security while maintaining operational efficiency.

## Overview

The approval system acts as a "human-in-the-loop" safeguard for actions that could have security, privacy, or operational impact. It combines multiple notification channels with escalation mechanisms to ensure timely responses.

## Core Components

### 1. Approval Queue

All pending approvals are managed in a centralized queue within the `AdminHandler` class.

```python
class AdminHandler:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.approval_queue = []  # Queue for sensitive actions
```

#### Queue Structure
Each approval action contains:
```python
action = {
    "id": str(uuid.uuid4()),  # Unique identifier
    "type": "action_type",    # e.g., "shell_command", "vision_outbound", "identity_link"
    "payload": {...},         # Action-specific data
    "description": "...",     # Human-readable description
    "timestamp": datetime.now()  # Creation time
}
```

### 2. Permission-Based Triggering

Actions are queued based on the permission manager's evaluation:

```python
# In orchestrator.py
auth = self.permissions.is_authorized("shell.execute")
if auth is False:      # NEVER - Block immediately
    return False
elif auth is None:     # ASK_EACH - Queue for approval
    # Create approval action and queue it
    action = self._create_approval_action("shell_command", ...)
    self.admin_handler.approval_queue.append(action)
    return True  # Action queued, not executed yet
else:                  # True - AUTO - Execute immediately
    return self._execute_command(...)
```

## Approval Methods

### 1. Chat-Based Approval

Admins can approve/reject actions through any connected messaging platform.

#### Commands
- `!approve [action_id]` - Approve the specified action
- `!yes` - Approve the most recent action
- `!reject [action_id]` - Reject the specified action
- `!no` - Reject the most recent action

#### Example Usage
```
User: Please run "rm -rf /tmp/cache"
MegaBot: ⚠️ Shell Command Approval Required: rm -rf /tmp/cache
         Type `!approve abc123` to authorize.

Admin: !approve abc123
MegaBot: ✅ Action approved: rm -rf /tmp/cache
```

### 2. Voice Call Escalation

If an approval isn't received within 5 minutes, the system automatically escalates to a voice call.

#### Escalation Logic
```python
async def _start_approval_escalation(self, action: Dict):
    await asyncio.sleep(300)  # 5 minutes

    # Check if action is still pending
    if action in self.approval_queue:
        # Check DND settings
        if not self._is_dnd_active():
            # Make voice call
            await self._make_escalation_call(action)
```

#### DND (Do Not Disturb) Detection

The system respects administrator availability through multiple DND mechanisms:

1. **Time-Based DND**
```python
dnd_start = getattr(self.config.system, "dnd_start", 22)  # 10 PM
dnd_end = getattr(self.config.system, "dnd_end", 7)      # 7 AM
```

2. **Calendar-Based DND**
```python
# Check for busy/meeting events in calendar
events = await self.adapters["mcp"].call_tool(
    "google-services", "list_events", {"limit": 3}
)
for event in events:
    if any(keyword in event.get("summary", "").upper()
           for keyword in ["BUSY", "MEETING", "DND", "SLEEP"]):
        return True  # DND active
```

#### Voice Call Integration
```python
async def _make_escalation_call(self, action: Dict):
    admin_phone = getattr(self.config.system, "admin_phone", None)
    if admin_phone and self.adapters["messaging"].voice_adapter:
        script = f"Hello, this is Mega Bot. A critical approval is pending: {action['description']}"
        await self.adapters["messaging"].voice_adapter.make_call(
            admin_phone, script, ivr=True, action_id=action["id"]
        )
```

### 3. Multi-Channel Notifications

Approvals are broadcast across all connected platforms simultaneously.

```python
# Notify all admin platforms
for platform in connected_platforms:
    await self.send_platform_message(
        approval_message,
        platform=platform,
        target_client=admin_id
    )
```

## Action Types

### 1. Shell Commands

Triggered for system shell operations.

```python
action = {
    "type": "shell_command",
    "payload": {
        "command": "rm -rf /tmp/cache",
        "working_directory": "/tmp",
        "environment": {...}
    },
    "description": "Execute shell command: rm -rf /tmp/cache"
}
```

### 2. Vision/Image Operations

Triggered for outbound image sharing to prevent data leakage.

```python
action = {
    "type": "outbound_vision",
    "payload": {
        "message_content": "Here's the screenshot you requested",
        "attachments": [...],
        "platform": "telegram",
        "chat_id": "123456"
    },
    "description": "Send image to telegram:chat_123456"
}
```

### 3. Identity Linking

Triggered when users claim to be specific identities.

```python
action = {
    "type": "identity_link",
    "payload": {
        "internal_id": "JohnDoe",
        "platform": "telegram",
        "platform_id": "123456789",
        "chat_id": "chat_001"
    },
    "description": "Link telegram ID to identity 'JohnDoe'"
}
```

### 4. File System Operations

Triggered for file read/write operations (when configured).

```python
action = {
    "type": "filesystem_write",
    "payload": {
        "path": "/etc/hosts",
        "operation": "write",
        "content_preview": "127.0.0.1 localhost"
    },
    "description": "Write to system file: /etc/hosts"
}
```

## Configuration

### Policy Configuration

Approval policies are configured in `mega-config.yaml`:

```yaml
policies:
  allow:
    - "git status"      # Automatically allow safe operations
    - "read *.md"       # Allow reading documentation
  deny:
    - "rm -rf /"        # Always block dangerous operations
    - "sudo *"          # Block privilege escalation
```

### Admin Configuration

```yaml
admins:
  - "admin_user_id"
  - "another_admin_id"

system:
  admin_phone: "+1234567890"  # For voice escalation
  dnd_start: 22               # DND start hour (10 PM)
  dnd_end: 7                  # DND end hour (7 AM)
```

## Workflow Examples

### Example 1: Safe Operation (Auto-Approved)
```
User: git status
MegaBot: ✅ Executing: git status
[output shown immediately]
```

### Example 2: Sensitive Operation (Requires Approval)
```
User: rm -rf /tmp/cache
MegaBot: ⚠️ Shell Command Approval Required: rm -rf /tmp/cache
         Type `!approve abc123` to authorize.
Admin: !approve abc123
MegaBot: ✅ Executing approved command: rm -rf /tmp/cache
[command executes]
```

### Example 3: Escalation to Voice
```
User: sudo apt update
MegaBot: ⚠️ Shell Command Approval Required: sudo apt update
         Type `!approve def456` to authorize.
[5 minutes pass without response]
MegaBot: 📞 Escalating to voice call...
[admin phone rings with IVR options]
```

### Example 4: Vision Approval
```
MegaBot generates screenshot with sensitive data
MegaBot: ⚠️ Vision Approval Required: Send image to telegram:chat_123
         Type `!approve ghi789` to authorize.
Admin: !approve ghi789
MegaBot: 📸 Sending approved image...
```

## Security Benefits

### Human Oversight
- Critical decisions require human judgment
- Prevents automated exploitation
- Allows context-aware decision making

### Multi-Channel Redundancy
- Notifications across all platforms
- Voice escalation ensures responsiveness
- DND-aware scheduling

### Audit Trail
- Complete record of all approvals/rejections
- Timestamped decision history
- Action attribution to specific admins

### Configurable Policies
- Fine-grained permission control
- Easy policy updates without code changes
- Environment-specific configurations

## Best Practices

### For Administrators
1. **Review Pending Actions Regularly**: Check for queued approvals frequently
2. **Use Specific Action IDs**: Always use `!approve [id]` instead of `!yes` for clarity
3. **Configure DND Settings**: Set appropriate do-not-disturb hours
4. **Monitor Approval Logs**: Review approval history for security insights

### For System Configuration
1. **Start Conservative**: Use `ASK_EACH` as default for new deployments
2. **Gradually Relax**: Move trusted operations to `AUTO` based on usage patterns
3. **Regular Audits**: Review approval logs quarterly for policy adjustments
4. **Test Escalation**: Verify voice call escalation works in your environment

### For Developers
1. **Clear Descriptions**: Provide meaningful descriptions for approval actions
2. **Action Categorization**: Use appropriate action types for better filtering
3. **Error Handling**: Handle approval rejections gracefully
4. **Testing**: Test approval workflows in development environments

This approval system ensures MegaBot operates securely while providing the flexibility needed for complex AI-assisted workflows.</content>
<parameter name="filePath">docs/security/approvals.md