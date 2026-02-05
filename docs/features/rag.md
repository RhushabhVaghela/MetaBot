# RAG (Retrieval-Augmented Generation) System

This document explores MegaBot's Retrieval-Augmented Generation system, which provides intelligent codebase understanding and context-aware assistance through structural indexing and LLM-guided navigation.

## RAG Architecture Overview

MegaBot's RAG system takes a unique approach compared to traditional vector-based RAG implementations:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Structural    │    │   Hierarchical  │    │   LLM-Guided    │
│   Indexing      │───►│   Navigation    │───►│   Reasoning     │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • File Analysis │    │ • Index Traversal│    │ • Query         │
│ • Symbol Extract│    │ • Path Resolution│    │ • Understanding │
│ • Content Summ. │    │ • Context Loading│    │ • Response Gen. │
└─────────────────┘    └─────────────────┘    └─────────────────┘
       │                        │                        │
       ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   JSON Index    │    │   File Context  │    │   Intelligent   │
│   Cache         │    │   Retrieval     │    │   Responses     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Differences from Vector RAG

**Traditional Vector RAG:**
- Converts documents to embeddings
- Performs vector similarity search
- Returns relevant chunks based on semantic similarity

**MegaBot Structural RAG:**
- Creates hierarchical file/folder structure index
- Uses LLM reasoning to navigate the index
- Retrieves complete file contexts based on structural understanding

## Core Components

### PageIndexRAG Class

The main RAG implementation that provides codebase-aware assistance:

```python
class PageIndexRAG:
    """
    Structural, Vectorless RAG system.
    Instead of vector similarity, it uses a hierarchical index (Page Index)
    and LLM-guided navigation to reason over a codebase.
    """

    def __init__(self, root_dir: str, llm: Optional[Any] = None):
        self.root_dir = root_dir
        self.llm = llm
        self.index: Dict[str, Any] = {}
        self.index_path = os.path.join(root_dir, ".megabot_index.json")
```

**Key Methods:**
- `build_index()`: Creates hierarchical codebase map
- `navigate()`: Main query interface with reasoning
- `get_file_context()`: Retrieves specific file content

### Index Structure

The RAG system builds a hierarchical JSON index of the codebase:

```json
{
  "root": "/path/to/project",
  "files": {
    "README.md": {
      "size": 2048,
      "headers": ["# MegaBot", "## Features", "## Installation"],
      "summary": "MegaBot is a unified AI orchestrator..."
    }
  },
  "folders": {
    "core": {
      "files": {
        "orchestrator.py": {
          "size": 15432,
          "headers": ["class MegaBot", "def __init__", "async def run"],
          "summary": "Main orchestrator class handling..."
        }
      },
      "folders": {
        "memory": {
          "files": {...},
          "folders": {...}
        }
      }
    }
  }
}
```

## Index Building Process

### File Analysis Pipeline

The system analyzes codebase files through a multi-stage process:

```python
async def build_index(self, force_rebuild: bool = False):
    """Creates a hierarchical map of the codebase with summaries."""

    # 1. Check for cached index
    if not force_rebuild and os.path.exists(self.index_path):
        self.index = json.load(open(self.index_path))
        return

    # 2. Build fresh index
    self.index = {"root": self.root_dir, "files": {}, "folders": {}}

    # 3. Walk directory structure
    self._walk_and_index(self.root_dir, self.index)

    # 4. Cache the index
    json.dump(self.index, open(self.index_path, "w"))
```

### Symbol Extraction

Extracts meaningful symbols and structure from different file types:

```python
def _extract_symbols(self, content: str, filename: str) -> List[str]:
    """Extract key symbols based on file type."""

    if filename.endswith(".py"):
        # Python: classes and functions
        return re.findall(
            r"^(?:class|def)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            content,
            re.MULTILINE
        )

    elif filename.endswith((".js", ".ts")):
        # JavaScript/TypeScript: classes, functions, constants
        return re.findall(
            r"^(?:class|function|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            content,
            re.MULTILINE,
        )

    elif filename.endswith(".md"):
        # Markdown: headers
        return re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)

    return []
```

### Content Summarization

Generates quick summaries for efficient indexing:

```python
def _generate_quick_summary(self, content: str) -> str:
    """Create a concise summary from file content."""

    # Extract first few non-empty lines
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    # Combine and truncate
    summary = " ".join(lines[:3])[:200]

    return summary + "..." if len(summary) == 200 else summary
```

## Query Processing

### Dual Navigation Modes

The system supports two query processing approaches:

#### 1. LLM-Guided Navigation (Primary)

Uses the LLM to intelligently navigate the structural index:

```python
async def _reasoned_navigation(self, query: str) -> str:
    """Uses LLM to navigate the structural index."""

    # Create collapsed index for context
    index_str = json.dumps(self._get_collapsed_index(), indent=2)

    # Build reasoning prompt
    prompt = f"""
    You are a Structural Navigation Agent.
    Given the following high-level 'Page Index' of a codebase,
    identify the 3 most relevant files to answer the user query.

    QUERY: {query}
    INDEX:
    {index_str}

    Return a JSON list of relative file paths.
    """

    # Get LLM response
    response = await self.llm.generate(
        context="PageIndex Reasoning",
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract file paths and retrieve content
    paths = re.findall(r'["\']([^"\']+\.[a-z0-9]+)["\']', str(response))

    results = []
    for path in paths:
        content = await self.get_file_context(path)
        results.append(f"--- {path} ---\n{content}")

    return "\n\n".join(results)
```

#### 2. Keyword Navigation (Fallback)

Simple structural keyword search when LLM is unavailable:

```python
def _keyword_navigation(self, query: str) -> str:
    """Fallback keyword-based search."""

    results = []
    query_lower = query.lower()

    def search_dict(index_dict, path=""):
        # Search files
        for filename, info in index_dict.get("files", {}).items():
            file_path = os.path.join(path, filename)

            # Check filename, summary, and symbols
            if (query_lower in file_path.lower() or
                query_lower in info["summary"].lower() or
                any(query_lower in symbol.lower() for symbol in info["headers"])):

                results.append(
                    f"File: {file_path}\n"
                    f"  Summary: {info['summary']}\n"
                    f"  Symbols: {info['headers'][:5]}"
                )

        # Recursively search folders
        for folder_name, sub_dict in index_dict.get("folders", {}).items():
            search_dict(sub_dict, os.path.join(path, folder_name))

    search_dict(self.index)
    return "\n\n".join(results[:5]) if results else "No matching files found."
```

## Index Optimization

### Collapsed Index for LLM Context

Creates simplified index representations to fit within LLM context windows:

```python
def _get_collapsed_index(self, max_depth=2) -> Dict:
    """Returns a simplified version of the index for LLM context."""

    def collapse(index_dict, depth):
        if depth > max_depth:
            return {"note": "Max depth reached"}

        return {
            "files": list(index_dict["files"].keys()),
            "folders": {
                folder_name: collapse(sub_dict, depth + 1)
                for folder_name, sub_dict in index_dict["folders"].items()
            },
        }

    return collapse(self.index, 0)
```

### Caching Strategy

Implements intelligent caching to minimize rebuild overhead:

```python
# Index persistence
self.index_path = os.path.join(root_dir, ".megabot_index.json")

# Cache validation
if not force_rebuild and os.path.exists(self.index_path):
    try:
        with open(self.index_path, "r") as f:
            self.index = json.load(f)
        print(f"RAG: Loading cached index from {self.index_path}...")
        return
    except Exception as e:
        print(f"RAG: Failed to load cache: {e}")

# Force rebuild logic
print(f"RAG: Building structural index for {self.root_dir}...")
# ... build process ...

# Cache saving
try:
    with open(self.index_path, "w") as f:
        json.dump(self.index, f)
    print(f"RAG: Index cached to {self.index_path}")
except Exception as e:
    print(f"RAG: Failed to save cache: {e}")
```

## Integration with MegaBot

### Orchestrator Integration

The RAG system integrates deeply with the main orchestrator:

```python
class MegaBot:
    def __init__(self, config):
        # Initialize RAG system
        self.rag = PageIndexRAG(
            root_dir=os.getcwd(),
            llm=self.llm_provider
        )

    async def initialize(self):
        """Initialize all systems including RAG."""
        # Build RAG index
        try:
            await self.rag.build_index()
            print(f"Project RAG index built for: {self.rag.root_dir}")
        except Exception as e:
            print(f"Failed to build RAG index: {e}")

    # Admin commands
    async def handle_admin_command(self, command: str):
        if command == "!rag_rebuild":
            await self.rag.build_index(force_rebuild=True)
            return "🏗️ RAG Index rebuilt and cached."
```

### Tool Integration

RAG provides tools for autonomous operation:

```python
# Available RAG tools
rag_tools = [
    {
        "name": "query_project_rag",
        "description": "Query the project codebase using RAG",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The question or topic to search for in the codebase"
                }
            },
            "required": ["query"]
        }
    }
]

# Tool execution
elif tool_name == "query_project_rag":
    query = tool_input.get("query", "")
    result = await self.rag.navigate(query)
    return f"Project RAG Results:\n{result}"

elif tool_name == "query_rag":
    return await self.rag.navigate(str(tool_input.get("query", "")))
```

## Performance Characteristics

### Index Size and Build Time

Performance metrics for typical projects:

```python
# Index statistics tracking
class RAGMetrics:
    def __init__(self):
        self.index_sizes = []
        self.build_times = []
        self.query_times = []

    def track_build(self, index_size: int, build_time: float):
        """Track index building performance."""
        self.index_sizes.append(index_size)
        self.build_times.append(build_time)

    def track_query(self, query_time: float):
        """Track query performance."""
        self.query_times.append(query_time)

# Performance benchmarks
# - Small project (< 100 files): < 5 seconds build, < 1KB index
# - Medium project (100-1000 files): < 30 seconds build, < 100KB index
# - Large project (> 1000 files): < 120 seconds build, < 1MB index
```

### Query Performance

Query response times vary by mode:

```python
# Performance characteristics
query_performance = {
    "llm_guided": {
        "avg_response_time": "3-8 seconds",
        "context_usage": "high",
        "accuracy": "very high",
        "cost": "medium"
    },
    "keyword_fallback": {
        "avg_response_time": "< 0.1 seconds",
        "context_usage": "none",
        "accuracy": "medium",
        "cost": "low"
    }
}
```

## Configuration and Tuning

### RAG System Configuration

```yaml
# mega-config.yaml - RAG configuration
rag:
  enabled: true
  index_cache_enabled: true
  index_max_age_hours: 24
  llm_guided_navigation: true
  max_query_results: 5
  context_window_size: 100  # lines per file
  supported_extensions:
    - ".py"
    - ".js"
    - ".ts"
    - ".md"
    - ".txt"
    - ".yaml"
    - ".yml"
    - ".json"
  excluded_dirs:
    - "node_modules"
    - "__pycache__"
    - ".git"
    - "venv"
    - ".venv"
```

### Advanced Tuning

Fine-tune RAG behavior for specific use cases:

```python
# Advanced RAG configuration
advanced_rag_config = {
    "index_depth": 3,  # Maximum folder depth to index
    "file_size_limit": 1024000,  # 1MB max file size
    "summary_length": 200,  # Characters per file summary
    "symbol_limit": 10,  # Max symbols to extract per file
    "llm_temperature": 0.1,  # Lower for more deterministic navigation
    "cache_compression": True,  # Compress cached index
    "parallel_processing": True,  # Process files in parallel
    "memory_efficient": False,  # Trade speed for memory usage
}
```

## Use Cases and Examples

### Code Understanding

Help developers understand complex codebases:

```python
# Example queries
queries = [
    "How does the authentication system work?",
    "Where is the database connection logic?",
    "What are the main API endpoints?",
    "How do I add a new feature?",
    "What testing utilities are available?"
]

# RAG responses provide contextual code snippets
# with file locations and structural understanding
```

### Documentation Generation

Automatically generate documentation from code:

```python
# Documentation generation
async def generate_api_docs():
    """Generate API documentation using RAG."""

    # Query for API endpoints
    api_files = await rag.navigate("API endpoints and routes")

    # Query for data models
    models = await rag.navigate("data models and schemas")

    # Query for authentication
    auth = await rag.navigate("authentication and authorization")

    # Combine into comprehensive documentation
    return f"""
# API Documentation

## Endpoints
{api_files}

## Data Models
{models}

## Authentication
{auth}
"""
```

### Code Review Assistance

Help with code reviews by providing context:

```python
# Code review support
async def analyze_changes(changed_files):
    """Analyze code changes using RAG context."""

    analysis = []
    for file_path in changed_files:
        # Get file context
        context = await rag.get_file_context(file_path)

        # Query related functionality
        related = await rag.navigate(
            f"What functionality depends on {file_path}?"
        )

        analysis.append({
            "file": file_path,
            "context": context,
            "dependencies": related
        })

    return analysis
```

## Monitoring and Maintenance

### Index Health Monitoring

Monitor RAG system health and performance:

```python
class RAGMonitor:
    def __init__(self, rag_system: PageIndexRAG):
        self.rag = rag_system

    async def health_check(self) -> Dict:
        """Perform comprehensive RAG health check."""

        return {
            "index_exists": os.path.exists(self.rag.index_path),
            "index_size": os.path.getsize(self.rag.index_path) if os.path.exists(self.rag.index_path) else 0,
            "index_age": self._get_index_age(),
            "llm_available": self.rag.llm is not None,
            "root_dir_exists": os.path.exists(self.rag.root_dir),
            "file_count": self._count_indexed_files(),
        }

    def _get_index_age(self) -> float:
        """Get age of index in hours."""
        if not os.path.exists(self.rag.index_path):
            return float('inf')

        mtime = os.path.getmtime(self.rag.index_path)
        age_seconds = time.time() - mtime
        return age_seconds / 3600

    def _count_indexed_files(self) -> int:
        """Count total files in index."""
        def count_files(index_dict):
            count = len(index_dict.get("files", {}))
            for folder in index_dict.get("folders", {}).values():
                count += count_files(folder)
            return count

        return count_files(self.rag.index)
```

### Automated Index Maintenance

Keep the RAG index current with codebase changes:

```python
class RAGMaintenance:
    def __init__(self, rag_system: PageIndexRAG):
        self.rag = rag_system
        self.last_build = 0

    async def scheduled_rebuild(self):
        """Rebuild index on schedule or when needed."""

        current_time = time.time()

        # Rebuild if index is stale (>24 hours)
        if current_time - self.last_build > 24 * 3600:
            print("RAG: Scheduled index rebuild...")
            await self.rag.build_index(force_rebuild=True)
            self.last_build = current_time

    async def incremental_update(self, changed_files: List[str]):
        """Update index for specific file changes."""

        # For now, trigger full rebuild
        # Future: implement incremental indexing
        await self.rag.build_index(force_rebuild=True)
```

## Comparison with Other RAG Approaches

### Vs. Vector-Based RAG

```python
comparison = {
    "structural_rag": {
        "pros": [
            "No embedding costs",
            "Exact code structure understanding",
            "LLM-guided navigation",
            "Lightweight and fast",
            "No vector database required"
        ],
        "cons": [
            "Limited to codebase structure",
            "Requires LLM for reasoning",
            "No semantic similarity search",
            "File-based granularity only"
        ]
    },
    "vector_rag": {
        "pros": [
            "Semantic understanding",
            "Cross-document relationships",
            "Flexible chunking strategies",
            "Works with any content type"
        ],
        "cons": [
            "High computational cost",
            "Requires vector database",
            "Chunking complexity",
            "Embedding model dependency"
        ]
    }
}
```

### Best Use Cases

**Structural RAG (MegaBot):**
- Codebase understanding and navigation
- Developer assistance and onboarding
- Documentation generation from code
- Code review support
- API discovery and exploration

**Vector RAG:**
- General document Q&A
- Knowledge base search
- Content recommendation
- Multi-modal content understanding

## Future Enhancements

### Planned Improvements

1. **Incremental Indexing**: Update index for changed files only
2. **Multi-Language Support**: Enhanced symbol extraction for more languages
3. **Dependency Analysis**: Track code dependencies and relationships
4. **Semantic Hybrid Mode**: Combine structural and vector approaches
5. **Collaborative Features**: Multi-user index sharing and merging
6. **Performance Optimization**: Parallel processing and memory optimization
7. **Advanced Querying**: Natural language to code query translation

This RAG system provides MegaBot with deep codebase understanding, enabling intelligent assistance and autonomous operation through structural awareness and LLM-guided reasoning.