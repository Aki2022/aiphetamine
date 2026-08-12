---
id: GUIDE-production-integration
updated_at: 2026-08-12
source_issues: []
source_workstreams:
  - WS-20260721-production-integration
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
---

# Production Integration

## Public Source Release

The source repository is public. Do not commit local runtime data under
`~/.local/share/aiphetamine/`, Claude configuration directories, credentials,
tokens, transcripts, generated settings, or generated LaunchAgent files.
Candidate and rate-limit records intentionally contain local session and
project metadata for runtime use; those records must remain on the operator's
machine. The public source boundary is documented in
[ADR-20260812-public-source-release](../adrs/ADR-20260812-public-source-release.md).

## Applied Boundary

The repository generates a JSON Hook fragment and an AIphetamine-only LaunchAgent plist. The Hook merge and LaunchAgent registration remain manual operator actions; this source tree does not silently edit Claude settings or register LaunchAgents. PyObjC availability, live menu-bar startup, and normal Hook behavior are not verified by the local source-tree tests. A bounded natural-resume attempt was operator-confirmed historically, but it is not a general rate-limit or resume guarantee.

## Normal Hook Verification

Use the selected Claude Code account normally and submit one ordinary prompt. Do not attempt to reach a rate limit. After the normal Hook event occurs, inspect only a sanitized success classification and event class; do not retain prompt, session, path, transcript, or authentication values.

## Rollback Boundary

Remove only the AIphetamine Hook entries that were manually merged, then manually unregister and delete only the generated `local.aiphetamine.menubar` LaunchAgent plist. Do not modify unrelated Hook entries or LaunchAgents.

## Known Limitations

- A natural one-shot resume was observed and recorded separately; repeat rate-limit behavior and long-running production reliability remain unverified.
- Unlabeled legacy records cannot be resumed until a fresh account-labeled Hook event is observed.
- No additional Claude CLI invocation is part of local repository verification.
