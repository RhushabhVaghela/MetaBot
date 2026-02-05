# MegaBot: API Reference

MegaBot communicates primarily via a high-performance WebSocket API on port `8000`.

## WebSocket Endpoint: `/ws`

### Incoming Messages (Client -> Server)

#### 1. Send Chat Message
Relays a message to OpenClaw and stores it in memU.
```json
{
  "type": "message",
  "content": "What is the weather in Tokyo?"
}
```

#### 2. Set System Mode
Changes the agent's behavior (plan, build, architect, debug).
```json
{
  "type": "set_mode",
  "mode": "build"
}
```

#### 3. Search Memory
Queries the local hierarchical memory.
```json
{
  "type": "search",
  "query": "coding preferences"
}
```

#### 4. Call MCP Tool
Executes a standardized tool from an MCP server.
```json
{
  "type": "mcp_call",
  "server": "filesystem",
  "tool": "read_file",
  "params": { "path": "README.md" }
}
```

### Outgoing Messages (Server -> Client)

#### 1. OpenClaw Event
Relays real-time events from messaging platforms (WhatsApp, Telegram, etc.).
```json
{
  "type": "openclaw_event",
  "payload": { ... }
}
```

#### 2. Search Results
Returns matches from the memory vector database.
```json
{
  "type": "search_results",
  "results": [ ... ]
}
```

#### 3. Mode Updated
Confirms a system mode change.
```json
{
  "type": "mode_updated",
  "mode": "build"
}
```
