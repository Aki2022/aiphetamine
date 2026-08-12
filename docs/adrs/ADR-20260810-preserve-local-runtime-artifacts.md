---
id: ADR-20260810-preserve-local-runtime-artifacts
status: accepted
scope: development
created_at: 2026-08-10
updated_at: 2026-08-10
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

# Decision: Preserve ambiguous and in-progress local runtime artifacts

## Context

The Hook receives `SessionEnd` events that may not carry an account label,
while candidate files are separated by account. Startup cleanup can also run
near an atomic Hook write and encounter its temporary file. Deleting either
artifact without proving ownership can remove a candidate or event that the
runtime still needs.

## Decision

An unlabeled `SessionEnd` may remove only the `unknown` or legacy flat
candidate namespace. It must not sweep `main` or `alias` candidates. Any
matching rate-limit event in any account scope is preserved.

Startup cleanup removes `.tmp.` artifacts only when their modification time is
older than 24 hours. Recent temporary files are treated as potentially active
writers and retained for a later cleanup pass.

## Alternatives Considered

- Delete every account-scoped candidate for an unlabeled end event: rejected
  because the event does not prove ownership and can delete another account's
  candidate.
- Delete every temporary artifact at startup: rejected because it can race an
  atomic Hook write and lose an event in progress.
- Never delete temporary artifacts: rejected because abandoned files would
  accumulate indefinitely.

## Consequences

### Positive

- Ambiguous lifecycle events cannot remove a candidate from another account.
- Startup cleanup does not remove a recently-created atomic-write temporary.

### Negative or Follow-up

- Unlabeled sessions may leave stale account-scoped candidates until their
  normal freshness handling removes them.
- A crashed writer's temporary artifact may remain for up to 24 hours.

## Links

- [Resume Wiring](../workstreams/WS-20260721-resume-wiring.md)
- [Architecture](../specs/architecture.md)
- [Resume Wiring Guide](../guides/resume-wiring.md)
