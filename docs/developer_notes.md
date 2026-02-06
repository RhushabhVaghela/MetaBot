Developer Notes
===============

Running tests
- Ensure `PYTHONPATH=.` is set when running pytest. Example:

  PYTHONPATH=. PYTEST_CURRENT_TEST=1 python3 -m pytest -q

- To avoid starting real background services during tests, the test suite respects mocks and some tests set `MEGABOT_SKIP_STARTUP=1`.

Environment
- The orchestrator reads workspace configuration from `orch.config.paths['workspaces']` — set this in tests if you need confined file operations.

Design decisions
- AgentCoordinator introduced stricter `_active` requirements for sub-agents. Tests that construct MagicMock agents must set `mock_agent._active = True` when expecting tool execution.
- Permission checks intentionally require boolean `True` to reduce accidental coast-throughs from truthy placeholder values.

Local verification
- After code or test edits, run the full test suite. The local test run after these changes passed: `1369 passed, 0 warnings`.
