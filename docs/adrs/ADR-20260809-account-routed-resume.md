---
id: ADR-20260809-account-routed-resume
status: proposed
scope: development
created_at: 2026-08-09
updated_at: 2026-08-09
source_workstreams:
  - WS-20260721-resume-wiring
source_issues: []
related_specs:
  - SPEC-aiphetamine-architecture
related_guides:
  - GUIDE-hook-setup
  - GUIDE-resume-wiring
supersedes: ""
superseded_by: ""
---

# Decision: Route resume by an explicit local account label

## Context

Two Claude Code configurations are used on one Mac. A session identifier alone does not tell AIphetamine which isolated configuration must execute a future resume. Existing rate-limit records can also predate account labeling, so treating an unlabeled event as the second account would be unsafe.

## Decision

Carry an optional allowlisted account label (`main` or `alias`) from the Hook record through the resume request. The live executor must set the matching `CLAUDE_CONFIG_DIR`; it refuses an unknown account or a conflict between the event and candidate labels. The resident scheduler remains disabled until the separate live-launch gate is accepted.

## Alternatives Considered

- Use one global `claude` executable for every session: rejected because it can resume a session through the wrong authenticated configuration.
- Infer the account from the menu label only: rejected because presentation text is not a trustworthy execution boundary.
- Store an email address or authentication identifier: rejected because it adds sensitive data without improving the routing contract.

## Consequences

### Positive

- A future live resume cannot silently fall back to the wrong Claude account.
- The Hook and executor can be tested locally without retaining authentication data.

### Negative or Follow-up

- Existing unlabeled rate-limit files require session-store matching or a new natural Hook event before they can prove second-account ownership.
- Enabling the resident executor still requires a separate human approval and live verification.

## Links

- [Resume Wiring](../workstreams/WS-20260721-resume-wiring.md)
- [Architecture](../specs/architecture.md)
- [Hook Setup](../guides/hook-setup.md)
- [Resume Wiring Guide](../guides/resume-wiring.md)
