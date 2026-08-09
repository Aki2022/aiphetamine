---
id: GUIDE-resume-wiring
updated_at: 2026-08-09
source_issues: []
source_workstreams:
  - WS-20260721-resume-wiring
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
---

# Resume Wiring

## Current Behavior

The status item is labelled `AI` with an AIphetamine tooltip. Its menu uses native macOS checkmarks; choosing a candidate updates that checkmark immediately and keeps activation only in memory. When a Hook does not provide names, the menu shows the project directory name and a short session discriminator instead of generic fallback labels.

The menu also shows the most recent poll boundary and aggregate outcome counts, such as `最終poll: 02:00（成功5／復元1）`. It never shows session IDs, prompts, or local paths. The status is held in memory and is refreshed when the menu opens, so restarting AIphetamine clears the displayed result until the next poll.

It schedules only the next even-hour poll and runs polls outside the menu thread. With the validated executable configuration, polls use the account-routed Claude executor; if configuration validation fails, the runtime falls back to a disabled executor.

Resume requests carry the account label from both the rate-limit event and its matching candidate. The labels must be present and equal; an unlabeled or conflicting pair is refused. The live executor routes `main` through `~/.claude` and `alias` through the explicit `~/.claude-seat2` path; it refuses an unknown or conflicting account. Live account-routed execution is enabled only for sessions explicitly selected in the menu. Claude is invoked with `-p --resume`, so the work continues in the background; an existing interactive Claude window is not opened or changed by the poll.

The in-memory check state is scoped by both session ID and account label. A
transcript lookup may add a title or repository display name, but it never
converts an unlabeled candidate into an account-authorized candidate.

When a rate-limit event exists without a candidate snapshot, the runtime reconstructs a selectable candidate from the event only when the event has a known account label. This covers Claude flows that emit `SessionEnd` after `StopFailure`; the event remains the authoritative trigger while the candidate supplies the menu selection boundary. Unlabeled legacy events are kept for inspection but cannot be selected for automatic resume.

## Configuration Boundary

The executable path is accepted only from an owner-controlled JSON configuration file when it is an absolute, regular, executable, non-symlink file and every ancestor directory is a trusted, non-writable boundary. The configured path points to the verified managed Claude executable. The account directory and executable are revalidated immediately before a real launch; if either becomes invalid, the runtime disables that launch without disabling the menu.

## Verification

Run the unittest suite, Python compilation, diff check, and documentation validator. The AppKit test verifies the status-item label and check-state behavior. Only checked menu rows can reach the live executor. Existing local rate-limit files without an account label are not evidence of the second account; they must be matched to the session store or recreated by a naturally occurring Hook event.

Decision records: [ADR-20260809-account-routed-resume](../adrs/ADR-20260809-account-routed-resume.md) and [ADR-20260809-account-scoped-artifacts](../adrs/ADR-20260809-account-scoped-artifacts.md).
