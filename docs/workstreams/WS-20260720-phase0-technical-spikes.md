---
schema_version: 2
id: WS-20260720-phase0-technical-spikes
status: active
created_at: 2026-07-20
updated_at: 2026-07-20
branch: WS-20260720-phase0-technical-spikes
pr: ""
human_boundary_confirmed_at: 2026-07-20
next_human_gate: phase0-results-review
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
related_guides: []
---

# Phase 0 Claude Hook and Resume Feasibility

## Goal

Determine whether the Claude Code Hook and official resume behaviors required by the AIphetamine MVP are feasible on the target macOS environment, and feed evidence-backed results into the active specs before any MVP implementation begins.

## Success Criteria

- Candidate discovery, activity refresh, and explicit session-end behavior are verified against real Hook payloads or recorded as unverified at the human gate.
- Rate-limit Hook payload, same-session event recreation, and non-interactive resume Hook behavior are verified only through separately approved live tests.
- `claude -p --resume <session_id> "Continue"` behavior is verified for history continuity, cwd handling, and original-process conflict only through separately approved live tests.
- Every conclusion distinguishes fixture/unit evidence from real-environment evidence; mocks alone never establish external Claude behavior.
- Evidence contains no secrets, prompt bodies, transcript bodies, local absolute paths, usernames, or raw session identifiers.
- PRD and architecture are updated when observed behavior contradicts an assumption.
- Spike tests, `git diff --check`, and the repository docs validator pass.

## Authorization Envelope

- Approved scope: AIphetamine Phase 0 technical spikes for Claude Hook payloads, candidate lifecycle, rate-limit event recreation, official resume behavior, and process conflict
- Autonomous actions allowed: repository-local spike harnesses, fixtures, unit tests, sanitized evidence tables, documentation updates, read-only environment inspection, and free local validation commands
- Confirm first: Claude Code settings changes; any rate-limit-related test; any live `claude --resume` invocation; writes outside this repository; dependency installation; network access; authentication or secret handling changes; destructive operations; git branch creation, commit, push, PR, release, or deployment
- Cost or usage ceiling: no metered API use; never intentionally drive Claude to a rate limit; rate-limit-related tests require human approval each time and must use naturally occurring events
- Out of scope: MVP production implementation, menu bar UI, scheduler, LaunchAgent installation, automatic Hook configuration changes, package installation, publishing, and deployment

## Human Gates

- Start gate: confirmed on 2026-07-20
- Next gate: phase0-results-review
- Stop conditions: stop before every confirm-first action; stop if a secret or local identifying value may be exposed; stop if observed behavior contradicts an active spec; stop if a required live event is unavailable; stop if a new dependency, network access, or metered use appears necessary

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-spike-harness | pending | none | Safe fixture-driven payload capture and redaction harness |
| ISSUE-02-candidate-lifecycle | pending | ISSUE-01 | Candidate discovery, refresh, and end behavior evidence |
| ISSUE-03-rate-limit-hook | pending | ISSUE-01 | Approved real-event rate-limit behavior evidence |
| ISSUE-04-resume-behavior | pending | ISSUE-01 | Approved official resume and process-conflict evidence |
| ISSUE-05-consolidate-results | pending | ISSUE-02, ISSUE-03, ISSUE-04 | Evidence matrix, spec alignment, and human-gate report |

### ISSUE-01-spike-harness

- status: pending
- depends_on: []
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Feasibility investigation only; no implemented user-visible behavior exists or changes in this workstream."

#### Goal

Create a repository-local, fixture-driven harness that validates expected Hook payload fields and produces sanitized evidence without retaining sensitive values.

#### Acceptance

- Tests are written before or with the harness for accepted/rejected payload shapes and redaction.
- Raw session IDs, paths, prompt content, transcript content, and secrets are never persisted in fixtures or output.
- The harness performs no network calls and does not modify Claude Code settings.

#### Current Status

Not started.

#### Next Actions

- Define minimal sanitized fixture contracts from the active specs.
- Add failing tests for payload validation and redaction.
- Implement only enough harness code to make those tests pass.

### ISSUE-02-candidate-lifecycle

- status: pending
- depends_on: [ISSUE-01-spike-harness]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Feasibility investigation only; no implemented user-visible behavior exists or changes in this issue."

#### Goal

Verify which Claude Code Hook events can create, refresh, and remove candidate-session snapshots, including whether activity can refresh `updated_at` within the 24-hour freshness requirement.

#### Acceptance

- Available event names and payload fields are recorded from approved evidence.
- Candidate creation, activity refresh, and explicit end behavior are each marked verified, contradicted, or unverified.
- Any Claude settings change or live Hook execution occurs only after explicit human approval.

#### Current Status

Blocked pending ISSUE-01 and human approval for live Hook work.

#### Next Actions

- Prepare a sanitized manual test protocol.
- Request approval before applying Hook settings or running the protocol.

### ISSUE-03-rate-limit-hook

- status: pending
- depends_on: [ISSUE-01-spike-harness]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Feasibility investigation only; no implemented user-visible behavior exists or changes in this issue."

#### Goal

Verify the natural rate-limit Hook payload and whether an approved resume attempt while still limited recreates an event for the same session.

#### Acceptance

- AI activity is never intentionally driven to a rate limit.
- Every rate-limit-related test has separate explicit human approval and uses a naturally occurring event.
- Payload availability, same-session identity, and event recreation are marked verified, contradicted, or unverified.

#### Current Status

Blocked pending ISSUE-01, a naturally occurring event, and human approval.

#### Next Actions

- Prepare a no-secret capture protocol and wait for a natural event.

### ISSUE-04-resume-behavior

- status: pending
- depends_on: [ISSUE-01-spike-harness]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Feasibility investigation only; no implemented user-visible behavior exists or changes in this issue."

#### Goal

Verify official non-interactive resume behavior, cwd handling, history continuity, Hook execution, and conflict behavior when the original Claude process is present or absent.

#### Acceptance

- Every live `claude --resume` invocation has explicit human approval.
- The fixed message is `Continue`; no prompt or transcript body is captured.
- Process-present and process-absent scenarios are marked verified, contradicted, or unverified.

#### Current Status

Blocked pending ISSUE-01 and human approval for live resume work.

#### Next Actions

- Prepare exact commands with placeholders and sanitized expected evidence.
- Request approval before each live invocation.

### ISSUE-05-consolidate-results

- status: pending
- depends_on: [ISSUE-02-candidate-lifecycle, ISSUE-03-rate-limit-hook, ISSUE-04-resume-behavior]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Documentation records feasibility conclusions; no implemented user-visible behavior exists yet."

#### Goal

Consolidate the spike evidence, align active specs with verified behavior, and present the Phase 0 result at the human gate.

#### Acceptance

- A single evidence matrix separates verified, contradicted, unverified, and blocked conclusions.
- Active specs contain no claims contradicted by evidence.
- Tests, `git diff --check`, and docs validation pass.
- No MVP implementation begins before human approval at `phase0-results-review`.

#### Current Status

Pending preceding spikes.

#### Next Actions

- Consolidate sanitized results after the preceding issues reach their stop conditions.

## Decisions

- Phase 0 is a feasibility workstream; MVP implementation is intentionally deferred to a later human-authorized workstream.
- Artificially causing a Claude rate limit is prohibited.
- Rate-limit-related tests and live resume invocations require explicit human approval each time.
- Mock or fixture evidence cannot establish real Claude Code behavior.

## Completion

- [ ] Every issue meets its acceptance criteria
- [ ] Every issue records guide impact as required or none
- [ ] Required guides describe current implemented behavior
- [ ] Specs reflect any changed direction or requirements
- [ ] Next human gate reached or the workstream intentionally stopped
- [ ] 00_index.md updated
- [ ] Workstream archived when complete
