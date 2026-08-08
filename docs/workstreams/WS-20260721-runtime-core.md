---
schema_version: 2
id: WS-20260721-runtime-core
status: active
created_at: 2026-07-21
updated_at: 2026-07-21
branch: main
pr: ""
human_boundary_confirmed_at: 2026-07-21
next_human_gate: runtime-core-review
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
    - all tests pass
    - no live Claude Code execution or rate-limit stimulation
    - no Claude settings changes, network calls, dependencies, or production data-directory writes
    - no secrets, raw session identifiers, prompt/transcript bodies, or local identifying values in evidence
required_reviewers: []
subagent_plan:
  mode: parent-only
  reason: "The runtime core crosses repository and service boundaries; shared-file integration remains parent-owned."
---

# Runtime Core

## Goal

Implement the local runtime core that connects the Phase 1 eligibility foundation to safe event-file processing and fixed resume command construction, while the natural rate-limit Hook verification remains deferred.

## Success Criteria

- Rate-limit event files can be atomically claimed, completed, restored, and cleaned up without overwriting a newly recreated event.
- Startup cleanup only removes rate-limit event artifacts and leaves candidate snapshots untouched.
- The poll-cycle service evaluates eligible events, claims them, invokes an injected executor, and completes or restores files according to the executor result.
- The resume command adapter produces the fixed `claude -p --resume SESSION_ID Continue` argument contract with `shell=False`, project cwd, and no output capture; it is tested without launching Claude.
- Synthetic local integration tests cover success, launch failure, exception, processing conflict, event recreation, and startup cleanup.
- No live Claude behavior is claimed, and ISSUE-03 natural rate-limit verification remains deferred.

## Authorization Envelope

- Approved scope: repository-local atomic event-file operations, local poll-cycle orchestration, injected resume executor contract, fixed command construction, synthetic fixtures, tests, and documentation updates.
- Autonomous actions allowed: code/test edits within the repository, docs/workstream/index updates, synthetic local filesystem operations inside temporary directories, and free local validation commands.
- Confirm first: any live Claude Code execution; any rate-limit-related test or event capture; Claude Code settings or Hook configuration changes; writes outside the repository or temporary test directories; network access; authentication or secret handling; dependency installation; destructive operations; branch creation, commit, push, PR, release, deployment, UI/AppKit, LaunchAgent, or packaging work.
- Cost or usage ceiling: no metered service use; zero live Claude Code calls; zero network calls; no dependency installation.
- Out of scope: natural rate-limit observation, production Hook installation, actual Claude subprocess launch, macOS menu bar UI, LaunchAgent, packaging, deployment, and changes to PRD deferred decisions.

## Human Gates

- Start gate: confirmed on 2026-07-21
- Next gate: runtime-core-review
- Stop conditions: stop before any confirm-first action; stop if the implementation requires live Claude behavior or a product/spec decision; stop if a test or validator fails after three same-root-cause attempts.

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-event-operations | complete | none | Atomic claim, complete, restore, and cleanup for local event files |
| ISSUE-02-resume-adapter | complete | ISSUE-01 | Fixed resume command construction and injected executor contract |
| ISSUE-03-poll-cycle | complete | ISSUE-01, ISSUE-02 | Local poll-cycle orchestration and integration handoff |

### ISSUE-01-event-operations

- status: complete
- depends_on: []
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Internal runtime core only; no packaged operator workflow is exposed yet."

#### Goal

Add safe atomic operations to the rate-limit event repository.

#### Acceptance

- `claim` uses same-directory atomic rename and skips already-claimed files.
- `complete` removes only the claimed artifact.
- `restore` returns failed work to `.json`, preserving a concurrently recreated JSON.
- Startup cleanup removes rate-limit artifacts while leaving candidates intact.
- Tests use temporary directories only.

#### Current Status

Implemented in `src/aiphetamine/repositories.py`. Atomic claim, complete, restore, recreated-event preservation, and startup cleanup are covered by temporary-directory tests.

#### Next Actions

- Covered by the runtime-core test suite; no production data directory was touched.

### ISSUE-02-resume-adapter

- status: complete
- depends_on: [ISSUE-01-event-operations]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Command construction is tested as an internal adapter; no user-facing execution command is published."

#### Goal

Implement the fixed resume command adapter and injected launch-result contract without running Claude.

#### Acceptance

- Arguments are fixed to the approved session ID, `Continue`, and verified cwd.
- `shell=False`, `DEVNULL` streams, and detached-session settings are represented in the launch contract.
- Raw output, prompt bodies, local paths, and identifiers are never logged or returned as evidence.
- Tests use a fake process factory and never start an external process.

#### Current Status

Implemented in `src/aiphetamine/executor.py` and `src/aiphetamine/domain.py`. The fixed command contract is tested with an injected process factory; no external process was started.

#### Next Actions

- Covered by the runtime-core test suite; actual Claude launch remains out of scope.

### ISSUE-03-poll-cycle

- status: complete
- depends_on: [ISSUE-01-event-operations, ISSUE-02-resume-adapter]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "The service is a local un-packaged core; UI and operator procedures remain out of scope."

#### Goal

Connect repository records, selection state, eligibility decisions, event claiming, and injected executor results into one deterministic poll cycle.

#### Acceptance

- Unselected, stale, mismatched, and already-processing events are not claimed.
- A successful injected launch completes the claimed event.
- A failed or exceptional injected launch restores the claimed event.
- A recreated JSON event wins over restoring an older `.processing` artifact.
- Integration tests and docs gates pass with no live Claude action.

#### Current Status

Implemented in `src/aiphetamine/resume_service.py`. The poll cycle connects repositories, eligibility, atomic event operations, and injected launch results.

#### Next Actions

- Covered by success, launch failure, exception, and recreated-event integration tests.

## Verification

- `python3 -m unittest discover -s tests -v` passes 31 tests.
- `git diff --check` passes.
- Repository docs validator passes.
- No live Claude Code process was started and no rate-limit event was induced or captured.

## Decisions

- Runtime core proceeds while rate-limit Hook verification remains deferred by explicit human decision.
- Actual Claude process launch is excluded; injected fakes establish only local orchestration behavior.
- The existing Phase 1 workstream remains the source of truth for repository, selection, scheduling, and eligibility contracts.
- Runtime core is complete for local orchestration and ready for the `runtime-core-review` human gate; it is not yet an installable or user-runnable MVP.

## Completion

- [x] Every issue meets its acceptance criteria
- [x] Every issue records guide impact as required or none
- [x] Required guides describe current implemented behavior (no guide required for the un-packaged core)
- [x] Specs reflect any changed direction or requirements
- [x] Next human gate reached or the workstream intentionally stopped
- [x] 00_index.md updated
- [ ] Workstream archived when complete
