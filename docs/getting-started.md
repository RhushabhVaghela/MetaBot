# Quick Start Guide

Get MegaBot running in under 5 minutes.

## 🚀 One-Command Setup

```bash
# Clone and run
git clone https://github.com/RhushabhVaghela/MegaBot.git
cd MegaBot
docker-compose up -d --build
```

That's it! MegaBot is now running with default configuration.

## 📋 Prerequisites

- Docker & Docker Compose
- 8GB RAM minimum (16GB recommended)
- NVIDIA GPU (optional, for local LLM acceleration)

## ⚙️ Basic Configuration

### 1. Environment Variables

Create `.env` file:

```bash
# Copy template
cp .env.example .env

# Edit with your tokens
MEGABOT_AUTH_TOKEN=your_secure_token_here
OPENCLAW_AUTH_TOKEN=your_openclaw_token_here

# Optional: Enable specific adapters
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
SIGNAL_PHONE_NUMBER=+1234567890
```

### 2. Adapter Configuration

Edit `mega-config.yaml` with your settings. For a complete configuration reference, see [Configuration Guide](deployment/configuration.md).

**Simplified Example (Development):**

```yaml
# Core system settings
system:
  name: "MegaBot"
  local_only: true
  default_mode: "plan"

# Admin users
admins: ["your_user_id"]

# LLM provider (choose one)
llm:
  anthropic_api_key: "${ANTHROPIC_API_KEY}"
  # openai_api_key: "${OPENAI_API_KEY}"

# Core adapters
adapters:
  openclaw:
    host: "127.0.0.1"
    port: 18789
    auth_token: "${OPENCLAW_AUTH_TOKEN}"
  
  memu:
    host: "127.0.0.1"
    port: 3000
    database_url: "sqlite:///:memory:"
  
  mcp:
    host: "127.0.0.1"
    port: 3000

# Security policies
policies:
  default_permission: "ASK_EACH"
  allow: ["git status", "ls", "pwd"]
  deny: ["rm -rf /", "sudo *"]
```

## 🔧 Available Interfaces

Once running, access MegaBot through:

### Web Dashboard
```
http://localhost:5173
```
React-based interface for full AI interaction.

### REST API
```
http://localhost:8000/health
http://localhost:8000/docs  # OpenAPI documentation
```

### WebSocket
```
ws://localhost:18790?token=your_auth_token
```

### Messaging Platforms
- **Telegram**: Message @YourBot
- **Signal**: Send messages to linked number
- **Discord**: Use bot commands in servers
- **WhatsApp**: Send to configured business number

## 💬 First Interaction

### Via Chat
Send a message to any connected platform:

```
Hello MegaBot! What can you do?
```

MegaBot will respond with capabilities and available commands.

### Via API
```bash
curl -X POST http://localhost:8000/api/v1/messages/send \
  -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "telegram",
    "chat_id": "123456789",
    "content": "Hello from API!"
  }'
```

### Via WebSocket
```javascript
const ws = new WebSocket('ws://localhost:18790?token=your_token');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'message',
    content: 'Hello MegaBot!',
    id: 'msg_1'
  }));
};

ws.onmessage = (event) => {
  const response = JSON.parse(event.data);
  console.log('Bot:', response.content);
};
```

## 🎯 Core Commands

| Command | Description |
|---------|-------------|
| `!help` | Show all available commands |
| `!approve` | Authorize pending actions |
| `!deny` | Reject pending actions |
| `!health` | Check system status |
| `!mode <mode>` | Switch modes (ask/plan/build/loki) |
| `!whoami` | Show your identity info |

## 🔒 Security Setup

### Enable Approval Interlock
```bash
# In chat
!allow ls pwd git status  # Pre-approve safe commands
```

### Check Security Status
```bash
# In chat
!health
```

Response shows all adapters and their status.

## 🧠 Memory & Context

MegaBot remembers context across platforms:

```bash
# Link your identity
!link myname

# Check your identity
!whoami
```

## 🛠️ Development Mode

For development and testing:

```bash
# Run locally
python -m core.orchestrator

# Run tests
pytest

# With coverage
pytest --cov=core --cov-report=html
```

## 📊 Monitoring

### Health Checks
```bash
# System health
curl http://localhost:8000/health

# Detailed status
curl http://localhost:8000/status
```

### Logs
```bash
# View logs
docker-compose logs -f megabot

# Filter by service
docker-compose logs -f megabot postgres
```

## 🔄 Updates

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 🆘 Troubleshooting

### Common Issues

**"Adapter not connecting"**
- Check API tokens in `.env`
- Verify network connectivity
- Check adapter logs: `docker-compose logs adapter_name`

**"Out of memory"**
- Increase Docker memory limit
- Use smaller Ollama model
- Add swap space

**"Permission denied"**
- Fix file permissions: `sudo chown -R 1000:1000 ./data`
- Check volume mounts in docker-compose.yml

### Debug Mode
```bash
# Enable debug logging
docker-compose logs -f megabot | grep DEBUG

# Check container status
docker ps

# Enter container
docker exec -it megabot bash
```

## 📚 Next Steps

- [Full Documentation](../../README.md)
- [API Reference](api/index.md)
- [Configuration Guide](deployment/configuration.md)
- [Development Guide](development/index.md)

---

Happy chatting with MegaBot! 🤖✨