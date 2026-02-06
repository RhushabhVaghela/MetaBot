## Unreleased

- AGC-001: Pre-flight validation for sub-agent spawn — sub-agents are blocked until validation returns an explicit approval. Prevents accidental execution of dangerous plans.
- AGC-002: Strict permission checks — `permissions.is_authorized(...)` must return the boolean `True` (truthy values are rejected).
- AGC-003: Secure filesystem tools — `read_file` and `write_file` now enforce workspace confinement, deny symlinks, enforce read size limit (1MB), and use atomic writes.
 - AGC-003: Secure filesystem tools — `read_file` and `write_file` now enforce workspace confinement, deny symlinks, enforce read size limit (1MB), and use atomic writes.
 - CI-001: New CI workflow added — runs lint (ruff), type checks (mypy), and the full pytest suite including new TOCTOU and write/read hardening tests.
 - AUD-001: Audit logging — critical AgentCoordinator events now emit to `megabot.audit` (file_read_attempt/file_read_denied/file_write_attempt/file_write_success/tool_execution_denied) with safe payloads.
 - TST-001: New security tests — `tests/test_agent_coordinator_toctou.py` and `tests/test_agent_coordinator_write_edgecases.py` added to cover TOCTOU and write edge-cases. These tests mock OS operations for deterministic behavior.

Changes
- Introduced `core/agent_coordinator.py` hardening: safe spawn flow, secure file ops, synthesis-to-memory with defensive parsing.
- Defensive scheduling in `core/orchestrator_components.py`: initialize task store, defensive start/shutdown wrappers to avoid unawaited coroutine warnings.
- Tests updated to reflect stricter `_active` requirement for MagicMock agents. Test harness warnings fixed by closing prepared coroutines in scheduling-failure test.

Testing
- Full test suite: `pytest -q` — 1369 passed, 0 warnings (local run after changes).
