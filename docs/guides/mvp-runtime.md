---
id: GUIDE-mvp-runtime
updated_at: 2026-07-21
source_issues: []
source_workstreams:
  - WS-20260721-mvp-integration
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
---

# MVP Runtime

## What It Does

The local runtime creates the event directories, keeps session activation only in memory, writes sanitized daily-rotated logs with seven backups, and schedules one future even-hour poll at a time. The menu presentation model sanitizes and truncates candidate labels before display.

## Local Verification

Run the full unittest suite, Python compilation, plist syntax validation for a generated temporary plist, `git diff --check`, and the documentation validator. The AppKit adapter is optional at runtime and raises the safe `appkit_unavailable` classification when PyObjC is not installed.

## Launch at Login Boundary

`LaunchAgentManager` only generates a plist. It does not register or deregister a LaunchAgent. Registering the generated plist is a separate human-confirmed production step.

## Known Limitations

- No Claude process is launched by this local verification workflow.
- Menu actions are represented by the testable controller; production AppKit binding and LaunchAgent registration require separate confirmation.
- No live rate-limit Hook behavior is claimed.
