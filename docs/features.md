# MegaBot: Comprehensive Feature Deep-Dive

MegaBot unifies the best features of leading AI agents into one cohesive system. Below is a detailed breakdown of its primary capabilities.

## 1. Unified Messaging (via OpenClaw)
MegaBot can act as your central messaging hub, allowing you to control AI and system tools via your favorite chat apps.
- **Supported Channels**: WhatsApp, Telegram, Slack, Discord, iMessage, MS Teams.
- **Relay System**: Messages from external platforms are synced in real-time to the MegaBot Dashboard.
- **Context Awareness**: Conversations from any channel are stored in hierarchical memory.

## 2. Proactive Hierarchical Memory (via memU)
MegaBot doesn't just store "chats"; it understands and evolves its knowledge base.
- **Three-Layer Architecture**:
  - **Resource Layer**: Stores raw multimodal data (PDFs, Images, JSON logs).
  - **Item Layer**: Extracts discrete facts, preferences, and relationships.
  - **Category Layer**: Synthesizes items into high-level summaries (e.g., "Work Life", "User Habits").
- **Intent Prediction**: By analyzing historical data, MegaBot can proactively suggest actions or provide relevant context before you ask.

## 3. Tooling & Automation
MegaBot is built for action, not just conversation.
- **Model Context Protocol (MCP)**: Seamlessly connect to standardized tool servers for filesystem management, web search, database access, and more.
- **Sandboxed Execution**: Shell commands and script runs are forced through Docker containers to prevent accidental host damage.
- **Browser Control**: Full automation of Chrome/Chromium via the Chrome DevTools Protocol.

## 4. Operation Modes
MegaBot adapts its behavior based on the active mode:
- **Plan**: Focuses on reasoning, architecture, and drafting without making changes.
- **Build**: Empowered to generate code, write files, and execute system modifications.
- **Debug**: Specialized in trace analysis, log reading, and root-cause identification.
- **Ask**: Optimized for fast, accurate answers and documentation lookup.

## 5. Local Dashboard UI
A premium React-based interface providing:
- **Live Chat**: High-performance real-time chat.
- **Memory Hub**: Visualize categories and browse recent memory items.
- **Integrated Terminal**: Low-latency command execution.
- **Mode Toggle**: Instant switching between operation profiles.

### Tech Stack

| Technology | Version | Role |
|------------|---------|------|
| Vite | 7.2 | Build tool & dev server |
| React | 19.2 | Component framework |
| Tailwind CSS | 4.1 | Utility-first styling |
| TypeScript | 5.9 | Type safety |
| Vitest | 4.0 | Unit & component testing |
| React Testing Library | — | DOM interaction tests |

---

## 6. Feature Modules

The `features/` directory houses specialized capabilities and integrated project documentation.

```
features/
├── dash_data/
│   ├── __init__.py
│   └── agent.py          # DashDataAgent — CSV/JSON analysis with sandboxed Python
├── DASH_README.md
├── TIRITH_README.md
├── MEMU_README.md
├── OPENCLAW_README.md
├── NANOBOT_README.md
├── PAGE_INDEX_README.md
├── AGENT_LIGHTNING_README.md
└── AGENT_ZERO_README.md
```

### DashDataAgent
`features/dash_data/agent.py` provides a sandboxed Python execution environment for deep data analysis on CSV and JSON datasets. It is invoked by the orchestrator when the user requests analytical operations.

### Integrated Project Documentation

| File | Project | Role |
|------|---------|------|
| `DASH_README.md` | Dashboard UI | Frontend architecture & setup |
| `TIRITH_README.md` | TirithGuard | Security & command sanitization |
| `MEMU_README.md` | memU | Hierarchical memory system |
| `OPENCLAW_README.md` | OpenClaw | Messaging relay & execution |
| `NANOBOT_README.md` | NanoBot | Lightweight agent framework |
| `PAGE_INDEX_README.md` | PageIndex | RAG-based codebase navigation |
| `AGENT_LIGHTNING_README.md` | Agent Lightning | Fast-response agent |
| `AGENT_ZERO_README.md` | Agent Zero | Base agent framework |

### Adding a New Feature Module
1. Create a directory under `features/` (e.g., `features/my_module/`).
2. Add an `__init__.py` and your main module file.
3. If integrating an external project, add a `MY_MODULE_README.md` at the `features/` root.
4. Register the module in the orchestrator's feature loader.
