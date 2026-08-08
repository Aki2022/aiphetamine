---
schema_version: 2
id: WS-20260721-app-shell
status: active
created_at: 2026-07-21
updated_at: 2026-07-21
branch: main
pr: ""
human_boundary_confirmed_at: 2026-07-21
next_human_gate: app-shell-review
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
related_guides:
  - docs/guides/runtime-core-dry-run.md
test_gates:
  commands:
    - python3 -m unittest discover -s tests -v
    - git diff --check
    - python3 <origin-doc-update-skill>/scripts/validate_repo_docs.py .
  quality:
    - all tests pass
    - dry-run performs no Claude process launch and no filesystem mutation
    - no live Claude Code execution or rate-limit stimulation
    - no secrets, raw session identifiers, prompt/transcript bodies, or local identifying values in output
required_reviewers: []
subagent_plan:
  mode: parent-only
  reason: "The app shell changes shared runtime boundaries and its guide; integration remains parent-owned."
---

# App Shell and Safe Dry Run

## Goal

Expose a minimal local runtime shell and safe dry-run command that can inspect candidate/event state and preview the next fixed poll boundary without launching Claude or mutating event files.

## Success Criteria

- Application startup wiring initializes the three data subdirectories, performs the documented rate-limit cleanup, loads candidates, and computes the next boundary when explicitly invoked.
- Dry-run inspection reads only and emits counts, allowlisted eligibility statuses, and the next boundary; it never claims or deletes event files and never starts a process.
- The dry-run command is directly executable with `python3`, has no dependency installation requirement, and does not print raw paths, session IDs, prompts, transcripts, or subprocess output.
- Tests cover startup cleanup, next-boundary reporting, dry-run immutability, and CLI-safe output.
- Natural rate-limit Hook behavior remains deferred and no live Claude action is performed.

## Authorization Envelope

- Approved scope: repository-local application runtime wiring, read-only dry-run command, synthetic temporary-directory tests, guide updates, and docs validation.
- Autonomous actions allowed: code/test/docs edits within the repository, temporary test filesystem operations, and free local validation commands.
- Confirm first: any live Claude Code execution; any rate-limit-related test or event capture; Claude Code settings or Hook configuration changes; writes outside the repository or temporary test directories; network access; authentication or secret handling; dependency installation; destructive operations; branch creation, commit, push, PR, release, deployment, UI/AppKit, LaunchAgent, or packaging work.
- Cost or usage ceiling: no metered service use; zero live Claude Code calls; zero network calls; no dependency installation.
- Out of scope: actual Claude subprocess launch, production Hook installation, macOS menu bar UI, LaunchAgent, packaging, deployment, and changes to PRD deferred decisions.

## Human Gates

- Start gate: confirmed on 2026-07-21
- Next gate: app-shell-review
- Stop conditions: stop before any confirm-first action; stop if a user-facing behavior requires a spec decision or external integration; stop if a test or validator fails after three same-root-cause attempts.

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-runtime-wiring | complete | none | Startup snapshot and preview orchestration |
| ISSUE-02-safe-dry-run | complete | ISSUE-01 | Read-only CLI with sanitized output |
| ISSUE-03-app-shell-integration | complete | ISSUE-01, ISSUE-02 | Tests, guide, and human-gate handoff |

### ISSUE-01-runtime-wiring

- status: complete
- depends_on: []
- guide_impact: required
- related_guides: [GUIDE-runtime-core-dry-run]
- guide_impact_reason: "The runtime shell exposes an operator-visible startup and preview contract documented by the guide."

#### Goal

Wire startup state inspection, explicit startup cleanup, next-boundary calculation, and read-only poll preview around the existing runtime core.

#### Acceptance

- Explicit startup creates/reuses only the app data subdirectories and cleans rate-limit artifacts according to the architecture contract.
- Startup does not run a poll cycle immediately.
- Preview reports safe counts/statuses and does not mutate files or invoke an executor.

#### Current Status

Implemented in `src/aiphetamine/app_runtime.py` and `src/aiphetamine/resume_service.py`. Explicit startup initializes directories and cleanup; dry-run preview remains read-only and does not launch an executor.

#### Next Actions

- Covered by startup and dry-run immutability tests.

### ISSUE-02-safe-dry-run

- status: complete
- depends_on: [ISSUE-01-runtime-wiring]
- guide_impact: required
- related_guides: [GUIDE-runtime-core-dry-run]
- guide_impact_reason: "The dry-run command is a user/operator-visible command and needs current usage and limitation documentation."

#### Goal

Provide a `python3` dry-run command that emits only sanitized inspection results.

#### Acceptance

- Command accepts an optional data root and defaults to the documented local data root.
- Output contains no raw identifiers, paths, prompts, transcripts, or process output.
- Command never invokes Claude and leaves input files byte-for-byte unchanged.

#### Current Status

Implemented in `scripts/run_dry_cycle.py`. The command emits only mode, counts, next boundary, and allowlisted status counts.

#### Next Actions

- Guide updated in `docs/guides/runtime-core-dry-run.md`; command execution is tested with a temporary data root.

### ISSUE-03-app-shell-integration

- status: complete
- depends_on: [ISSUE-01-runtime-wiring, ISSUE-02-safe-dry-run]
- guide_impact: required
- related_guides: [GUIDE-runtime-core-dry-run]
- guide_impact_reason: "Integration changes the documented dry-run contract and verification procedure."

#### Goal

Complete local integration tests and hand off the safe dry-run shell for human review.

#### Acceptance

- All tests and docs gates pass.
- Guide describes current behavior and explicitly states that this is not yet an installable MVP.
- Natural rate-limit verification remains deferred.

#### Current Status

The full app-shell test suite and documentation gates pass. The implementation is ready for the `app-shell-review` human gate.

#### Next Actions

- All local gates pass; hand off at `app-shell-review`.

## Human Review Checkpoint

- Local app-shell scope is complete: startup wiring, read-only dry-run preview, sanitized CLI output, guide, 34 tests, `git diff --check`, and docs validation are complete.
- The current workstream must stop before the next action because the recorded envelope excludes live Claude execution, Claude Code settings or Hook changes, external writes, UI/AppKit, LaunchAgent, and packaging.
- The next recommended bounded action is one separately approved non-rate-limit Claude CLI E2E using transient settings and a fixed harmless message, with no intentional rate-limit stimulation and no raw output retention.
- Human decision required: approve the next workstream for that single non-rate-limit CLI E2E, or choose to prioritize Hook configuration, macOS UI, or LaunchAgent work instead.

## Verification

- `python3 -m unittest discover -s tests -v` passes 34 tests.
- `git diff --check` passes.
- Repository docs validator passes.
- Dry-run output contains no raw identifiers or paths, and no Claude process was started.

## Decisions

- The app shell proceeds while rate-limit verification remains deferred by explicit human decision.
- Dry-run is read-only and does not prove Claude runtime behavior.
- The guide is required because the command is operator-visible even though the full MVP is not yet runnable.
- The app shell is complete for safe local inspection, but it is not yet an installable or user-runnable MVP.

## Completion

- [x] Every issue meets its acceptance criteria
- [x] Every issue records guide impact as required or none
- [x] Required guides describe current implemented behavior
- [x] Specs reflect any changed direction or requirements
- [x] Next human gate reached or the workstream intentionally stopped
- [x] 00_index.md updated
- [ ] Workstream archived when complete
