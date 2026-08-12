---
id: ADR-20260812-public-source-release
status: accepted
scope: development
created_at: 2026-08-12
updated_at: 2026-08-12
source_workstreams:
  - docs/workstreams/WS-20260721-resume-wiring.md
source_issues: []
related_specs:
  - docs/specs/architecture.md
related_guides:
  - docs/guides/production-integration.md
supersedes: ""
superseded_by: ""
---

# Decision: Publish the source repository

## Context

The implementation is intended for public source distribution. The repository
contains local-runtime integration code, so publication must not expose
credentials, local records, transcripts, or raw external process output.

## Decision

Publish `Aki2022/aiphetamine` as a public repository after the independent
security review returned `PUBLISH`. Keep local runtime state, Claude
configuration, credentials, tokens, transcripts, and generated local files
outside the repository. Keep live resume and LaunchAgent registration as
operator-controlled actions rather than public-release guarantees.

## Alternatives Considered

- Keep the repository private: rejected because the user explicitly approved
  public source distribution after the security review.
- Publish only a reduced source archive: rejected because the repository's
  documented source tree is the intended distribution boundary.

## Consequences

### Positive

- The source is discoverable and reviewable by users.
- The repository's privacy boundary is explicit in the operator guide and
  README.

### Negative or Follow-up

- Future changes must preserve the no-credentials/no-runtime-data boundary.
- Public publication does not imply that live Claude resume or LaunchAgent
  registration has been verified on every operator machine.

## Links

- [Resume wiring workstream](../workstreams/WS-20260721-resume-wiring.md)
- [Production integration guide](../guides/production-integration.md)
- [Architecture specification](../specs/architecture.md)
