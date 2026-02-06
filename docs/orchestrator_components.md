Orchestrator Components
======================

BackgroundTasks
- Responsible for periodic maintenance loops: `sync_loop`, `proactive_loop`, `pruning_loop`, `backup_loop`.
- Defensive scheduling and hardening:
  - `_tasks` initialization: the background task store (`self._tasks`) is always initialized (empty) at construction to avoid None checks and race conditions.
  - Defensive scheduling: `start_all_tasks` schedules each loop with `asyncio.create_task`, falling back to `asyncio.ensure_future` when needed. When scheduling fails or functions are patched, coroutines are explicitly closed to avoid "coroutine was never awaited" warnings.
  - Scheduling checks: before scheduling, the component verifies a task is not already present in `_tasks` and skips duplicate starts.

HealthMonitor
- Periodically collects health data from adapters and maintains `last_status` and `restart_counts`.
- Start/stop fixes: start/stop logic was made defensive so the HealthMonitor registers its task in the orchestrator's `_tasks` store and ensures the task is cancelled and awaited on shutdown to prevent dangling background tasks.

HealthMonitor
- Periodically collects health data from adapters and maintains `last_status` and `restart_counts`.
- Start/stop logic is defensive and stores the task in the orchestrator's background tasks store so shutdown cancels it safely.

MessageHandler
- Routes / processes incoming messages, handles admin commands, attachments, and mode-specific behavior.
