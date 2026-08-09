---
id: GUIDE-hook-setup
updated_at: 2026-08-09
source_issues: []
source_workstreams:
  - WS-20260721-mvp-integration
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
---

# Claude Hook Setup

## Generate a Fragment

Generate a JSON settings fragment with `python3 scripts/generate_hook_config.py --hook-command '<command>' [--account-name main|alias]`. Review the resulting fragment and merge it manually with the intended Claude Code settings file. The account value is allowlisted to `main` or `alias`; unknown values are rejected.

The generator parses the command into argv tokens, rejects shell metacharacters,
newlines, and shell environment-assignment words such as `PATH=/tmp/evil`, and
quotes the normalized tokens before adding Hook arguments.
Use a direct executable plus its fixed arguments; do not pass shell pipelines,
command substitutions, or other shell syntax.

## Safety Boundary

The generator never reads or edits existing Claude settings. The Hook writer creates candidate records for session/activity events, creates a rate-limit record only for `StopFailure`, and removes the candidate record on session end unless the matching rate-limit record exists. New records are stored in account-scoped directories under `candidates/{main,alias,unknown}/` and `rate_limits/{main,alias,unknown}/`; the scope and optional JSON label must agree. Local records contain the session ID and absolute project path required by the runtime; operational logs and diagnostic output do not echo those values.

For two isolated Claude Code configurations, merge the `main` fragment into `~/.claude/settings.json` and the `alias` fragment into `~/.claude-seat2/settings.json`. The runtime uses the explicit `~/.claude-seat2` path for the alias account and does not execute a login shell to discover it. The shell wrapper must set `CLAUDE_CONFIG_DIR=~/.claude-seat2` before invoking Claude Code; a label in settings alone does not change the authenticated account. When multiple Claude installations exist, call the same verified executable explicitly in both wrappers rather than relying on PATH order; otherwise an older installation can select retired model IDs.

## Resume Safety

Both the rate-limit event and its candidate snapshot must carry the same
allowlisted account label before a resume can be launched. Unlabeled legacy
records remain inspectable but are never treated as an account authorization;
they require a fresh account-labeled Hook event.

## Verification and Removal

Validate the generated JSON before merging, confirm Hook-event compatibility in the target Claude Code environment, and remove only the manually merged AIphetamine Hook entries to disable it. Do not deliberately cause a rate limit; the earlier natural one-shot result is historical evidence, not a general rate-limit guarantee.
