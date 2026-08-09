---
schema_version: 2
id: WS-20260721-resume-wiring
status: active
created_at: 2026-07-21
updated_at: 2026-08-09
branch: main
pr: ""
human_boundary_confirmed_at: 2026-07-21
next_human_gate: live-resume-verification
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
related_guides:
  - docs/guides/resume-wiring.md
test_gates:
  commands:
    - python3 -m unittest discover -s tests -v
    - python3 -m compileall -q src hooks scripts
    - git diff --check
    - python3 <origin-doc-update-skill>/scripts/validate_repo_docs.py .
  quality:
    - selected-session live resume produces only sanitized local outcome classifications
required_reviewers: []
subagent_plan:
  mode: parent-only
  reason: "The menu and scheduler connect to the live LaunchAgent-owned process."
---

# Resume Wiring

## Goal

Wire the existing local eligibility and resume contracts into the running menu-bar application while keeping every live launch behind an explicit selected, account-labeled session boundary.

## Success Criteria

- Menu rows can toggle in-memory activation and Quit works.
- One-shot AppKit scheduling invokes the local poll service through an injected resume boundary.
- A validated configured Claude executable is available to the account-routed resume adapter; live launch remains limited to the separately gated verification issue.

## Authorization Envelope

- Approved scope: 操作可能なメニューバー、2時間scheduler、設定済みClaude実行ファイルのアカウント別resume接続、およびチェック済みセッションに限定したlive resume検証。
- Autonomous actions allowed: repository-local code, tests, guides, and one AIphetamine-only LaunchAgent restart.
- Confirm first: additional Claude resume launches beyond the selected-session verification, Claude settings changes, dependency additions, account changes, other LaunchAgent changes, data deletion, and Git publication.
- Cost or usage ceiling: one fixed-boundary live verification for the explicitly checked sessions; no additional rate-limit stimulation; three same-root-cause failures maximum.
- Out of scope: unselected-session resume, intentional rate-limit stimulation, and Git publication.

## Human Gates

- Start gate: confirmed on 2026-07-21
- Next gate: live-resume-verification
- Stop conditions: stop at `live-resume-verification`, on unexpected external writes, or after three same-root-cause failures.

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-menu-actions | complete | none | Interactive candidate, Quit, and login controls |
| ISSUE-02-scheduler-runtime | complete | ISSUE-01 | AppKit timer and worker integration |
| ISSUE-03-resume-configuration | complete | ISSUE-02 | Validated executable configuration and disabled launch boundary |
| ISSUE-04-wiring-handoff | complete | ISSUE-01, ISSUE-02, ISSUE-03 | Guides and local verification |
| ISSUE-05-menu-operability | complete | ISSUE-01 | Identifiable candidates and native check state |
| ISSUE-06-live-resume-enablement | in_progress | ISSUE-01, ISSUE-02, ISSUE-03, ISSUE-05 | Account-routed live executor behind explicit menu selection |

### ISSUE-01-menu-actions

- status: complete
- depends_on: []
- guide_impact: required
- related_guides: [GUIDE-resume-wiring]
- guide_impact_reason: ""

#### Goal

Connect AppKit menu items to the existing menu controller while keeping action logic testable.

#### Acceptance

- Candidate toggles, Quit, and login control actions are connected without changing unrelated system state.

#### Current Status

Candidate toggle and Quit bindings are connected in the AppKit adapter. Launch at Login remains intentionally disabled because changing it is outside this workstream's autonomous boundary.

#### Next Actions

- Complete.

### ISSUE-02-scheduler-runtime

- status: complete
- depends_on: [ISSUE-01-menu-actions]
- guide_impact: required
- related_guides: [GUIDE-resume-wiring]
- guide_impact_reason: "Fixed-time polling becomes active application behavior."

#### Goal

Connect AppKit timers and background dispatch to the existing one-shot scheduler.

#### Acceptance

- The app starts scheduling only the next future boundary and refreshes after a safe poll.

#### Current Status

The running entry point starts the one-shot scheduler, uses a background worker, and routes polls through the validated account-routed executor. Invalid executable configuration still falls back to `DisabledResumeExecutor`.

#### Next Actions

- Existing scheduler and executor tests pass; the LaunchAgent reports a running state after the safe reload.

### ISSUE-03-resume-configuration

- status: complete
- depends_on: [ISSUE-02-scheduler-runtime]
- guide_impact: required
- related_guides: [GUIDE-resume-wiring]
- guide_impact_reason: "Executable configuration controls whether future resume may be enabled."

#### Goal

Validate a configured executable and wire it as a disabled-by-policy executor.

#### Acceptance

- The configured path is validated before launch.
- A policy permits actual launch only for explicitly selected sessions and a known account.

#### Current Status

The approved owner-only runtime configuration contains one resolved, regular, executable Claude path. The account-routed live executor now uses it only for explicitly selected sessions.

The resume contract carries an optional account label. The account-routed executor selects an isolated `CLAUDE_CONFIG_DIR` and refuses unknown or conflicting labels.

The Hook/runtime boundary also preserves or reconstructs a candidate when `StopFailure(rate_limit)` is followed by `SessionEnd`, so an account-labeled rate-limit event remains selectable.

Startup now preserves fresh valid rate-limit events and removes only stale or invalid artifacts, so reloading the menu does not discard the current natural verification event. See [ADR-20260809-preserve-fresh-rate-limits](../adrs/ADR-20260809-preserve-fresh-rate-limits.md).

Decision record: [ADR-20260809-account-routed-resume](../adrs/ADR-20260809-account-routed-resume.md).

#### Next Actions

- Restart the LaunchAgent, reselect the intended menu rows, and observe the next fixed boundary.

### ISSUE-06-live-resume-enablement

- status: in_progress
- depends_on: [ISSUE-01-menu-actions, ISSUE-02-scheduler-runtime, ISSUE-03-resume-configuration, ISSUE-05-menu-operability]
- guide_impact: required
- related_guides: [GUIDE-resume-wiring, GUIDE-natural-resume]
- guide_impact_reason: "Live account-routed resume changes the operator-visible scheduler behavior."

#### Goal

Enable the account-routed resume executor for sessions explicitly checked in the menu after the operator's live-launch approval.

#### Acceptance

- The resident runtime constructs the account-routed executor from the validated executable configuration.
- An alias request sets the second `CLAUDE_CONFIG_DIR`; an unknown account is refused.
- Selection remains an explicit in-memory boundary; no unchecked event is launched.
- The next fixed boundary produces only sanitized outcome classifications.
- The menu exposes the latest boundary and aggregate outcome counts without exposing private session data.

#### Current Status

The operator approved live resume after confirming the menu rows. The executor and enriched candidate provider are implemented and unit-tested. The 02:00 JST boundary ran for the selected resident process and local diagnostics showed five rate-limit events completed while one older unmatched event remained. Because the menu previously exposed only selection state, the result was not visible to the operator; the menu now displays the latest poll boundary and aggregate statuses without private identifiers. The resident LaunchAgent was restarted with the operator's approval and is running the updated code; the remaining human check is to open the menu and confirm the summary, then reselect desired rows because selection is intentionally in memory only. Current security hardening additionally isolates account artifacts, refuses unlabeled or duplicate account evidence, and uses descriptor-relative no-follow file operations before any future public release.

#### Next Actions

- Human checkpoint: reselect the intended rows, open the menu, and confirm the latest poll summary is visible. Do not trigger an additional Claude resume solely for this UI check.

### ISSUE-04-wiring-handoff

- status: complete
- depends_on: [ISSUE-01-menu-actions, ISSUE-02-scheduler-runtime, ISSUE-03-resume-configuration]
- guide_impact: required
- related_guides: [GUIDE-resume-wiring]
- guide_impact_reason: "The active runtime's safety behavior requires an operator guide."

#### Goal

Complete guides and the local verification handoff.

#### Acceptance

- All recorded handoff gates pass and any live launch remains behind the explicit verification boundary.

#### Current Status

Configuration and the local handoff verification are complete; the historical disabled-by-policy handoff is distinct from ISSUE-06 live verification.

#### Next Actions

- Stop at `resume-wiring-review` before any live launch.

### ISSUE-05-menu-operability

- status: complete
- depends_on: [ISSUE-01-menu-actions]
- guide_impact: required
- related_guides: [GUIDE-resume-wiring]
- guide_impact_reason: "Candidate selection is an operator-visible safety boundary."

#### Goal

Make the menu-bar owner identifiable and candidate selection visibly reliable before any automatic resume enablement.

#### Acceptance

- The status item identifies AIphetamine.
- A candidate without Hook-provided names still shows a safe project-directory label and short discriminator.
- The AppKit menu uses native checked state and updates it immediately after a toggle.
- No Claude process is launched.

#### Current Status

Operator evidence showed an unlabeled status icon, fallback-only candidate rows, and no visible checked state after clicks. Project paths are valid, while Hook-provided names are absent for the observed candidates. The AppKit adapter now has a labelled status item, safe fallback labels, and an immediate native check-state update; an AppKit test verifies all three without launching Claude.

#### Next Actions

- Live execution is now gated by explicit checked rows and account validation.

## Decisions

Record only decisions that are difficult to reverse or surprising without context.

- The approved owner-only configuration file stores one resolved, executable Claude path; it is used only by checked, account-labeled resume requests.

## Human Review Checkpoint

- Completed: interactive candidate/quit bindings, fixed-boundary scheduler integration, disabled-by-policy executor, executable configuration validator, owner-only configuration creation, and one AIphetamine LaunchAgent restart.
- Final live-resume verification is in progress after the operator's explicit approval.

## Verification

- `python3 -m unittest discover -s tests -v` passes the repository test suite.
- `python3 -m compileall -q src hooks scripts`, `git diff --check`, and the repository docs validator pass.
- The runtime configuration is owner-only and its configured executable passes the read-only validator.
- The LaunchAgent remains running after its one permitted restart.
- The account-routed executor is live and the 02:00 JST boundary produced sanitized local evidence; the UI-result confirmation remains pending until the resident process is restarted with the status display.
- Account-scoped artifacts, duplicate-session ambiguity, malformed account metadata, shell assignment words, and descriptor-relative filesystem operations are covered by local tests.

## Completion

- [x] Every issue meets its acceptance criteria
- [x] Every issue records guide impact as required or none
- [x] Required guides describe current implemented behavior
- [x] Specs reflect any changed direction or requirements
- [x] Next human gate reached or the workstream intentionally stopped
- [x] 00_index.md updated
- [ ] Workstream archived when complete
