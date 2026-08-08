---
id: GUIDE-production-integration
updated_at: 2026-07-21
source_issues: []
source_workstreams:
  - WS-20260721-production-integration
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
---

# Production Integration

## Applied Boundary

PyObjC is installed, the AIphetamine Hook fragment is merged without removing existing Hook entries, and the AIphetamine-only LaunchAgent is registered. The generated settings are valid JSON and the LaunchAgent is registered.

## Normal Hook Verification

Use the selected Claude Code account normally and submit one ordinary prompt. Do not attempt to reach a rate limit. After the normal Hook event occurs, inspect only a sanitized success classification and event class; do not retain prompt, session, path, transcript, or authentication values.

## Rollback Boundary

Remove only the AIphetamine Hook entries that were added during the merge, then unregister and delete only the `local.aiphetamine.menubar` LaunchAgent plist. Do not modify unrelated Hook entries or LaunchAgents.

## Known Limitations

- Rate-limit Hook behavior and resume behavior remain unverified.
- No additional Claude CLI invocation was used for this integration.
