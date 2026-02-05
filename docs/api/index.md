# MegaBot API Reference

Complete REST API documentation for MegaBot's FastAPI endpoints.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health & Status](#health--status)
  - [Messaging](#messaging)
  - [Memory](#memory)
  - [Configuration](#configuration)
  - [Security](#security)
- [WebSocket API](websocket.md)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

## Overview

MegaBot provides a comprehensive REST API built with FastAPI, featuring automatic OpenAPI documentation, type validation, and async support.

**Base URL**: `http://localhost:8000` (configurable)
**API Version**: v1
**Format**: JSON

## Authentication

### API Token Authentication
All API endpoints require authentication via API token.

**Header**: `Authorization: Bearer <token>`

**Environment Variable**: `MEGABOT_AUTH_TOKEN`

### WebSocket Authentication
WebSocket connections require authentication token in the connection URL or initial message.

```
ws://localhost:18790?token=<auth_token>
```

## Endpoints

### Health & Status

#### GET /health
Get system health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600,
  "components": {
    "memory": "up",
    "openclaw": "up",
    "messaging": "up",
    "mcp": "up"
  }
}
```

#### GET /status
Detailed system status including adapter states and resource usage.

**Response:**
```json
{
  "system": {
    "name": "MegaBot",
    "mode": "auto",
    "version": "1.0.0"
  },
  "adapters": {
    "messaging": {
      "status": "up",
      "clients": 3,
      "platforms": ["telegram", "signal", "websocket"]
    },
    "gateway": {
      "status": "up",
      "connections": ["local", "cloudflare"]
    }
  },
  "memory": {
    "total_chats": 15,
    "total_messages": 1247,
    "backup_status": "last_backup_2h_ago"
  }
}
```

### Messaging

#### POST /api/v1/messages/send
Send a message through MegaBot.

**Request:**
```json
{
  "platform": "telegram",
  "chat_id": "123456789",
  "content": "Hello from API",
  "message_type": "text"
}
```

**Parameters:**
- `platform`: Target messaging platform
- `chat_id`: Platform-specific chat identifier
- `content`: Message content
- `message_type`: Message type (text, image, file)

#### GET /api/v1/messages/history/{chat_id}
Retrieve message history for a specific chat.

**Parameters:**
- `chat_id`: Chat identifier
- `limit`: Maximum messages to return (default: 50)
- `offset`: Pagination offset (default: 0)

**Response:**
```json
{
  "chat_id": "123456789",
  "messages": [
    {
      "id": "msg_123",
      "sender": "user",
      "content": "Hello bot",
      "timestamp": "2024-01-01T12:00:00Z",
      "platform": "telegram"
    }
  ],
  "total": 150
}
```

#### POST /api/v1/messages/broadcast
Broadcast message to all active chats.

**Request:**
```json
{
  "content": "System maintenance in 5 minutes",
  "platforms": ["telegram", "signal"],
  "exclude_chats": ["admin_chat_123"]
}
```

### Memory

#### GET /api/v1/memory/stats
Get memory system statistics.

**Response:**
```json
{
  "chats": 25,
  "messages": 3456,
  "learned_lessons": 89,
  "backup_size_mb": 45.2,
  "last_backup": "2024-01-01T06:00:00Z"
}
```

#### POST /api/v1/memory/search
Search through memory content.

**Request:**
```json
{
  "query": "database configuration",
  "type": "learned_lesson",
  "limit": 10
}
```

**Parameters:**
- `query`: Search query
- `type`: Memory type (chat_history, learned_lesson, user_preference)
- `limit`: Maximum results

#### POST /api/v1/memory/backup
Trigger manual memory backup.

**Response:**
```json
{
  "status": "success",
  "backup_path": "/app/backups/memory_20240101_120000.db",
  "size_mb": 45.2
}
```

### Configuration

#### GET /api/v1/config
Get current configuration (admin only).

**Response:**
```json
{
  "system": {
    "name": "MegaBot",
    "mode": "auto",
    "log_level": "INFO"
  },
  "adapters": {
    "telegram": {"enabled": true},
    "signal": {"enabled": true}
  },
  "security": {
    "default_policy": "prompt",
    "allowed_patterns": ["ls", "pwd"]
  }
}
```

#### PUT /api/v1/config
Update configuration (admin only).

**Request:**
```json
{
  "system": {
    "mode": "plan"
  },
  "security": {
    "allowed_patterns": ["ls", "pwd", "git status"]
  }
}
```

### Security

#### GET /api/v1/security/approvals
Get pending approval queue.

**Response:**
```json
{
  "pending": [
    {
      "id": "approval_123",
      "type": "shell_command",
      "action": "rm -rf /tmp/cache",
      "platform": "telegram",
      "requester": "user_456",
      "timestamp": "2024-01-01T12:00:00Z"
    }
  ]
}
```

#### POST /api/v1/security/approve/{approval_id}
Approve a pending action.

**Response:**
```json
{
  "status": "approved",
  "action_id": "approval_123",
  "executed_at": "2024-01-01T12:00:05Z"
}
```

#### POST /api/v1/security/deny/{approval_id}
Deny a pending action.

**Request:**
```json
{
  "reason": "Potentially dangerous command"
}
```

#### GET /api/v1/security/policies
Get current security policies.

**Response:**
```json
{
  "allow": ["ls *", "pwd"],
  "deny": ["rm -rf *", "mkfs*"],
  "default_policy": "prompt"
}
```

#### POST /api/v1/security/policies
Update security policies (admin only).

**Request:**
```json
{
  "allow": ["ls *", "pwd", "git *"],
  "deny": ["rm -rf *", "mkfs*", "dd *"]
}
```

## Error Handling

MegaBot uses standard HTTP status codes and provides detailed error responses.

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "platform",
      "reason": "Must be one of: telegram, signal, discord"
    }
  },
  "request_id": "req_123"
}
```

### Common Error Codes
- `AUTHENTICATION_ERROR`: Invalid or missing API token
- `AUTHORIZATION_ERROR`: Insufficient permissions
- `VALIDATION_ERROR`: Invalid request parameters
- `NOT_FOUND`: Resource not found
- `RATE_LIMITED`: Too many requests
- `INTERNAL_ERROR`: Server error

## Rate Limiting

API endpoints are rate limited to prevent abuse:

- **General endpoints**: 1000 requests/minute
- **Messaging endpoints**: 500 requests/minute
- **Security endpoints**: 100 requests/minute
- **WebSocket connections**: 10 concurrent per IP

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1640995200
```

When rate limited, the API returns HTTP 429 with retry information:
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests",
    "retry_after": 60
  }
}
```