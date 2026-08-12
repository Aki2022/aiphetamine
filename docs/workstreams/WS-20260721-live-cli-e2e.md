---
schema_version: 2
id: WS-20260721-live-cli-e2e
status: active
created_at: 2026-07-21
updated_at: 2026-07-21
branch: main
pr: ""
human_boundary_confirmed_at: 2026-07-21
next_human_gate: live-cli-e2e-review
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
related_guides: []
test_gates:
  commands:
    - python3 -m unittest discover -s tests -v
    - git diff --check
    - python3 <origin-doc-update-skill>/scripts/validate_repo_docs.py .
  quality:
    - live output is retained only in memory and reduced to allowlisted evidence
    - no authentication values, raw response, prompt, transcript, path, or session identifier is persisted
    - no intentional rate-limit stimulation
required_reviewers: []
subagent_plan:
  mode: parent-only
  reason: "The single live call requires parent-owned authorization, target selection, and sanitized evidence handling."
---

# Live Claude CLI E2E

## Goal

Run exactly one approved, non-rate-limit Claude CLI invocation to confirm that the authenticated primary CLI can start in non-interactive mode under the current environment, while retaining only sanitized process evidence.

## Success Criteria

- Exactly one non-interactive CLI call is made with `--verbose` and a fixed harmless message.
- The call returns a process exit status and a non-error classification without retaining response content.
- No Claude settings are persisted or modified, no account switch occurs, and no rate-limit event is induced.
- Any observed `rate_limit_event` stream type is explicitly not treated as a `StopFailure(rate_limit)` Hook payload.
- The result is recorded for the next human review without claiming MVP readiness or Hook feasibility.

## Authorization Envelope

- Approved scope: one primary-account non-interactive Claude CLI E2E call using transient command-line options, in-memory output capture, sanitized evidence, and repository documentation updates.
- Autonomous actions allowed: read-only local target checks, exactly one approved CLI invocation, in-memory output parsing, sanitized evidence recording, tests, and docs updates.
- Confirm first: any second CLI call or retry; any rate-limit-related test or event capture; Claude settings or Hook configuration writes; account switching or authentication changes; external writes; network changes; dependency installation; destructive operations; branch creation, commit, push, PR, release, deployment, UI/AppKit, LaunchAgent, or packaging.
- Cost or usage ceiling: one CLI invocation, zero retries, no currency approval required by human decision, and no usable token/price telemetry claimed.
- Out of scope: intentional rate-limit stimulation, rate-limit Hook verification, resume-history claims, production Hook installation, app installation, UI, LaunchAgent, and deployment.

## Human Gates

- Start gate: confirmed on 2026-07-21 for one live CLI invocation; subscription usage is not a separate approval gate.
- Next gate: live-cli-e2e-review
- Stop conditions: stop after the single call regardless of result; stop immediately on authentication change, settings persistence, unexpected external write, raw sensitive output exposure, or any need for retry.

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-single-live-cli | blocked | none | One call was launched, but its sanitized result was not recoverable from the tool boundary |
| ISSUE-02-e2e-handoff | blocked | ISSUE-01 | Bounded inconclusive result and human review handoff |

### ISSUE-01-single-live-cli

- status: blocked
- depends_on: []
- guide_impact: none
- related_guides: []
- guide_impact_reason: "This is a feasibility observation; it does not change the current user workflow or production behavior."

#### Goal

Execute the one approved live CLI call and reduce its result to safe allowlisted evidence.

#### Acceptance

- One call only, with no retry.
- Exit status, fixed stream type classifications, and result error booleans are retained; raw response and identifiers are discarded.
- No rate-limit behavior is inferred from a generic stream type.

#### Current Status

The single approved call was launched once and was not retried. The wrapper completed without returning the expected sanitized evidence lines, and no raw output was persisted. Exit status, stream types, and result error classification therefore remain unverified.

#### Next Actions

- Human review is required before any second call or retry is considered.

### ISSUE-02-e2e-handoff

- status: blocked
- depends_on: [ISSUE-01-single-live-cli]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Evidence handoff only; no current operator workflow changes."

#### Goal

Run repository gates and hand off the bounded live result for human review.

#### Acceptance

- Workstream records the sanitized result and resource usage.
- Tests, diff check, and docs validator pass.
- No MVP or rate-limit Hook claim is upgraded by this one call.

#### Current Status

ISSUE-01 is blocked because the execution wrapper did not return the expected sanitized evidence lines. Local repository gates pass, but the live result cannot be classified.

#### Next Actions

- Obtain a human decision before any replacement live call or move to another implementation slice.

## Human Review Checkpoint

- The approved one-call boundary was honored: one primary-account non-rate-limit CLI call was launched, with no retry, settings write, account switch, or intentional rate-limit stimulation.
- The sanitized result could not be recovered after the execution wrapper completed. No raw response, authentication value, prompt, transcript, path, or session identifier was retained.
- This workstream does not claim CLI success, non-error completion, MVP readiness, or rate-limit Hook feasibility.
- Human decision required: either accept the bounded inconclusive result and choose the next implementation slice, or separately approve a replacement single-call evidence collection run.

## Verification

- `python3 -m unittest discover -s tests -v` passes 34 tests.
- `git diff --check` passes.
- Repository docs validator passes.

## Decisions

- Human decision on 2026-07-21: subscription usage is not a separate approval gate; the live action itself is approved once for one call.
- The call is a capability check only and cannot establish rate-limit Hook behavior.
- A missing tool-returned sanitized result is recorded as inconclusive; it is not converted into a success or failure claim.

## Completion

- [ ] Every issue meets its acceptance criteria
- [ ] Every issue records guide impact as required or none
- [ ] Required guides describe current implemented behavior
- [ ] Specs reflect any changed direction or requirements
- [x] Next human gate reached or the workstream intentionally stopped
- [x] 00_index.md updated
- [ ] Workstream archived when complete
