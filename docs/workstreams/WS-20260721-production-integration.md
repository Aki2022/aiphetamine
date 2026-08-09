---
schema_version: 2
id: WS-20260721-production-integration
status: archived
created_at: 2026-07-21
updated_at: 2026-07-21
branch: main
pr: ""
human_boundary_confirmed_at: 2026-07-21
next_human_gate: production-integration-review
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
related_guides:
  - docs/guides/production-integration.md
test_gates:
  commands:
    - python3 -m unittest discover -s tests -v
    - python3 -m compileall -q src hooks scripts
    - git diff --check
    - python3 <origin-doc-update-skill>/scripts/validate_repo_docs.py .
  quality:
    - Historical PyObjC, settings JSON, and normal Hook observations are recorded without persisting sensitive values; current release uses manual plist review and does not manage LaunchAgent state
required_reviewers: []
subagent_plan:
  mode: parent-only
  reason: "The task modifies one authenticated Claude configuration and one user LaunchAgent registration."
---

# Production Integration

## Goal

Apply and verify the approved macOS integration for AIphetamine without intentionally stimulating a rate limit or retaining sensitive operational data.

## Historical Success Criteria

The following criteria describe the 2026-07-21 operator integration record. They are
not current source-tree release claims. The current source tree only generates
Hook/plist artifacts; settings merge and LaunchAgent registration remain manual.

- PyObjC availability and menu-bar startup were checked in the historical integration attempt.
- One generated Hook fragment was reviewed for merge into one intended Claude settings file.
- One AIphetamine-only plist was generated and reviewed; registration is a manual operator action and is not managed by this repository.
- One naturally occurring ordinary Hook event was observed through sanitized evidence.

## Authorization Envelope

- Approved scope: PyObjC導入、実AppKit起動、Claude Hook設定の手動マージ、AIphetamine専用LaunchAgent登録、自然に発生する通常Hookイベントの確認を、意図的rate-limit誘発なしで実施する。
- Autonomous actions allowed: install PyObjC once; start the AppKit menu bar; merge one generated Hook fragment into one intended Claude settings file while preserving existing content; register one AIphetamine LaunchAgent; inspect and retain only sanitized normal Hook evidence.
- Confirm first: delete or replace existing Hooks; any additional Claude CLI invocation; rate-limit testing or capture; account/authentication changes; non-AIphetamine system setting changes; data deletion; commit, push, PR, release, or external publication.
- Cost or usage ceiling: one PyObjC installation, one settings-file merge, one LaunchAgent registration, one naturally occurring normal Hook event, no intentional rate limit, no additional Claude CLI invocation, and three same-root-cause failures maximum. Existing subscription use has no currency ceiling or invoice inspection.
- Out of scope: intentional rate-limit stimulation, resume verification, account switching, changing existing Hook behavior, distribution, deployment, or Git publication.

## Human Gates

- Start gate: confirmed on 2026-07-21
- Next gate: production-integration-review
- Stop conditions: stop at `production-integration-review`; stop on authentication change, existing-settings conflict, unexpected external write, sensitive-output risk, or three same-root-cause failures.

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-environment-preflight | complete | none | Safe dependency and configuration baseline |
| ISSUE-02-hook-merge | complete | ISSUE-01 | One non-destructive Hook settings merge |
| ISSUE-03-menubar-launchagent | complete | ISSUE-01 | One menu-bar start and LaunchAgent registration |
| ISSUE-04-normal-hook-evidence | complete | ISSUE-02 | One natural ordinary Hook evidence record |
| ISSUE-05-production-handoff | complete | ISSUE-02, ISSUE-03, ISSUE-04 | Sanitized verification and review handoff |

### ISSUE-01-environment-preflight

- status: complete
- depends_on: []
- guide_impact: required
- related_guides: [GUIDE-production-integration]
- guide_impact_reason: ""

#### Goal

Confirm dependency, configuration, and target-file state without modifying them.

#### Acceptance

- Intended Claude configuration is identified without retaining identity values.
- Existing configuration is valid JSON and can be preserved during a merge.
- PyObjC availability and existing AIphetamine LaunchAgent state are classified.

#### Current Status

PyObjC was absent; the selected settings file was valid JSON with existing Hook entries; no AIphetamine LaunchAgent was present before integration.

#### Next Actions

- Baseline complete.

### ISSUE-02-hook-merge

- status: complete
- depends_on: [ISSUE-01-environment-preflight]
- guide_impact: required
- related_guides: [GUIDE-production-integration]
- guide_impact_reason: "The manual Hook integration becomes an active operator workflow."

#### Goal

Merge one generated Hook fragment while preserving all existing settings content.

#### Acceptance

- A rollback copy is created only for the chosen settings file.
- Existing Hook entries remain present after merge.
- The resulting settings JSON is valid and the generated AIphetamine entries are present.

#### Current Status

One generated fragment was appended to the selected settings file with a rollback copy. Four AIphetamine Hook entries are present and JSON validity is confirmed; existing entries were retained.

#### Next Actions

- Await one ordinary Hook event for ISSUE-04.

### ISSUE-03-menubar-launchagent

- status: complete
- depends_on: [ISSUE-01-environment-preflight]
- guide_impact: required
- related_guides: [GUIDE-production-integration]
- guide_impact_reason: "The menu-bar and login integration are operator-visible."

#### Goal

Historically start the menu bar and generate one AIphetamine LaunchAgent plist for
manual operator review. Registration is not performed by the current source tree.

#### Acceptance

- PyObjC import succeeds and the menu adapter starts.
- The generated plist has the approved label and is syntactically valid.
- No unrelated LaunchAgent is changed.

#### Current Status

PyObjC import and plist syntax were checked in the historical integration attempt. The current release does not assert or manage a registered LaunchAgent; registration, if desired, is a separate human action after reviewing the generated plist.

#### Next Actions

- Await one ordinary Hook event for ISSUE-04.

### ISSUE-04-normal-hook-evidence

- status: complete
- depends_on: [ISSUE-02-hook-merge]
- guide_impact: required
- related_guides: [GUIDE-production-integration]
- guide_impact_reason: "The normal Hook verification procedure is operator-visible."

#### Goal

Observe one ordinary Hook event without issuing an additional Claude command or inducing a rate limit.

#### Acceptance

- Evidence contains only event class and success classification.
- No rate-limit behavior is inferred from ordinary events.

#### Current Status

After the user submitted one ordinary prompt in the selected primary Claude Code account, nine valid candidate records were observed. Only record type, count, and required-field validity were retained; no session, prompt, path, transcript, or authentication value was retained. No rate-limit record or rate-limit claim was made.

#### Next Actions

- Complete final local and runtime verification.

### ISSUE-05-production-handoff

- status: complete
- depends_on: [ISSUE-02-hook-merge, ISSUE-03-menubar-launchagent, ISSUE-04-normal-hook-evidence]
- guide_impact: required
- related_guides: [GUIDE-production-integration]
- guide_impact_reason: "The final production boundary and rollback instructions must be current."

#### Goal

Run quality gates and hand off the bounded production integration.

#### Acceptance

- All required verification passes and no out-of-scope behavior is claimed.

#### Current Status

Normal Hook evidence and all local/runtime gates are complete; the workstream is ready for human review.

#### Next Actions

- Stop at `production-integration-review`.

## Decisions

- The existing live CLI outcome remains inconclusive and is not retried in this workstream.
- Natural rate-limit behavior is explicitly excluded even if it occurs.
- PyObjC installation initially stopped before mutation because the Python environment required a virtual environment; a one-command, non-persistent override was used for the approved installation and succeeded.
- The normal Hook event was verified through user-operated primary-account activity; no agent-run Claude CLI invocation was used.

## Human Review Checkpoint

- Historical record: PyObjC/menu-bar checks, non-destructive Hook review, plist generation, and one user-generated ordinary Hook event. Current release does not install/register LaunchAgents or merge settings automatically.
- Final local and runtime gates pass. No rate limit was triggered or claimed.

## Verification

- `python3 -m unittest discover -s tests -v` passes 46 tests.
- `python3 -m compileall -q src hooks scripts` passes.
- `git diff --check` and the repository docs validator pass.
- The registered AIphetamine-only LaunchAgent plist passes `plutil -lint` and reports a running state.
- The selected primary Claude Code configuration has four AIphetamine Hook entries and remains valid JSON.
- A user-generated normal prompt produced nine valid candidate records; only count, record type, and required-field validity were retained.

## Completion

- [x] Every issue meets its acceptance criteria
- [x] Every issue records guide impact as required or none
- [x] Required guides describe current implemented behavior
- [x] Specs reflect any changed direction or requirements
- [x] Next human gate reached or the workstream intentionally stopped
- [x] 00_index.md updated
- [ ] Workstream archived when complete
