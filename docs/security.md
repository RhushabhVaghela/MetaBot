Audit Logging and File-Tool Hardening
-----------------------------------

Summary
- The orchestrator and AgentCoordinator emit structured JSON audit events to
  the logger `megabot.audit`. This helps with forensic analysis and tracking
  sensitive tool usage (file reads/writes, denied actions, TOCTOU detections).

How to enable audit logging
- Opt-in: set environment variable `MEGABOT_ENABLE_AUDIT_LOG=1` to force
  writing audit logs to disk at the path defined in `config.paths.audit_log`
  (defaults to `logs/audit.log`).
- Auto-enable: by default the orchestrator will auto-enable audit logging
  when it detects a manual run (not in CI and not invoked by pytest). This
  avoids creating files during CI/test runs while being convenient for local
  development.

What is logged
- Events include: `read_file.denied`, `read_file.toctou_detected`,
  `write_file.dest_symlink`, `write_file.toctou_detected`, `sub_agent.preflight_blocked`,
  and other error/exception events.

Retention & Rotation
- `core/logging_setup.py` attaches a `RotatingFileHandler` with default
  `maxBytes=5MB` and `backupCount=5`. Adjust these values in production
  or replace the handler with your preferred logging stack (syslog, ELK,
  cloud logging, etc.).

CI behaviour
- The GitHub Actions workflow uploads `logs/audit.log` (and rotated files)
  as an artifact when the test job fails. This makes investigating test
  failures easier when an audit-event influenced the outcome.

Threat Model Notes
- File-tool hardening enforces workspace confinement, denies symlinks,
  applies O_NOFOLLOW when available, and performs pre/post `lstat` checks
  to mitigate simple TOCTOU races. It is not a replacement for a hardened
  container runtime or kernel-level protections; consider adding
  `openat2`/`O_PATH`-based checks or running sensitive components in
  read-only containers for higher assurance.
