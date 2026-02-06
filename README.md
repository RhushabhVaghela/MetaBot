# MegaBot: The Ultimate Unified AI Orchestrator 🤖🚀

MegaBot is a production-ready, local-first AI assistant that unifies the world's most powerful agentic frameworks into a single, secure, and modular brain. By combining the execution power of **OpenClaw**, the proactive memory of **memU**, the tool-standardization of **MCP**, and the terminal-centric philosophy of **OpenCode**, MegaBot delivers a future-proof agentic experience.

---

## Table of Contents

- [🚀 Key Features](#-key-features)
- [⌨️ Command Reference](#️-command-reference)
- [🐳 Quick Start](#-quick-start)
- [📚 Documentation](#-documentation)
- [🔧 Architecture](#-architecture)
- [🔒 Security Model](#-security-model)
- [🧪 Testing](#-testing)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## 🚀 Key Features

### 1. Unified Action Engine (via OpenClaw & MCP)
- **Omni-Channel Execution**: Seamlessly communicate across WhatsApp, Telegram, Slack, Discord, iMessage, and SMS.
- **Universal Tooling**: Standardized integration with 1000+ MCP servers (Filesystem, Google Maps, GitHub, etc.).
- **Approval Interlock**: Sensitive system commands are queued for human approval before execution—keeping your host machine safe. You can approve or deny actions directly from your messaging app.

### 2. Neuro-Proactive Memory (via memU)
- **Hierarchical Storage**: Three-layer memory (Resource -> Item -> Category) for long-term context retention and relationship mapping.
- **Layered Fetching**: Fetches data in abstracted layers, allowing the system to handle massive amounts of context without overloading the context window.
- **Intent Prediction**: Anticipates user needs based on historical patterns and current context (Proactive Memory).

### 3. Native Secure Messaging
- **Encrypted WebSocket**: A custom, high-performance channel for mobile and web clients using Fernet (AES-128) encryption.
- **Zero Telemetry**: All data stays on your local machine—no external pings, no cloud tracking.
- **Full Control**: Command your bot, approve/deny actions, and revoke access using simple chat commands (`!approve`, `!deny`, `!allow`, `!mode`).

### 4. Unified Gateway (Cloud Sync)
- **Triple-Layer Access**: Built-in support for **Cloudflare Tunnels** (Public), **Tailscale VPN** (Private Mesh), **Direct HTTPS**, plus localhost fallback.
- **Security First**: Rate limiting, health monitoring, and secure mesh networking via Tailscale ensure your gateway is safe to use.

### 5. Multi-Modal Vision & Safety 👁️🛡️
- **Visual Redaction Agent**: Automatically detects and blurs sensitive regions (API keys, passwords, faces) in outbound screenshots before they reach the admin.
- **Verification Audit**: Uses a secondary vision pass to confirm redaction success. Unsafe images are permanently blocked.
- **Approval Escalation (IVR)**: If a critical approval is ignored for 5 minutes, the bot proactively calls your phone via Twilio (respecting DND hours) to seek authorization via voice.

### 6. Sovereign Identity & Continuity 👤🔄
- **Identity-Link**: Unifies your chat history across Telegram, Signal, WhatsApp, and WebSockets.
- **Context Continuity**: Seamlessly switch from your phone to your desktop while maintaining the same "Working Memory".
- **Self-Healing Heartbeat**: A proactive monitor that detects adapter failures and automatically attempts to restart crashed components.
- **Encrypted Backups**: Automated 12-hour encrypted snapshots of the memory database.

---

## ⌨️ Command Reference

| Command | Description |
|---------|-------------|
| `!approve` / `!yes` | Authorize the last pending sensitive action. |
| `!deny` / `!no` | Reject the last pending action. |
| `!allow <pattern>` | Permanently pre-approve specific commands or patterns. |
| `!link <name>` | Pair your current device with a unified identity. |
| `!whoami` | View your current platform ID and linked unified identity. |
| `!backup` | Manually trigger an encrypted database snapshot. |
| `!briefing` | Request a phone call summarizing recent bot activities. |
| `!health` | Check the status of all system adapters and memory. |
| `!rag_rebuild` | Force a re-scan and cache update of the project codebase. |
| `!history_clean` | Clear current chat history (Architectural lessons are preserved). |
| `!mode <mode>` | Switch between `plan`, `build`, `ask`, and `loki`. |

---

## 🐳 Quick Start

MegaBot is fully containerized and optimized for one-command deployment.

### Prerequisites
- Docker & Docker Compose installed
- At least 8GB RAM (16GB recommended for Ollama with larger models)
- NVIDIA GPU (optional, for Ollama acceleration)

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/RhushabhVaghela/MegaBot
   cd MegaBot
   ```

2. **Configure API Credentials**
   ```bash
   cp api-credentials.py.template api-credentials.py
   # Edit api-credentials.py with your keys and settings
   nano api-credentials.py
   ```

3. **Start services**
   ```bash
   docker-compose up -d --build
   ```

4. **Pull Ollama model** (first time only)
   ```bash
   docker exec -it megabot-ollama ollama pull qwen2.5:14b
   ```

5. **Access MegaBot**
   - API: http://localhost:8000
   - Health: http://localhost:8000/health
   - WebSocket: ws://localhost:18790
   - Search (SearXNG): http://localhost:8080

---

## 📚 Documentation

For comprehensive documentation, visit our [complete documentation index](docs/index.md).

### 📖 Getting Started
- **[Getting Started Guide](docs/getting-started.md)** - Quick start for new users
- **[Installation Guide](docs/deployment/installation.md)** - Complete setup instructions
- **[Configuration](docs/deployment/configuration.md)** - Environment variables and settings

### 🏗️ Architecture
- **[System Overview](docs/architecture/overview.md)** - High-level architecture and components
- **[Adapter Framework](docs/adapters/framework.md)** - Build custom platform integrations

### 🔌 APIs & Integration
- **[REST API Reference](docs/api/index.md)** - Complete API documentation
- **[WebSocket API](docs/api/websocket.md)** - Real-time communication
- **[Webhooks](docs/api/webhooks.md)** - External service integration

### 🛠️ Development
- **[Development Guide](docs/development/index.md)** - Coding standards and contribution guidelines
- **[Testing](docs/development/testing.md)** - Test suite and coverage requirements
- **[CI/CD](docs/development/ci-cd.md)** - Continuous integration and deployment

### 🔒 Security
- **[Security Model](docs/security/model.md)** - Security principles and architecture
- **[Approval Workflows](docs/security/approvals.md)** - Human-in-the-loop security
- **[Best Practices](docs/security/best-practices.md)** - Security recommendations

### 🚀 Advanced Features
- **[Memory System](docs/features/memory.md)** - Persistent memory and context management
- **[RAG System](docs/features/rag.md)** - Retrieval-Augmented Generation
- **[Loki Mode](docs/features/loki.md)** - Autonomous development capabilities

### 📦 Deployment & Operations
- **[Scaling Guide](docs/deployment/scaling.md)** - Production deployment and scaling
- **[Troubleshooting](docs/deployment/troubleshooting.md)** - Common issues and solutions

---

## 🔧 Architecture

### Core Components

```
MegaBot/
├── core/                    # Core business logic
│   ├── orchestrator.py      # Main orchestrator engine
│   ├── config.py           # Configuration management
│   ├── dependencies.py     # Dependency injection
│   ├── interfaces.py       # Core interfaces
│   ├── llm_providers.py    # LLM integration
│   ├── permissions.py      # Security permissions
│   ├── projects.py         # Project management
│   ├── secrets.py          # Secret management
│   └── memory/             # Memory systems
├── adapters/               # Platform integrations
│   ├── messaging/          # Chat platforms
│   ├── gateway/            # Network gateways
│   └── security/           # Security adapters
├── features/               # Feature modules
└── api/                    # REST endpoints
```

### Message Lifecycle

1. **External Platform** → Messaging adapter receives message
2. **Platform Normalization** → Converted to standard `PlatformMessage`
3. **Orchestrator Processing** → Memory lookup and context augmentation
4. **Security Check** → Approval interlock for sensitive actions
5. **Tool Execution** → MCP servers or native tools
6. **Response Generation** → LLM generates response
7. **Platform Delivery** → Response sent back via appropriate adapter

---

## 🔒 Security Model

1. **The Sandbox**: All execution happens inside Docker, isolating your Windows/Linux host.
2. **The Firewall**: MegaBot acts as a proxy for OpenClaw, filtering and intercepting dangerous RCE commands.
3. **The Interlock**: You are the final authority. System-level commands require a physical click to execute.

### Key Security Features
- **Command Sanitization**: All shell commands are validated and sanitized
- **Approval Workflows**: Sensitive operations require explicit human approval
- **Encrypted Communication**: End-to-end encryption for all messaging
- **Visual Redaction**: Automatic detection and blurring of sensitive content
- **Access Control**: Granular permissions and policy enforcement

---

## 🧪 Testing

We maintain rigorous engineering standards with comprehensive test coverage.

### Running Tests
```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=adapters --cov-report=html

# Run specific test suite
pytest tests/test_orchestrator.py
```

### Test Coverage
- **Backend (Python)**: `pytest --cov --cov-report=term-missing`
- **Current**: 840 tests passing across all core modules (**100% coverage**)
- **Components**: Core components, adapters, async testing with proper mocking

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/development/contributing.md) for details.

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Submit a pull request

### Code Standards
- Follow PEP 8 style guidelines
- Add type hints for all functions
- Write comprehensive docstrings
- Include unit tests for new features
- Update documentation as needed

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Maintained by Rhushabh Vaghela. Built for the era of private, agentic intelligence.*
