# MegaBot: Security & Privacy Guide

MegaBot is built with a "Privacy First" philosophy. It unifies several powerful AI frameworks while enforcing strict security boundaries to protect your system and data.

## 🛡️ Core Security Principles

### 1. Local-Only Enforcement
MegaBot is configured to be 100% offline-ready by default.
- **Loopback Binding**: The orchestrator strictly binds to `127.0.0.1`. This prevents your instance from being exposed to the public internet, mitigating "Mass Gateway Exposure" risks.
- **Zero Telemetry**: All data collection and external pings are disabled in the core engine.
- **Local AI Providers**: MegaBot is optimized for Ollama, LM Studio, and LocalAI to ensure no prompt data leaves your local network.

### 2. Sandboxed Execution
Dangerous operations (shell commands, script execution, file modifications) are managed via containerized sandboxing.
- **Docker Isolation**: When enabled, MegaBot forces all tool calls into transient Docker containers.
- **Privilege Separation**: The AI agent operates with the minimum necessary permissions within its sandbox, protecting your host filesystem.
- **Native MegaBot Messaging**: Our own WebSocket implementation (port 18790) with end-to-end encryption support, reducing reliance on external gateways.

### 3. Credential Management
MegaBot addresses the "Credential Concentration" risk found in early agentic frameworks.
- **Environment Variables**: Sensitive credentials (auth tokens, API keys) are loaded from environment variables:
  ```bash
  export OPENCLAW_AUTH_TOKEN="your-secure-token"
  export MEGABOT_AUTH_TOKEN="your-secure-token"
  export MEGABOT_WS_PASSWORD="websocket-encryption-key"
  ```
- **Secure Token Generation**: If no token is provided, MegaBot generates a cryptographically secure random token using `secrets.token_urlsafe()`.
- **Template-Based Config**: Personal credentials and API keys can be stored in `meta-config.yaml`, which is excluded from version control via `.gitignore`.
- **Encrypted Storage**: (Planned) Support for local system keychains (macOS Keychain, Windows Credential Manager) for sensitive tokens.

## 🔐 Messaging Bridge Hardening

MegaBot treats external messaging bridges (OpenClaw, WhatsApp, Telegram) as **Untrusted Zones**. We apply a "Zero-Trust" architecture to ensure that even a compromised messaging account cannot take control of your host machine.

### 1. Zero-Trust Architecture
- **Inbound Filtering**: All messages from external platforms are treated as raw data. MegaBot never executes code directly from a message.
- **Protocol Isolation**: The connection to OpenClaw is isolated. MegaBot only communicates via a restricted set of JSON-RPC methods (`chat.send`, `gateway.subscribe`).
- **Cryptographic Handshake**: Connections between MegaBot and its adapters require a secure `OPENCLAW_AUTH_TOKEN`. If the token doesn't match, the bridge is immediately dropped.

### 2. Human-in-the-Loop (HitL) Approval
The **Approval Interlock** is your primary defense against RCE (Remote Code Execution) attacks.
- **Default Deny**: Any command involving shell access, filesystem modification, or system configuration is blocked by default.
- **Messaging-Based Approval**: You can approve pending actions directly from your messaging app using `!approve <id>`.
- **Persistent Policies**: Use `!allow <pattern>` to automate trust for safe commands. These are saved to `meta-config.yaml` and verified on every execution.

### 3. Layered Gateway Security
When accessing MegaBot remotely, we provide three layers of protection:
- **Layer 1: Cloudflare Tunnel**: Hides your home IP address and provides DDoS protection.
- **Layer 2: Tailscale VPN**: Creates a private, encrypted mesh network. The MegaBot API is not even visible to the public internet; it is only accessible to devices on your private Tailscale network.
- **Layer 3: End-to-End Encryption**: All WebSocket traffic is encrypted with AES-128 before it even leaves the MegaBot process.

### 4. Policy Persistence & Wildcards
MegaBot supports persistent policy management via chat commands:
- `!allow *`: **⚠️ DANGEROUS**. Auto-approves every single command. MegaBot will log a security warning to the console every time this policy is invoked.
- `!deny *`: The "Lockdown" mode. Blocks all system commands, regardless of other rules.

---

## 🔒 Privacy Controls

### 1. Memory Isolation
The **memU** adapter uses a local SQLite database for hierarchical memory.
- **Data Residence**: Your long-term context, preferences, and knowledge stay on your physical disk.
- **No Cloud Sync**: MegaBot does not sync your memory to any 3rd party cloud providers.

### 2. Network Isolation (Docker)
When running via `docker-compose`, MegaBot creates an internal bridge network.
- The UI and Backend communicate privately.
- Only required ports (`8000`, `5173`, `18790`) are exposed to your local machine.

### 3. OpenClaw Integration - Data Sharing Notice

⚠️ **IMPORTANT**: When using OpenClaw Gateway for messaging platforms (WhatsApp, Telegram, Discord, etc.):

**Data Flow**:
1. Your messages are sent from MegaBot → OpenClaw Gateway (localhost:18789 via WebSocket)
2. OpenClaw Gateway processes and forwards to external platform APIs (WhatsApp Web, Telegram Bot API, etc.)
3. Platform APIs then deliver to recipients

**Safety Verification: The Approval Interlock**
To protect your host machine from malicious or accidental commands, MegaBot implements an **Interlock System**:
- **Intercept**: Every `system.run` or `shell` command is caught by the MegaBot Orchestrator.
- **Queue**: The command is moved to a `Pending Approval` queue and blocked from executing.
- **Decision**: You must manually click **"Approve"** in the MegaBot UI or via a trusted WebSocket message to release the block.
- **Policies**: You can define `allow` and `deny` patterns in `meta-config.yaml` to permanently automate approvals or rejections for specific commands (e.g., auto-allow `git status`, auto-deny `rm -rf`).
- **Sandbox**: Even when approved, the command runs inside the Docker container unless explicitly bridged to the host via an MCP Node.

### 4. Policy-Based Automation
MegaBot allows you to automate trust via a declarative policy system. This prevents "approval fatigue" for common, safe commands.

**Example Configuration**:
```yaml
policies:
  allow:
    - "git status"
    - "ls"
    - "dir"
    # - "*" # ⚠️ DANGEROUS: Use this to auto-approve ALL commands
  deny:
    - "rm -rf"
    - "format"
    - "shutdown"
    # - "*" # Use this to block ALL system commands by default
```
*   **Allow List**: Any command containing these strings will execute without asking.
*   **Deny List**: Any command containing these strings will be immediately discarded.
*   **Global Wildcard (`*`)**: If you put `"*"` in a list, it acts as a "match all" flag. Putting `"*"` in the `allow` list effectively disables the approval interlock (not recommended for production).
*   **Ask (Default)**: Anything else will be queued for manual approval.

**Known Security Considerations**:
- **OpenClaw Telemetry**: OpenClaw may collect usage data (see [Reddit discussion](https://www.reddit.com/r/privacy/comments/1qrtpse/openclaw_telemetry/))
- **Gateway Exposure Risk**: Misconfigured OpenClaw instances have been exposed to the public internet ("Mass Gateway Exposure")
- **Malicious Skills**: OpenClaw's skill marketplace has had malicious packages (e.g., crypto-stealing "moltbot" skill)
- **Credential Risk**: OpenClaw stores platform credentials (WhatsApp session, Telegram tokens) locally

**Mitigation Strategies**:
- Use MegaBot's native messaging server (port 18790) when possible
- Enable the **Interlock**: Keep MegaBot in `plan` or `ask` mode for high-risk sessions.
- Enable encryption: Set `MEGABOT_WS_PASSWORD` environment variable
- Audit all skills before installation
- Keep OpenClaw Gateway bound to localhost only
- Regularly rotate auth tokens

### 4. End-to-End Encryption

MegaBot's native WebSocket implementation supports optional end-to-end encryption:
- Uses Fernet symmetric encryption (AES-128 in CBC mode with PKCS7 padding)
- Keys derived using PBKDF2HMAC with 100,000 iterations
- All messages encrypted before transmission over WebSocket
- Media files encrypted at rest in local storage

**To enable encryption**:
```bash
export MEGABOT_WS_PASSWORD="your-strong-password"
```

## 🔐 Multi-Platform Messaging Architecture

### Option 1: Native MegaBot Messaging (Recommended for Privacy)
- **Protocol**: Custom WebSocket with encryption
- **Port**: 18790
- **Data Sharing**: None - all data stays local
- **Multimedia Support**: Full (images, video, audio, documents)
- **Platforms**: Custom clients, web interface, mobile apps

### Option 2: OpenClaw Gateway (For Platform Integration)
- **Protocol**: WebSocket to OpenClaw → Platform APIs
- **Port**: 18789
- **Data Sharing**: Messages routed through OpenClaw and platform APIs
- **Multimedia Support**: Depends on platform (WhatsApp, Telegram, etc.)
- **Platforms**: WhatsApp, Telegram, Discord, Slack, iMessage

**Recommendation**: Use Option 1 for sensitive communications. Use Option 2 only when necessary for external platform integration, and be aware of data sharing implications.

## 📊 Data Residency Comparison

| Component | Storage Location | Encrypted | Cloud Sync |
|-----------|-----------------|-----------|------------|
| MegaBot Native Messaging | Local disk | ✅ Yes | ❌ No |
| OpenClaw Gateway | Local + Platform APIs | ⚠️ Partial | ⚠️ Via platforms |
| memU Memory | Local SQLite/pgvector | ❌ No | ❌ No |
| MCP Tools | Local execution | N/A | ❌ No |
| Config Files | Local filesystem | ❌ No | ❌ No |

## 🛠️ Security Hardening Checklist

For production-ready local deployments, follow these steps:

### Critical (Do First)
- [ ] Set strong `MEGABOT_AUTH_TOKEN` and `MEGABOT_WS_PASSWORD` environment variables
- [ ] Ensure `meta-config.yaml` has `local_only: true`
- [ ] Bind all services to `127.0.0.1` (localhost) only
- [ ] Enable encryption: `enable_encryption: true` in messaging config
- [ ] Review and audit any MCP servers before installation

### Important
- [ ] Only install vetted skills via the **Module Discovery** system
- [ ] Keep your local LLM provider (e.g., Ollama) updated to the latest version
- [ ] Regularly audit the `megabot.db` (local SQLite) to manage your stored context
- [ ] Enable Docker sandboxing for all tool execution
- [ ] Rotate auth tokens monthly

### Advanced
- [ ] Set up firewall rules to block external access to ports 18789-18790
- [ ] Use separate authentication tokens for each platform adapter
- [ ] Enable media file encryption at rest
- [ ] Implement message retention policies (auto-delete after N days)
- [ ] Set up log rotation and monitoring

## 🚨 Privacy Policies Clarification

**memU Bot** is a local AI assistant that MegaBot integrates for memory management.

**memU Bot**:
- Claims fully local operation
- Uses local PostgreSQL + VectorDB
- No official Docker support
- Privacy policy: Available at https://memu.bot/privacy

**OpenClaw Privacy**:
- Telemetry concerns raised by community
- Data shared with platform APIs (WhatsApp, Telegram, etc.)
- Privacy policy: https://openclaw.ai/privacy

## 🔍 Transparency: What Data Leaves Your Machine

### With Native MegaBot Messaging:
- ✅ **Nothing** - all data stays on your local machine
- ✅ Messages stored locally in SQLite
- ✅ Media files stored in `./media` directory
- ✅ No external API calls (unless using web search feature)

### With OpenClaw Integration:
- ⚠️ **Messages** → Sent to OpenClaw Gateway (localhost) → Platform APIs
- ⚠️ **Media** → Uploaded to platform servers (WhatsApp, Telegram, etc.)
- ⚠️ **Metadata** → May be logged by OpenClaw and platforms
- ⚠️ **Telemetry** → OpenClaw may collect usage analytics

### With Web Search (Optional):
- ⚠️ **Search queries** → Sent to configured search provider (SearXNG, Perplexity, etc.)
- ⚠️ **Results** → Retrieved from external APIs

## 🚨 Vulnerability Reporting

If you discover a security issue, please report it via the GitHub Issues tab using the `Security` label.

For critical vulnerabilities, please email: security@megabot.local
