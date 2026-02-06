Developer Notes
===============

Running tests
- Ensure `PYTHONPATH=.` is set when running pytest. Example:

  PYTHONPATH=. PYTEST_CURRENT_TEST=1 python3 -m pytest -q

- To avoid starting real background services during tests, the test suite respects mocks and some tests set `MEGABOT_SKIP_STARTUP=1`.

Local test helpers and fixtures
- New test fixture: `active_mock_agent` is available in tests to provide a MagicMock-like agent with `_active = True` and reasonable defaults for permissions and tool lists. Use this fixture in tests when you need a coordinator-managed, active agent.

Running focused checks
- Run a single test module or file:

  PYTHONPATH=. pytest tests/test_agent_coordinator_write_edgecases.py -q

- Run a focused test by node id (single test):

  PYTHONPATH=. pytest tests/test_agent_coordinator_toctou.py::test_open_no_follow -q

Reproducing full test suite
- Reproduce CI/test run locally (runs ruff, mypy, and pytest):

  # From repo root
  PYTHONPATH=. ./scripts/ci_check.sh

Deterministic TOCTOU tests guidance
- Prefer mocking OS operations (open, os.open, os.replace, os.fstat) and file descriptors to simulate races deterministically rather than relying on timing-based sleeps. The new TOCTOU tests use monkeypatch/patch to control behavior and assert that fstat checks and O_NOFOLLOW usage prevent unsafe outcomes.

Other local verification
- After code or test edits, run the full test suite. Example shown in CI logs; local runs may vary depending on environment and optional network-related tests.

Environment
- The orchestrator reads workspace configuration from `orch.config.paths['workspaces']` — set this in tests if you need confined file operations.

Design decisions
- AgentCoordinator introduced stricter `_active` requirements for sub-agents. Tests that construct MagicMock agents must set `mock_agent._active = True` when expecting tool execution.
- Permission checks intentionally require boolean `True` to reduce accidental coast-throughs from truthy placeholder values.

Local verification
- After code or test edits, run the full test suite. The local test run after these changes passed: `1369 passed, 0 warnings`.
