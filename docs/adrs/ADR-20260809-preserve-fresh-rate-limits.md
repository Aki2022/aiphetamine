---
id: ADR-20260809-preserve-fresh-rate-limits
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
  - GUIDE-resume-wiring
supersedes: ""
superseded_by: ""
---

# Decision: Preserve fresh rate-limit events across an AIphetamine restart

## Context

AIphetamine originally removed every rate-limit artifact at startup. That prevented stale events from being resumed, but it also discarded a naturally observed event before the operator could select it. The selection store is in memory, so preserving an event does not authorize an automatic resume after restart.

## Decision

During startup, preserve valid rate-limit JSON that is within the repository's 12-hour freshness window. Remove stale, invalid, processing, and temporary artifacts as before. If a preserved event has no candidate snapshot, reconstruct a selectable candidate from the event without changing the event itself.

## Alternatives Considered

- Continue deleting every event: rejected because a restart loses a current natural rate-limit observation.
- Preserve every event indefinitely: rejected because stale sessions would accumulate and become misleading.
- Automatically resume preserved events: rejected because selection remains an explicit in-memory human boundary.

## Consequences

### Positive

- A restart no longer destroys a current rate-limit observation or its account label.
- The operator can inspect and select a fresh event after the menu reloads.

### Negative or Follow-up

- Startup may display events created while AIphetamine was offline; the 12-hour freshness bound limits this exposure.
- The resident executor remains disabled until the live-launch gate is accepted.

## Links

- [Resume Wiring](../workstreams/WS-20260721-resume-wiring.md)
- [Architecture](../specs/architecture.md)
- [Resume Wiring Guide](../guides/resume-wiring.md)
