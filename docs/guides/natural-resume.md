---
id: GUIDE-natural-resume
updated_at: 2026-07-22
source_issues: []
source_workstreams:
  - WS-20260721-natural-resume
  - WS-20260722-resume-outcome
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
---

# Natural Resume Verification

## Observed Boundary

One naturally occurring rate-limit event caused one Claude resume process to be started at the next fixed boundary; unselected events were left untouched. The operator confirmed that the intended session resumed. No retry or intentional rate-limit action occurred.

This guide records the earlier one-shot verification. The current resident scheduler uses account-routed execution only for sessions explicitly checked in the menu.

## Limitations

The one-shot result was confirmed by the operator after the fact; its earlier process runner did not retain a machine-readable exit result. The runtime now treats only a zero process exit code as completion. This does not prove rate-limit re-event handling or make the resident scheduler automatically enabled.

## Safety Rules

Never induce a rate limit. Before any additional live resume or re-event verification, obtain a separate approval and retain only sanitized classifications.
