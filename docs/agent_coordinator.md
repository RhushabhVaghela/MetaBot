AgentCoordinator
=================

Purpose
- Central point for spawning and managing sub-agents (SubAgent). Enforces pre-flight validation, permission checks, and secure tool execution on behalf of sub-agents.

Key security behaviors
- Pre-flight validation: before a sub-agent is registered, the orchestrator's LLM is asked to validate the proposed plan. Only an explicit VALID-like response allows registration; otherwise the spawn is blocked.
- Permission checks: `orch.permissions.is_authorized(scope)` must return the boolean `True`. Any other truthy value is treated as denial.
- Filesystem confinement and hardening: `read_file` and `write_file` have been hardened with several defenses:
  - Workspace confinement: paths outside `orch.config.paths['workspaces']` are rejected.
  - Symlink denial: file operations forbid symlinks and use O_NOFOLLOW (where available) to prevent following symlinks.
  - Read limits: configurable READ_LIMIT (default 1MB) is enforced to avoid large content disclosure.
  - Atomic writes: writes use a tempfile + `os.replace` to ensure atomic replace semantics and avoid partial files.
  - TOCTOU mitigations: operations validate file identity after open (fstat checks) and prefer single-shot open flags (O_NOFOLLOW) and file descriptor based operations to reduce TOCTOU windows. Tests are included to cover common TOCTOU edge cases.
  - Defensive error handling: clear audit-safe error messages are returned for permission/file errors and stack traces are not leaked.

Activation policy
- Agent operations (tool execution, file access) require the agent object's `_active` attribute to be True. Mock agents in tests must set `mock_agent._active = True` to simulate active state.

Audit logging (megabot.audit)
- Significant events are emitted to the audit channel `megabot.audit`. Event names and concise payload examples:
  - `file_read_attempt` -> {"agent": "agent-name", "path": "workspaces/foo.txt", "size_limit": 1048576}
  - `file_read_success` -> {"agent": "agent-name", "path": "workspaces/foo.txt", "bytes": 512}
  - `file_read_denied` -> {"agent": "agent-name", "path": "../etc/passwd", "reason": "path_outside_workspace"}
  - `file_write_attempt` -> {"agent": "agent-name", "path": "workspaces/out.txt", "atomic_temp": "..."}
  - `file_write_success` -> {"agent": "agent-name", "path": "workspaces/out.txt", "bytes": 256}
  - `tool_execution_denied` -> {"agent": "agent-name", "tool": "dangerous_tool", "reason": "not_active_or_not_permitted"}

These audit events are lightweight, safe to expose to logging backends, and avoid including file contents.

Usage
- Spawning a sub-agent (delegated from `orchestrator._spawn_sub_agent`) takes an input dict `{name, task, role}`. If validation passes, the SubAgent is created and registered in `orch.sub_agents` with `_coordinator_managed = True` and `_active = True`.

- Executing a tool for a sub-agent (via `AgentCoordinator._execute_tool_for_sub_agent`) enforces:
  1. The agent exists and has `_active` True.
  2. The requested tool is permitted by the agent's declared tools and scope boundaries.
  3. `permissions.is_authorized(scope)` returns boolean `True`.
  4. The corresponding adapter (e.g., `mcp`) implements the tool; otherwise the call returns "logic not implemented".

Errors and responses
- All error conditions return textual messages suitable for debug/logging and are safe to be shown to reviewers; do not leak file contents or internal stack traces.
