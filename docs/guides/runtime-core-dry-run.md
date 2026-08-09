---
id: GUIDE-runtime-core-dry-run
updated_at: 2026-07-21
source_issues: []
source_workstreams:
  - WS-20260721-app-shell
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
---

# Runtime Core Dry Run

## What It Does

The dry-run command inspects existing AIphetamine candidate and rate-limit event directories, calculates the next even-hour boundary, and reports aggregate eligibility statuses. It does not create data directories or logs, launch Claude, claim events, delete files, or persist selection state.

## How To Use

Run:

```bash
python3 scripts/run_dry_cycle.py
```

To inspect a temporary or alternate data root:

```bash
python3 scripts/run_dry_cycle.py --data-root /path/to/aiphetamine-data
```

Output is sanitized JSON containing only the mode, counts, next boundary, and allowlisted status counts.

## Maintenance Notes

Keep this guide aligned with `scripts/run_dry_cycle.py` and `src/aiphetamine/app_runtime.py`. Verify it with the repository unittest suite, `git diff --check`, and the docs validator.

## Known Limitations

- This command is a read-only inspection path, not the installable or user-runnable MVP.
- It creates no runtime directories or logs.
- It does not install Claude Code Hooks, run the macOS menu bar app, register LaunchAgent, or launch Claude.
- Selection state is in memory only and is empty for a fresh command invocation.
- Natural rate-limit Hook behavior and same-session event recreation remain unverified.
