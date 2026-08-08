---
schema_version: 2
id: WS-20260721-phase1-foundation
status: active
created_at: 2026-07-21
updated_at: 2026-07-21
branch: main
pr: ""
human_boundary_confirmed_at: 2026-07-21
next_human_gate: phase1-foundation-review
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
    - no secrets, raw session identifiers, prompt/transcript bodies, or local identifying values in evidence
    - implementation remains within the PRD and architecture contracts
required_reviewers: []
subagent_plan:
  mode: parent-only
  reason: "Shared implementation and documentation are small and must be integrated by the parent agent."
---

# Phase 1 Foundation

## Goal

Implement and test the local Phase 1 foundation for candidate ingestion, in-memory activation, fixed two-hour boundaries, and safe resume eligibility decisions while the natural rate-limit Hook verification remains deferred.

## Success Criteria

- Candidate and rate-limit JSON can be read, validated, deduplicated, and safely classified without exposing raw values in logs or evidence.
- Candidate freshness, project-path matching, in-memory activation, and 12-hour expiry decisions follow the active PRD and architecture contracts.
- Fixed two-hour boundary calculation is deterministic and handles exact boundaries, day rollover, and timezone-aware inputs.
- Resume eligibility is decided locally from repository data and activation state; no Claude process is started in this workstream.
- Tests cover accepted, rejected, expired, mismatched, and non-selected cases before implementation is marked complete.
- Phase 0 ISSUE-03 remains explicitly deferred and no claim is made about natural rate-limit Hook behavior.

## Authorization Envelope

- Approved scope: repository-local Phase 1 foundation for JSON repositories, candidate and rate-limit event models, in-memory selection state, fixed boundary scheduling, local resume eligibility decisions, and tests.
- Autonomous actions allowed: repository code and test edits, workstream/index documentation updates, fixture creation with synthetic non-sensitive values, and free local validation commands.
- Confirm first: any live Claude Code execution; any rate-limit-related test or event capture; Claude Code settings or Hook configuration changes; external writes; network access; authentication or secret handling; dependency installation; destructive operations; branch creation, commit, push, PR, release, deployment, or UI/AppKit implementation.
- Cost or usage ceiling: no metered service use; zero live Claude Code calls; zero network calls; no dependency installation.
- Out of scope: natural rate-limit observation, production Hook installation, Claude subprocess execution, macOS menu bar UI, scheduler runtime integration, LaunchAgent, packaging, deployment, and changes to active product requirements.

## Human Gates

- Start gate: confirmed on 2026-07-21
- Next gate: phase1-foundation-review
- Stop conditions: stop before any confirm-first action; stop if implementation requires a spec decision, dependency, network access, live Claude behavior, or production data-directory access; stop if a test or validator fails after three same-root-cause attempts.

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-domain-repositories | complete | none | Safe domain models and read-only JSON repositories |
| ISSUE-02-selection-scheduling | complete | ISSUE-01 | In-memory activation and deterministic fixed-boundary scheduling |
| ISSUE-03-resume-eligibility | complete | ISSUE-01, ISSUE-02 | Local resume eligibility decision without process execution |
| ISSUE-04-foundation-integration | complete | ISSUE-01, ISSUE-02, ISSUE-03 | Integrated tests, docs alignment, and human-gate handoff |

### ISSUE-01-domain-repositories

- status: complete
- depends_on: []
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Repository-local foundation only; no packaged user or operator workflow exists yet."

#### Goal

Define safe domain records and read-only repositories for candidate snapshots and rate-limit events.

#### Acceptance

- Required fields and timestamps are validated.
- Candidate freshness and file-name/session-key integrity are enforced.
- Invalid, stale, symlink, and malformed records are skipped or classified without echoing raw values.
- Tests are written before or with the implementation.

#### Current Status

Implemented in `src/aiphetamine/domain.py` and `src/aiphetamine/repositories.py`. Tests cover valid records, session-key filenames, malformed records, stale/future timestamps, wrong record types, and symlink rejection.

#### Next Actions

- Run the complete workstream gates after the documentation update.

### ISSUE-02-selection-scheduling

- status: complete
- depends_on: [ISSUE-01-domain-repositories]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "In-memory foundation and pure scheduling logic are not yet a packaged user workflow."

#### Goal

Implement non-persistent activation state with 12-hour expiry and deterministic two-hour local-time boundaries.

#### Acceptance

- New candidates remain OFF until explicitly activated.
- Activation survives event-file removal/recreation only in memory and expires after 12 hours.
- Boundary calculation does not run work immediately at startup and handles day rollover.
- Tests cover exact boundaries, rollover, expiry, activation, deactivation, and missing candidates.

#### Current Status

Implemented in `src/aiphetamine/selection.py` and `src/aiphetamine/scheduling.py`. Activation is ephemeral, expires after 12 hours, captures project identity, and boundary calculation skips the current boundary.

#### Next Actions

- Covered by the foundation test suite; no runtime timer or UI integration is included.

### ISSUE-03-resume-eligibility

- status: complete
- depends_on: [ISSUE-01-domain-repositories, ISSUE-02-selection-scheduling]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Only local eligibility decisions are implemented; no Claude process is launched."

#### Goal

Decide whether a rate-limit event is eligible for resume using candidate identity, project path, freshness, activation, expiry, and processing state.

#### Acceptance

- Only selected, non-expired, fresh, path-matching candidates can produce an eligible decision.
- Invalid or mismatched events are rejected with allowlisted classifications.
- The decision layer does not launch subprocesses, write settings, or delete/claim production files.
- Tests cover selected/unselected, expired, stale, mismatched, malformed, processing, and eligible cases.

#### Current Status

Implemented in `src/aiphetamine/resume.py`. Decisions require selection, freshness, non-expiry, event/candidate path identity, project identity, and absence from the processing set; the layer never launches Claude.

#### Next Actions

- Covered by the foundation test suite; live resume behavior remains documented in the Phase 0 workstream.

### ISSUE-04-foundation-integration

- status: complete
- depends_on: [ISSUE-01-domain-repositories, ISSUE-02-selection-scheduling, ISSUE-03-resume-eligibility]
- guide_impact: none
- related_guides: []
- guide_impact_reason: "Phase 1 remains an un-packaged local foundation; no current guide is required."

#### Goal

Run the complete local test and documentation gates and leave a precise handoff for human review.

#### Acceptance

- All agreed tests pass.
- `git diff --check` and the repository docs validator pass.
- Documentation distinguishes implemented local logic from unverified live Claude behavior.
- The natural rate-limit verification remains deferred without artificial stimulation.

#### Current Status

The integrated foundation test suite passes 23 tests. Documentation and repository-wide gates also pass. The implementation is ready for the `phase1-foundation-review` human gate.

#### Next Actions

- All local gates pass; hand off at `phase1-foundation-review`.

## Decisions

- Phase 1 foundation starts before natural rate-limit evidence is available, under the explicit human approval on 2026-07-21.
- No live Claude Code invocation, rate-limit stimulation, Hook configuration change, or external write is part of this workstream.
- `CLAUDE_CONFIG_DIR` account isolation is already verified in the Phase 0 workstream and is not repeated here.
- The Phase 1 foundation is complete for local repository, selection, scheduling, and eligibility logic; Claude subprocess execution and rate-limit re-creation remain outside this workstream.

## Completion

- [x] Every issue meets its acceptance criteria
- [x] Every issue records guide impact as required or none
- [x] Required guides describe current implemented behavior (no guide required for the un-packaged foundation)
- [x] Specs reflect any changed direction or requirements
- [x] Next human gate reached or the workstream intentionally stopped
- [x] 00_index.md updated
- [ ] Workstream archived when complete
