---
id: ADR-20260809-account-scoped-artifacts
status: accepted
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

# Decision: Isolate account artifacts and fail closed on ambiguity

## Context

Two Claude Code accounts can produce the same session identifier. A single flat
filename namespace can therefore overwrite the other account's candidate or
rate-limit event. An unlabeled or malformed record must not be allowed to pick
an execution account by inference.

## Decision

New Hook records are written below `candidates/{main,alias,unknown}/` and
`rate_limits/{main,alias,unknown}/`. The scoped directory and JSON label must
agree. Legacy flat records remain readable only when unlabeled; labeled legacy
records are rejected. Resume eligibility requires both the event and candidate
to carry the same allowlisted account label. Duplicate session IDs are removed
from repository results instead of selecting an arbitrary winner.

Filesystem reads and mutations use no-follow directory descriptors where the
platform provides them. The executable and account directory are revalidated
immediately before a real process launch.

The in-memory selection state is keyed by `(session_id, account_name)`;
selection from one account cannot authorize the same session ID in another
account. Transcript metadata may supply a human-readable title, but it never
fills an absent account label.

## Alternatives Considered

- Keep one flat namespace and trust `account_name`: rejected because identical
  session IDs can overwrite one another before validation.
- Infer a missing account from the candidate or menu row: rejected because it
  turns ambiguous historical data into an execution authorization.
- Delete all legacy records immediately: rejected because it would discard
  natural events without an explicit migration boundary.

## Consequences

### Positive

- Account routing has an explicit storage and runtime boundary.
- Ambiguous, malformed, or unlabeled data cannot launch Claude.
- Path-based symlink races are reduced by descriptor-relative operations and
  no-follow opens.

### Negative or Follow-up

- Existing unlabeled events must be observed again through an account-labeled
  Hook before they can be resumed.
- Legacy flat records are retained for safe inspection but are not a trusted
  source for account-routed execution.

## Links

- [Resume Wiring](../workstreams/WS-20260721-resume-wiring.md)
- [Architecture](../specs/architecture.md)
- [Hook Setup](../guides/hook-setup.md)
- [Resume Wiring Guide](../guides/resume-wiring.md)
