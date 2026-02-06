AgentCoordinator
=================

Purpose
- Central point for spawning and managing sub-agents (SubAgent). Enforces pre-flight validation, permission checks, and secure tool execution on behalf of sub-agents.

Key security behaviors
- Pre-flight validation: before a sub-agent is registered, the orchestrator's LLM is asked to validate the proposed plan. Only an explicit VALID-like response allows registration; otherwise the spawn is blocked.
- Permission checks: `orch.permissions.is_authorized(scope)` must return the boolean `True`. Any other truthy value is treated as denial.
- Filesystem confinement: `read_file` and `write_file` operate under workspace confinement:
  - Paths outside `orch.config.paths['workspaces']` are rejected.
  - Symlinks are denied.
  - Reads have a size limit (1MB by default).
  - Writes are atomic (tempfile + `os.replace`).

Usage
- Spawning a sub-agent (delegated from `orchestrator._spawn_sub_agent`) takes an input dict `{name, task, role}`. If validation passes, the SubAgent is created and registered in `orch.sub_agents` with `_coordinator_managed = True` and `_active = True`.

- Executing a tool for a sub-agent (via `AgentCoordinator._execute_tool_for_sub_agent`) enforces:
  1. The agent exists and has `_active` True.
  2. The requested tool is permitted by the agent's declared tools and scope boundaries.
  3. `permissions.is_authorized(scope)` returns boolean `True`.
  4. The corresponding adapter (e.g., `mcp`) implements the tool; otherwise the call returns "logic not implemented".

Errors and responses
- All error conditions return textual messages suitable for debug/logging and are safe to be shown to reviewers; do not leak file contents or internal stack traces.
