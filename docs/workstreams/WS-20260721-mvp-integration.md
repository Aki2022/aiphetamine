---
schema_version: 2
id: WS-20260721-mvp-integration
status: active
created_at: 2026-07-21
updated_at: 2026-07-21
branch: main
pr: ""
human_boundary_confirmed_at: 2026-07-21
next_human_gate: mvp-integration-review
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
related_guides:
  - docs/guides/mvp-runtime.md
  - docs/guides/hook-setup.md
test_gates:
  commands:
    - python3 -m unittest discover -s tests -v
    - python3 -m compileall -q src hooks scripts
    - plutil -lint <generated-launchagent-plist>
    - git diff --check
    - python3 <origin-doc-update-skill>/scripts/validate_repo_docs.py .
  quality:
    - no live Claude Code execution, production Hook application, or LaunchAgent registration
    - no network access, dependency installation, or writes outside the repository and temporary test directories
    - UI behavior is verified through isolated AppKit adapters and unit tests
    - logs and generated artifacts retain no raw session IDs, prompt/transcript bodies, authentication values, usernames, or local absolute paths
required_reviewers: []
subagent_plan:
  mode: parent-only
  reason: "UI, runtime, installer, and documentation share service boundaries and are integrated by the parent agent."
---

# MVP Integration

## Goal

Deliver a locally runnable macOS menu-bar MVP that integrates the existing event-processing core with fixed two-hour scheduling, sanitized seven-day logs, optional Launch at Login artifacts, and generated Claude Hook configuration instructions without applying any production integration.

## Success Criteria

- A menu-bar controller presents candidate sessions, preserves in-memory activation state, and exposes Launch at Login and Quit actions through isolated AppKit adapters.
- A one-shot scheduler schedules only the next even-hour boundary, delegates work off the UI thread, and reschedules after each run or wake notification.
- Sanitized rotating logs retain at most seven daily backups and never retain sensitive session or filesystem values.
- LaunchAgent plist generation, validation, status inspection, and non-registering install/uninstall commands are testable without changing user LaunchAgent state.
- Hook scripts atomically create, refresh, and remove candidate/event records; settings fragments and manual merge, verification, and removal instructions are generated without editing Claude settings.
- Guides describe the manual startup, Hook setup, and the explicit production-application boundaries.

## Authorization Envelope

- Approved scope: macOSメニューバーUI、固定時刻スケジューラ、7日ログ、LaunchAgent、Claude Hook設定断片と手動導入手順を、実本番適用なしで統合する。
- Autonomous actions allowed: repository-local code, tests, guides, generated configuration fragments, and install/uninstall scripts; temporary-directory filesystem tests; local static validation including plist syntax checks.
- Confirm first: LaunchAgent registration or deregistration; editing or merging Claude settings; any Claude CLI execution, production Hook application, or rate-limit test; dependency installation; network access; authentication or secret handling; writes outside this repository or test temporary directories; destructive operations; commit, push, PR, release, deployment, or packaging.
- Cost or usage ceiling: no metered work is permitted; zero network calls, zero Claude CLI calls, zero dependency installations, zero production integration writes, parent-only execution, and at most three consecutive attempts for any same-root-cause failure.
- Out of scope: actual LaunchAgent registration, editing any Claude settings file, live Hook/rate-limit verification, Claude subprocess execution, package installation, signed distribution, release, deployment, and Git publication.

## Human Gates

- Start gate: confirmed on 2026-07-21
- Next gate: mvp-integration-review
- Stop conditions: stop at `mvp-integration-review`; stop immediately before any confirm-first action, if an unavailable dependency is required, if scope expands beyond the listed MVP integration, or after three same-root-cause failures.

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-runtime-observability | complete | none | Sanitized logging and application integration seam |
| ISSUE-02-boundary-scheduler | complete | ISSUE-01 | One-shot even-hour scheduling with UI-safe dispatch |
| ISSUE-03-menu-bar-ui | complete | ISSUE-01, ISSUE-02 | AppKit-isolated session menu and actions |
| ISSUE-04-local-integration-artifacts | complete | ISSUE-01 | LaunchAgent and Hook fragment generation without production application |
| ISSUE-05-mvp-handoff | complete | ISSUE-02, ISSUE-03, ISSUE-04 | Guides, full verification, and human review handoff |

### ISSUE-01-runtime-observability

- status: complete
- depends_on: []
- guide_impact: required
- related_guides: [GUIDE-mvp-runtime]
- guide_impact_reason: "Manual startup and diagnostic behavior become operator-visible."

#### Goal

Add a safe logging boundary and runtime composition seam that can be used by the scheduler and menu controller without exposing sensitive input values.

#### Acceptance

- Seven-day rotation and allowlisted event/error logging are unit tested.
- Runtime composition can refresh candidates and run the existing poll cycle through injected dependencies.
- No subprocess output, raw identifiers, paths, prompts, transcripts, or authentication values are logged.

#### Current Status

Implemented in `src/aiphetamine/runtime_logging.py` and `src/aiphetamine/app_runtime.py`; the runtime logs only allowlisted fields and invokes the existing poll cycle through an injected executor.

#### Next Actions

- Covered by `tests/test_runtime_logging.py`.

### ISSUE-02-boundary-scheduler

- status: complete
- depends_on: [ISSUE-01-runtime-observability]
- guide_impact: required
- related_guides: [GUIDE-mvp-runtime]
- guide_impact_reason: "The fixed scheduling and wake behavior affects manual app operation."

#### Goal

Integrate a one-shot fixed-boundary scheduler with explicit UI-loop and worker-dispatch ports.

#### Acceptance

- Startup schedules the next future even-hour boundary without running a cycle immediately.
- Each callback runs one cycle off the UI thread and reschedules from current local time.
- Wake reschedules without replaying missed cycles.
- Unit tests cover scheduling, callback, overlap prevention, and wake behavior without AppKit execution.

#### Current Status

Implemented in `src/aiphetamine/boundary_scheduler.py` with timer and worker ports that avoid GUI startup in tests.

#### Next Actions

- Covered by `tests/test_boundary_scheduler.py`.

### ISSUE-03-menu-bar-ui

- status: complete
- depends_on: [ISSUE-01-runtime-observability, ISSUE-02-boundary-scheduler]
- guide_impact: required
- related_guides: [GUIDE-mvp-runtime]
- guide_impact_reason: "The menu rows, activation behavior, and Launch at Login control are user-visible."

#### Goal

Create a minimal AppKit-backed menu bar controller with a testable presentation model.

#### Acceptance

- Candidate rows are sanitized, bounded, and show activation and allowed status labels.
- User actions change only in-memory selection state and request scheduler/UI refresh through services.
- AppKit imports are isolated so unit tests run without launching a GUI.
- Quit and Launch at Login actions are represented but do not register any LaunchAgent in tests.

#### Current Status

Implemented as pure models/controller plus an optional AppKit adapter. The adapter remains unavailable until a human installs PyObjC and starts the application.

#### Next Actions

- Covered by `tests/test_menu_models.py`; no GUI was launched.

### ISSUE-04-local-integration-artifacts

- status: complete
- depends_on: [ISSUE-01-runtime-observability]
- guide_impact: required
- related_guides: [GUIDE-mvp-runtime, GUIDE-hook-setup]
- guide_impact_reason: "Generated local artifacts and the manual integration procedure are operator-visible."

#### Goal

Generate and validate LaunchAgent and Claude Hook configuration artifacts without registering, editing, or applying them.

#### Acceptance

- LaunchAgent plist generation and status inspection are testable and do not invoke registration commands.
- Hook scripts atomically write/remove only the specified local event records and emit only allowlisted errors.
- Generated settings fragment is valid JSON and never edits an existing Claude settings file.
- Manual merge, verification, and removal steps are documented.

#### Current Status

Implemented in `src/aiphetamine/launch_agent.py`, `src/aiphetamine/hook_setup.py`, `hooks/aiphetamine_hook.py`, and `scripts/generate_hook_config.py`.

#### Next Actions

- Covered by artifact and Hook tests; no settings or LaunchAgent state was changed.

### ISSUE-05-mvp-handoff

- status: complete
- depends_on: [ISSUE-02-boundary-scheduler, ISSUE-03-menu-bar-ui, ISSUE-04-local-integration-artifacts]
- guide_impact: required
- related_guides: [GUIDE-mvp-runtime, GUIDE-hook-setup]
- guide_impact_reason: "The integrated local MVP requires current operator instructions and limitations."

#### Goal

Finish guides, run all local gates, and hand off the implementation before any production integration.

#### Acceptance

- Both guides describe current behavior, verification, and confirm-first production steps.
- All recorded gates pass, including generated plist validation.
- The workstream records that live Claude, production Hooks, and LaunchAgent registration remain unperformed.

#### Current Status

Guides and local verification are complete; the workstream is ready for the human gate.

#### Next Actions

- Stop at `mvp-integration-review` before production integration.

## Decisions

- Work continues without resolving the inconclusive live CLI result because all workstream acceptance is local and no live Claude execution is permitted.
- AppKit behavior must be isolated behind ports so the test suite does not require GUI startup or PyObjC installation.
- The user owns all production integration: LaunchAgent registration and removal, Claude settings merge, and live Hook verification.

## Human Review Checkpoint

- Repository-local MVP integration is complete: sanitized logging, one-shot scheduling, menu models/controller, optional AppKit adapter, LaunchAgent plist generation, Hook fragment generation, and atomic Hook record handling are implemented and tested.
- No dependency was installed, no GUI was launched, no LaunchAgent was registered, no Claude settings were read or edited, and no Claude process or rate-limit test was run.
- Human decision required: approve a separate production-integration workstream for PyObjC installation, manual Hook settings merge, LaunchAgent registration, and any live verification; or keep this repository-local implementation only.

## Verification

- `python3 -m unittest discover -s tests -v` passes 46 tests.
- `python3 -m compileall -q src hooks scripts` passes.
- Generated LaunchAgent plist passes `plutil -lint`.
- `git diff --check` passes.
- Repository docs validator passes without warnings.

## Completion

- [x] Every issue meets its acceptance criteria
- [x] Every issue records guide impact as required or none
- [x] Required guides describe current implemented behavior
- [x] Specs reflect any changed direction or requirements
- [x] Next human gate reached or the workstream intentionally stopped
- [x] 00_index.md updated
- [ ] Workstream archived when complete
