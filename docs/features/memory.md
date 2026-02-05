# Memory System Deep-Dive

This document provides an in-depth exploration of MegaBot's memory system, which includes the core memory server, memU adapter, and MCP integration for persistent, intelligent knowledge management.

## Architecture Overview

MegaBot's memory system is a multi-layered architecture designed for persistent cross-session knowledge management:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Memory Server │    │   MemU Adapter  │    │   MCP Server    │
│   (Core)        │◄──►│   (External)    │◄──►│   (Protocol)    │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • Chat History  │    │ • Multi-modal   │    │ • Tool Access   │
│ • User Identity │    │ • Semantic      │    │ • Function      │
│ • Knowledge     │    │ • Vector Search │    │ • Resource Mgmt │
│ • Backups       │    │ • LLM Reasoning│    │ • Context       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
       │                        │                        │
       ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SQLite DB     │    │   Vector DB     │    │   External      │
│   (Metadata)    │    │   (Embeddings)  │    │   Services      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Components

#### Memory Server (`core/memory/mcp_server.py`)

The central memory management system that coordinates all memory operations:

```python
class MemoryServer:
    """
    Persistent cross-session knowledge system for MegaBot.
    Acts as an internal MCP server for memory management.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.chat_memory = ChatMemoryManager(db_path)
        self.user_identity = UserIdentityManager(db_path)
        self.knowledge_memory = KnowledgeMemoryManager(db_path)
        self.backup_manager = MemoryBackupManager(db_path)
```

**Key Features:**
- **Modular Architecture**: Separate managers for different memory types
- **Cross-Session Persistence**: Maintains context across application restarts
- **Backup & Recovery**: Automated backup creation and restoration
- **Identity Management**: Persistent user identity mapping

#### MemU Adapter (`adapters/memu_adapter.py`)

External memory service integration providing advanced semantic capabilities:

```python
class MemUAdapter(MemoryInterface):
    def __init__(self, memu_path: str, db_url: str):
        # Multi-modal storage, semantic search, LLM reasoning
```

**Key Features:**
- **Multi-Modal Storage**: Documents, images, videos, audio, conversations
- **Semantic Search**: Vector-based similarity search
- **LLM-Powered Reasoning**: Intelligent query understanding
- **Proactive Suggestions**: Pattern-based recommendations

## Memory Types and Managers

### Chat Memory Manager

Handles conversation history and context persistence:

```python
class ChatMemoryManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def chat_write(self, chat_id: str, role: str, content: str):
        """Store chat message with metadata."""

    async def chat_read(self, chat_id: str, limit: int = 50) -> List[Dict]:
        """Retrieve recent chat history."""

    async def chat_search(self, query: str, chat_id: Optional[str] = None) -> List[Dict]:
        """Search chat history with semantic matching."""
```

**Database Schema:**
```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    timestamp REAL NOT NULL,
    metadata TEXT, -- JSON metadata
    created_at REAL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_chat_messages_chat_id_timestamp
ON chat_messages(chat_id, timestamp);
```

**Features:**
- **Threaded Conversations**: Support for multiple concurrent chat threads
- **Rich Metadata**: Store message metadata (tokens, model, etc.)
- **Efficient Retrieval**: Indexed queries with pagination
- **Search Capabilities**: Full-text and semantic search

### User Identity Manager

Manages persistent user identity across platforms:

```python
class UserIdentityManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def map_identity(self, platform: str, platform_id: str, megabot_user_id: str):
        """Map platform-specific user ID to MegaBot user ID."""

    async def get_user_id(self, platform: str, platform_id: str) -> Optional[str]:
        """Get MegaBot user ID from platform identity."""
```

**Database Schema:**
```sql
CREATE TABLE user_identities (
    id INTEGER PRIMARY KEY,
    megabot_user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,
    platform_username TEXT,
    metadata TEXT, -- JSON metadata
    created_at REAL DEFAULT (strftime('%s', 'now')),
    updated_at REAL DEFAULT (strftime('%s', 'now')),

    UNIQUE(platform, platform_user_id)
);

CREATE INDEX idx_user_identities_megabot_user
ON user_identities(megabot_user_id);
```

**Features:**
- **Cross-Platform Identity**: Unified user identity across Telegram, Discord, Slack, etc.
- **Privacy Protection**: Encrypted storage of sensitive identity data
- **Identity Resolution**: Automatic identity linking and conflict resolution
- **Audit Trail**: Complete history of identity mappings

### Knowledge Memory Manager

Manages structured knowledge and learned information:

```python
class KnowledgeMemoryManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def store_fact(self, key: str, value: Any, category: str = "general"):
        """Store a piece of knowledge."""

    async def retrieve_fact(self, key: str) -> Optional[Any]:
        """Retrieve stored knowledge."""

    async def search_knowledge(self, query: str, category: Optional[str] = None) -> List[Dict]:
        """Search knowledge base with semantic matching."""
```

**Database Schema:**
```sql
CREATE TABLE knowledge_facts (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    confidence REAL DEFAULT 1.0, -- 0.0 to 1.0
    source TEXT, -- How this knowledge was acquired
    metadata TEXT, -- JSON metadata
    created_at REAL DEFAULT (strftime('%s', 'now')),
    updated_at REAL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE knowledge_relations (
    id INTEGER PRIMARY KEY,
    from_fact_id INTEGER,
    to_fact_id INTEGER,
    relation_type TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    created_at REAL DEFAULT (strftime('%s', 'now')),

    FOREIGN KEY(from_fact_id) REFERENCES knowledge_facts(id),
    FOREIGN KEY(to_fact_id) REFERENCES knowledge_facts(id)
);
```

**Features:**
- **Fact Storage**: Structured storage of learned information
- **Knowledge Graphs**: Relationship mapping between facts
- **Semantic Search**: Vector-based knowledge retrieval
- **Confidence Scoring**: Track reliability of stored information

### Backup Manager

Handles memory system backups and recovery:

```python
class MemoryBackupManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def create_backup(self, backup_path: Optional[str] = None) -> str:
        """Create encrypted backup of memory database."""

    async def restore_backup(self, backup_path: str, target_path: Optional[str] = None):
        """Restore memory from backup."""

    async def list_backups(self) -> List[Dict]:
        """List available backups with metadata."""
```

## MemU Integration

### Multi-Modal Memory Storage

MemU provides advanced memory capabilities beyond the core memory server:

```python
# Multi-modal storage example
await memu_adapter.store("document.pdf", content)
await memu_adapter.store("screenshot.jpg", image_data)
await memu_adapter.store("conversation.log", chat_history)
```

**Supported Modalities:**
- **Documents**: PDF, DOCX, TXT, MD files
- **Images**: JPG, PNG, GIF with OCR and visual understanding
- **Videos**: MP4, MOV with frame analysis and transcription
- **Audio**: MP3, WAV with speech-to-text
- **Conversations**: Chat logs with conversation understanding

### Semantic Search and Retrieval

Advanced search capabilities with multiple retrieval methods:

```python
# Semantic search with different methods
results = await memu_adapter.retrieve(
    query="How to deploy MegaBot to production?",
    method="semantic"  # Vector similarity search
)

# LLM-powered reasoning
insights = await memu_adapter.retrieve(
    query="What are the user's main pain points?",
    method="llm"  # Deep reasoning over memory
)

# Hybrid search
combined = await memu_adapter.retrieve(
    query="Kubernetes deployment issues",
    method="hybrid"  # Combine semantic + keyword search
)
```

### Proactive Memory Features

MemU can provide proactive suggestions based on patterns:

```python
# Get proactive suggestions
suggestions = await memu_adapter.get_proactive_suggestions()

# Anticipate user needs
anticipations = await memu_adapter.get_anticipations()
```

**Proactive Features:**
- **Pattern Recognition**: Identify user behavior patterns
- **Context Awareness**: Understand current user context
- **Predictive Suggestions**: Anticipate user needs
- **Automated Learning**: Learn from interactions to improve suggestions

## Vector Database Integration

### Embedding and Indexing

Memory system uses vector databases for semantic understanding:

```python
# Vector database configuration
vector_config = {
    "provider": "pgvector",  # or "sqlite", "pinecone", "weaviate"
    "connection_url": "postgresql://user:pass@localhost/memu",
    "embedding_model": "text-embedding-ada-002",
    "dimension": 1536
}
```

**Supported Vector Databases:**
- **pgvector**: PostgreSQL extension for vector operations
- **SQLite**: Simple file-based vector storage
- **Pinecone**: Managed vector database service
- **Weaviate**: Open-source vector search engine

### Semantic Search Implementation

Advanced search combining multiple techniques:

```python
class SemanticSearch:
    def __init__(self, vector_db, embedding_model):
        self.vector_db = vector_db
        self.embedding_model = embedding_model

    async def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Perform semantic search over memory."""

        # Generate query embedding
        query_embedding = await self.embedding_model.embed(query)

        # Vector similarity search
        candidates = await self.vector_db.search(query_embedding, top_k * 2)

        # Re-rank with cross-encoders (optional)
        reranked = await self.rerank(query, candidates)

        return reranked[:top_k]

    async def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """Re-rank results using cross-encoder model."""
        # Implementation for better relevance
```

## MCP (Model Context Protocol) Integration

### Memory as MCP Server

The memory system exposes capabilities through MCP:

```python
# MCP server implementation
class MemoryMCPServer:
    def __init__(self, memory_server: MemoryServer):
        self.memory = memory_server

    async def handle_tool_call(self, tool_name: str, args: Dict) -> Any:
        """Handle MCP tool calls for memory operations."""

        if tool_name == "memory_store":
            return await self.memory.knowledge_memory.store_fact(**args)
        elif tool_name == "memory_retrieve":
            return await self.memory.knowledge_memory.retrieve_fact(**args)
        elif tool_name == "memory_search":
            return await self.memory.knowledge_memory.search_knowledge(**args)
```

### Available MCP Tools

**Memory Management Tools:**
- `memory_store`: Store information in knowledge base
- `memory_retrieve`: Retrieve specific information
- `memory_search`: Search knowledge base semantically
- `memory_backup`: Create memory backup
- `memory_restore`: Restore from backup

**Chat History Tools:**
- `chat_history`: Retrieve conversation history
- `chat_search`: Search chat messages
- `chat_summarize`: Generate chat summaries

**Identity Tools:**
- `identity_map`: Map user identities across platforms
- `identity_lookup`: Find user identity information

## Configuration and Deployment

### Memory System Configuration

```yaml
# mega-config.yaml - Memory configuration
adapters:
  memu:
    host: "127.0.0.1"
    port: 3000
    database_url: "postgresql://user:pass@localhost/memu"
    auth_token: "${MEMU_AUTH_TOKEN}"
    vector_db: "pgvector"
    web_search:
      enabled: true
      provider: "duckduckgo"
      max_results: 10

memory:
  db_path: "/var/lib/megabot/memory.db"
  backup_interval_hours: 24
  max_backup_age_days: 30
  enable_compression: true
  enable_encryption: true
```

### Production Deployment

```yaml
# docker-compose.memory.yml
services:
  memu:
    image: memu:latest
    environment:
      - DATABASE_URL=postgresql://memu:password@postgres/memu
      - REDIS_URL=redis://redis:6379
      - LLM_PROVIDER=anthropic
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - memu_data:/app/data
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: memu
      POSTGRES_USER: memu
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    command: ["postgres", "-c", "shared_preload_libraries=vector"]

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
```

## Performance Optimization

### Indexing Strategies

Optimize memory operations with proper indexing:

```sql
-- Performance indexes for memory tables
CREATE INDEX idx_chat_messages_timestamp ON chat_messages(timestamp);
CREATE INDEX idx_chat_messages_role ON chat_messages(role);
CREATE INDEX idx_knowledge_category ON knowledge_facts(category);
CREATE INDEX idx_user_platform ON user_identities(platform, platform_user_id);

-- Vector search indexes
CREATE INDEX idx_memory_embeddings_cosine
ON memory_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Caching Layers

Multi-level caching for performance:

```python
class MemoryCache:
    def __init__(self, redis_client, ttl_seconds: int = 3600):
        self.redis = redis_client
        self.ttl = ttl_seconds

    async def get(self, key: str) -> Optional[Any]:
        """Get cached memory data."""
        cached = await self.redis.get(f"memory:{key}")
        return json.loads(cached) if cached else None

    async def set(self, key: str, value: Any):
        """Cache memory data."""
        await self.redis.setex(
            f"memory:{key}",
            self.ttl,
            json.dumps(value)
        )

    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern."""
        keys = await self.redis.keys(f"memory:{pattern}")
        if keys:
            await self.redis.delete(*keys)
```

### Memory Usage Optimization

Monitor and optimize memory consumption:

```python
class MemoryMonitor:
    def __init__(self, memory_server: MemoryServer):
        self.memory = memory_server
        self.stats = {}

    async def get_usage_stats(self) -> Dict:
        """Get comprehensive memory usage statistics."""
        return {
            "chat_messages": await self._count_table("chat_messages"),
            "knowledge_facts": await self._count_table("knowledge_facts"),
            "user_identities": await self._count_table("user_identities"),
            "db_size_mb": await self._get_db_size(),
            "cache_hit_rate": await self._get_cache_stats()
        }

    async def cleanup_old_data(self, days_old: int = 90):
        """Clean up old memory data."""
        cutoff = time.time() - (days_old * 24 * 60 * 60)

        # Archive old chat messages
        await self.memory.chat_memory.archive_old_messages(cutoff)

        # Clean up old knowledge with low confidence
        await self.memory.knowledge_memory.cleanup_low_confidence(0.3)
```

## Security and Privacy

### Data Encryption

Encrypt sensitive memory data:

```python
class MemoryEncryption:
    def __init__(self, key: bytes):
        self.key = key
        self.cipher = AES.new(key, AES.MODE_GCM)

    async def encrypt_data(self, data: str) -> bytes:
        """Encrypt memory data."""
        nonce = os.urandom(12)
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(data.encode())
        return nonce + tag + ciphertext

    async def decrypt_data(self, encrypted_data: bytes) -> str:
        """Decrypt memory data."""
        nonce = encrypted_data[:12]
        tag = encrypted_data[12:28]
        ciphertext = encrypted_data[28:]

        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode()
```

### Privacy Controls

Implement privacy-preserving memory operations:

```python
class PrivacyManager:
    def __init__(self, memory_server: MemoryServer):
        self.memory = memory_server

    async def sanitize_message(self, message: str, user_id: str) -> str:
        """Remove or anonymize sensitive information."""
        # Remove email addresses
        message = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', message)

        # Remove phone numbers
        message = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', message)

        # Anonymize user mentions
        message = await self._anonymize_user_mentions(message, user_id)

        return message

    async def check_consent(self, user_id: str, data_type: str) -> bool:
        """Check if user has consented to data collection."""
        consent = await self.memory.user_identity.get_consent(user_id, data_type)
        return consent.get("approved", False)
```

## Monitoring and Maintenance

### Health Checks

Comprehensive memory system health monitoring:

```python
class MemoryHealthChecker:
    def __init__(self, memory_server: MemoryServer, memu_adapter):
        self.memory = memory_server
        self.memu = memu_adapter

    async def check_health(self) -> Dict:
        """Perform comprehensive health check."""
        return {
            "database": await self._check_database(),
            "memu_service": await self._check_memu(),
            "vector_search": await self._check_vector_search(),
            "backup_system": await self._check_backups(),
            "performance": await self._check_performance()
        }

    async def _check_database(self) -> Dict:
        """Check database connectivity and integrity."""
        try:
            # Test basic connectivity
            stats = await self.memory.get_usage_stats()

            # Check for corruption
            integrity_check = await self._run_integrity_check()

            return {
                "status": "healthy" if integrity_check else "unhealthy",
                "stats": stats,
                "integrity": integrity_check
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
```

### Automated Maintenance

Scheduled maintenance tasks:

```python
class MemoryMaintenance:
    def __init__(self, memory_server: MemoryServer):
        self.memory = memory_server

    async def run_maintenance(self):
        """Run comprehensive maintenance tasks."""
        await self._optimize_database()
        await self._rebuild_indexes()
        await self._cleanup_old_data()
        await self._update_statistics()

    async def _optimize_database(self):
        """Optimize database performance."""
        # Vacuum database
        # Rebuild indexes
        # Update statistics
        pass

    async def _cleanup_old_data(self):
        """Clean up expired or low-value data."""
        # Remove old chat messages
        # Archive old knowledge
        # Clean up temporary data
        pass
```

## Integration Examples

### Basic Memory Operations

```python
# Initialize memory system
memory = MemoryServer("megabot_memory.db")
memu = MemUAdapter("/path/to/memu", "postgresql://localhost/memu")

# Store conversation
await memory.chat_write("chat_123", "user", "Hello MegaBot!")
await memory.chat_write("chat_123", "assistant", "Hello! How can I help?")

# Store knowledge
await memory.knowledge_memory.store_fact(
    "deployment_guide",
    "MegaBot can be deployed using Docker Compose",
    category="deployment"
)

# Search memories
results = await memu.search("How to deploy MegaBot?")

# Get proactive suggestions
suggestions = await memu.get_proactive_suggestions()
```

### Advanced Memory Features

```python
# Cross-platform identity management
await memory.user_identity.map_identity(
    "telegram", "123456789", "user_abc123"
)
await memory.user_identity.map_identity(
    "discord", "987654321", "user_abc123"
)

# Semantic knowledge search
knowledge = await memory.knowledge_memory.search_knowledge(
    "production deployment strategies",
    category="deployment"
)

# Memory backup and recovery
backup_path = await memory.backup_manager.create_backup()
await memory.backup_manager.restore_backup(backup_path)

# Multi-modal storage with memU
await memu.store("architecture.pdf", None)  # File path
await memu.store("user_feedback", "Users love the new UI", "text")  # Direct content
```

This comprehensive memory system enables MegaBot to maintain context, learn from interactions, and provide increasingly intelligent assistance over time. The combination of structured storage, semantic search, and proactive capabilities creates a powerful foundation for persistent AI interactions.