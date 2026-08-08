---
schema_version: 2
id: WS-20260720-phase0-technical-spikes
status: active
created_at: 2026-07-20
updated_at: 2026-07-21
branch: WS-20260720-phase0-technical-spikes
pr: ""
human_boundary_confirmed_at: 2026-07-20
next_human_gate: phase0-results-review
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
    - evidence contains no secrets, prompt/transcript bodies, local absolute paths, usernames, or raw session identifiers
    - specs remain consistent with the evidence
required_reviewers: []
subagent_plan:
  mode: parent-only
  reason: "ISSUE-01 is a small repository-local fixture harness; shared-file writes and integration remain parent-owned."
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
- Candidate-lifecycle live run approved on 2026-07-21: transient Hook settings only, with an ephemeral candidate root inside this repository that is removed after evidence collection
- Cost or usage ceiling: no metered API use by default. One minimal non-interactive second-account execution was explicitly approved on 2026-07-21; usable token or price telemetry was unavailable, so no currency spend is claimed. Never intentionally drive Claude to a rate limit; rate-limit-related tests require human approval each time and must use naturally occurring events
- Out of scope: MVP production implementation, menu bar UI, scheduler, LaunchAgent installation, automatic Hook configuration changes, package installation, publishing, and deployment

## Human Gates

- Start gate: confirmed on 2026-07-20
- Next gate: phase0-results-review
- Stop conditions: stop before every confirm-first action; stop if a secret or local identifying value may be exposed; stop if observed behavior contradicts an active spec; stop if a required live event is unavailable; stop if a new dependency, network access, or metered use appears necessary

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-spike-harness | complete | none | Safe fixture-driven payload capture and redaction harness |
| ISSUE-02-candidate-lifecycle | complete | ISSUE-01 | Candidate discovery, refresh, and end behavior evidence |
| ISSUE-03-rate-limit-hook | blocked | ISSUE-01 | Approved real-event rate-limit behavior evidence |
| ISSUE-04-resume-behavior | complete | ISSUE-01 | Approved official resume and process-conflict evidence |
| ISSUE-05-consolidate-results | complete | ISSUE-02, ISSUE-03, ISSUE-04 | Evidence matrix, spec alignment, and human-gate report |

### ISSUE-01-spike-harness

- status: complete
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

Completed for fixture/unit evidence. The harness validates the minimum payload shape and emits only safe field-presence and allowlisted classification evidence. No live Claude Code payload was captured.

#### Evidence

- Fixture/unit verified: required `session_id`, `cwd`, `transcript_path`, and event-type fields are accepted only when non-empty text; missing and invalid fields receive separate safe error codes.
- Fixture/unit verified: `reason` is classified as `rate_limit`, `other`, `missing`, or `invalid`; arbitrary event names, session names, paths, prompts, tokens, and identifiers are not retained in evidence.
- Live environment: unverified. This slice does not edit Claude Code settings, invoke Hooks, access the network, or run Claude Code.
- Verification: `python3 -m unittest discover -s tests -v` passes 14 tests.

#### Implementation

- `src/aiphetamine/spikes/hook_payload.py`
- `tests/test_hook_payload.py`

#### Next Actions

- Full workstream test and docs validation gates passed.
- ISSUE-02 live evidence captured; continue only with the separately approved ISSUE-03 and ISSUE-04 protocols.

### ISSUE-02-candidate-lifecycle

- status: complete
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

Completed with real Hook payload evidence for event availability, field shape, and an ephemeral candidate snapshot lifecycle. The live lifecycle writer validates event-driven create, refresh, and explicit end deletion without writing to the production data directory. PATH lookup does not resolve the Claude CLI; a direct executable lookup reports Claude Code 2.1.215.

#### Evidence

- Environment inspection: `claude --version` on PATH is unavailable; a direct executable invocation reports version 2.1.215. A separate installed candidate fails because Node is unavailable.
- Environment inspection: existing user settings contain Hook event entries, but this workstream has not modified or persisted them.
- Repository-local preparation: `hooks/capture_sanitized_payload.py` reads one Hook stdin JSON and emits only the ISSUE-01 safe evidence contract; it performs no network access and no file writes.
- Live attempt 1: the approved one-time invocation exited with code 1, emitted no sanitized evidence records, and did not modify settings. Read-only `claude doctor` classified the root cause as missing `claude.ai` subscription authentication; no Hook payload was received.
- Authentication follow-up: the exact direct CLI now reports `loggedIn: true`, `authMethod: claude.ai`, and a team subscription. Account email and organization identifiers were inspected locally but not persisted.
- Live attempt 2: after the intended account was confirmed and a second approval was given, the transient-settings invocation again exited with code 1 and emitted no sanitized evidence records. The failure cause is not yet classified because raw stderr was intentionally discarded; no settings were modified.
- Live diagnostic correction: user-provided stderr shows the CLI rejected every recent diagnostic invocation before starting Claude because `--print` with `--output-format=stream-json` requires `--verbose`. No Hook or authentication failure was established by those invocations.
- Prior `transient_settings_or_hook_config` classifications are superseded by this evidence and were incorrect; the failure was a command-line validation error caused by the missing `--verbose` flag.
- The capture adapter remedies (stderr evidence and self-resolving `src`) were live-verified after adding `--verbose`.
- Repository-local preparation: `hooks/capture_candidate_lifecycle.py` writes only safe digest/boolean candidate snapshots to a run-local temporary directory and records allowlisted lifecycle transitions; `scripts/run_candidate_lifecycle_spike.py` removes that directory after collection.
- Account boundary: the primary and second Claude Code configuration directories were inspected through the official `CLAUDE_CONFIG_DIR` override. Both reported authenticated `claude.ai` status; a local comparison confirmed that they represent distinct accounts without retaining either identity value.
- Second-account follow-up: the user-approved, minimal safe-mode non-interactive execution succeeded with `claude_exit=0` and a non-error result record. Only allowlisted stream type names were observed; no response, identity, authentication value, or Hook payload was retained. The observed `rate_limit_event` stream type is not a `StopFailure` Hook payload and does not satisfy ISSUE-03.
- Browser navigation was unnecessary. No logout, account switch, login submission, magic link, or authentication value was used or persisted.
- Live environment: event availability, payload fields, candidate creation, activity refresh, and explicit end behavior verified in the approved ephemeral lifecycle run. Production candidate path/schema integration remains out of scope for this spike.

#### Live Evidence

- Approved live run: `claude_exit=0`; no settings file was modified, no rate limit was triggered, and no resume command was run.
- Observed Hook names: `SessionStart:startup`, `UserPromptSubmit`, and `Stop`.
- Six sanitized evidence records were emitted by the capture adapter. Each retained only field-presence booleans and allowlisted classifications; no session ID, path, prompt, transcript, or account value was persisted.
- Verified payload fields: `session_id`, `cwd`, `transcript_path`, and `hook_event_name` were present and non-empty. Normal lifecycle events had no failure reason (`failure_reason_class=missing`).
- Candidate lifecycle classification: candidate creation — verified; activity refresh — verified by revision `1` to `2`; explicit end removal — verified by `SessionEnd` and final candidate file count `0`.
- Approved lifecycle run: `claude_exit=0`; observed Hook payload event classes were `SessionStart`, `UserPromptSubmit`, `Stop`, and `SessionEnd`. Safe actions were `upsert`, `upsert`, `ignored`, and `remove`; no rate limit was intentionally triggered.

#### Next Actions

- No further ISSUE-02 live action is required. ISSUE-03 rate-limit behavior remains deferred; ISSUE-04 resume behavior is complete for the approved process scenarios.
- No second-account browser check is required: Claude Code configuration isolation, authenticated distinct-account status, and one approved non-interactive execution are verified.

### ISSUE-03-rate-limit-hook

- status: blocked
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

Blocked pending a naturally occurring event and explicit human approval.

The capture harness now supports an optional, ephemeral `AIPHEMETINE_CAPTURE_SALT`. When supplied for a single approved run, evidence includes only a 12-character salted SHA-256 digest for same-session comparison; without the salt, no session correlation value is emitted.

An approved resume run also emitted the stream type `rate_limit_event`, but it did not produce a `StopFailure` Hook payload or a classified failure reason. This observation alone does not satisfy the rate-limit acceptance criteria and no rate limit was intentionally triggered.

#### Protocol

- Never intentionally drive Claude Code to a rate limit.
- Before each live run, confirm that a natural rate-limit event is available or that an already rate-limited session is being tested, and obtain explicit approval for that run.
- Attach `python3 hooks/capture_sanitized_payload.py` to the relevant `StopFailure` Hook through transient settings only. Keep Hook stdout empty and collect only sanitized stderr/stream evidence.
- Supply a fresh run-local `AIPHEMETINE_CAPTURE_SALT` through `env`; never persist the salt or raw payload.
- Mark payload availability, `failure_reason_class`, same-session digest continuity, and event recreation as verified, contradicted, or unverified.

#### Next Actions

- Wait for a natural rate-limit event or an already rate-limited session.
- Request approval immediately before the single live capture/resume attempt; stop if no natural event is available.
- Human decision on 2026-07-21: defer this verification; do not trigger or capture a rate-limit event in the current workstream.

### ISSUE-04-resume-behavior

- status: complete
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

Complete for the separately approved process-present and process-absent scenarios. Both runs returned `claude_exit=0` with resume Hook evidence. History continuity and exact cwd handling remain unverified because prompt, transcript, and path values are excluded; process conflict was not reproduced in either scenario and remains unverified as a distinct behavior.

#### Protocol

- Keep the session ID and project path in the user's local shell only; do not paste either value into chat, logs, fixtures, or the repository.
- For each scenario, record only `process_present=true/false`, `cwd_check=passed/failed`, `claude_exit` as an integer, sanitized Hook event names, and whether a resume-start event was observed.
- Run the official command with the fixed message `Continue`, `shell=False` semantics, the verified CLI executable, and the selected project path as cwd. When using `--output-format stream-json` in print mode, include `--verbose`.
- Use `python3 scripts/run_resume_spike.py` after setting `AIPHEMETINE_RESUME_SESSION_ID`, `AIPHEMETINE_RESUME_CWD`, and `AIPHEMETINE_ORIGINAL_PROCESS_PRESENT=true` in the user's local shell only. The runner prints only exit status, boolean process state, Hook names, and sanitized evidence.
- Use transient settings only, with the capture adapter on `SessionStart`, `Stop`, and `StopFailure`; keep Hook stdout empty and collect sanitized stderr/stream evidence.
- Test separately: original process absent, original process present, and (if naturally available) a session that is still rate-limited. Never inject input into the original process.
- Mark history continuity, cwd handling, Hook execution, and process conflict as verified, contradicted, or unverified. A successful process start alone does not prove task continuation.

#### Live Evidence

- Approved process-present run: one active top-level Claude process and its latest project session were selected deterministically after the user authorized any target.
- Sanitized result: `process_present=true`, `claude_exit=0`, eight safe evidence records, and Hook names `SessionStart:resume`, `UserPromptSubmit`, `Stop`, and an inherited `PreToolUse:Bash` event.
- The stream included `previous_message_not_found` and `rate_limit_event`; neither is treated as proof of history continuity or a rate-limit Hook payload.
- Four Hook payload records contained the required field-presence evidence and repeated the same run-local salted session digest. No raw stderr, session ID, path, prompt, or transcript was retained.
- Hook execution and successful process start are verified for this run. History continuity, exact cwd handling, and process-conflict behavior remain unverified; a successful process start alone does not prove task continuation.
- Earlier process-present failures remain recorded as historical attempts: one command-validation failure caused by the missing `--verbose` flag, followed by a Hook-enabled failure and a Hook-disabled baseline with `is_error=true`. Those failures were superseded for the selected target by this successful run, but they do not establish a root cause for the earlier failures.
- Approved process-absent run: a session file not held open by an active Claude process was selected read-only, then resumed with `process_present=false`; it returned `claude_exit=0`, six safe evidence records, and Hook names `SessionStart:resume`, `UserPromptSubmit`, `Stop`, plus inherited `PreToolUse:Bash` and `PostToolUse:Edit` events.
- The process-absent run also emitted `rate_limit_event` but no `StopFailure` Hook payload; no rate limit was intentionally triggered.
- The process-present and process-absent runs both verified successful non-interactive start and Hook execution. Neither proves history continuity, exact cwd equality, or a distinct process-conflict response.
- The resume runner now classifies result-record error fields into an allowlisted category while retaining neither the raw message nor its identifiers. This is fixture-verified only; no additional live resume was run for this change.

#### Next Actions

- No further resume live action is required for the two process-presence scenarios.
- Keep history continuity, exact cwd handling, and process conflict explicitly unverified for the Phase 0 human review.

#### Implementation

- `scripts/run_resume_spike.py`
- `tests/test_hook_payload.py` (command-construction and result-error redaction coverage)

### ISSUE-05-consolidate-results

- status: complete
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

Consolidated for the `phase0-results-review` gate. Real-environment Hook event availability, payload field shape, and ephemeral candidate lifecycle are verified. The rate-limit Hook remains blocked. Official non-interactive resume and Hook execution are verified for both process-present and process-absent scenarios, while history continuity, exact cwd equality, and distinct process-conflict behavior remain explicitly unverified. No active spec claim is contradicted by the current evidence, so no spec edit is required.

#### Evidence Matrix

| Spike question | Evidence class | Result |
| -------------- | -------------- | ------ |
| Payload validation and redaction contract (Issue 01) | Fixture/unit | verified |
| Resume command construction (fixed `Continue`, `--verbose`, `shell=False`) and result-error redaction | Fixture/unit | verified |
| Hook event availability (`SessionStart:startup`, `UserPromptSubmit`, `Stop`, `SessionEnd` observed) | Live/real | verified |
| Hook payload fields present and non-empty (`session_id`, `cwd`, `transcript_path`, `hook_event_name`) | Live/real | verified |
| Candidate snapshot creation from a Hook event | Live/real | verified — ephemeral candidate snapshot created on `SessionStart` |
| Candidate activity refresh of `updated_at` within the 24-hour freshness window | Live/real | verified — same candidate revision advanced from `1` to `2` on `UserPromptSubmit`; production 24-hour clock behavior remains out of scope |
| Explicit session-end removal of a candidate | Live/real | verified — `SessionEnd` removed the candidate and final file count was `0` |
| `StopFailure(rate_limit)` payload availability and `failure_reason_class` | Live/real | blocked — needs a natural rate-limit event and per-run approval |
| Same-session identity on a rate-limit re-event (salted digest continuity) | Live/real | blocked |
| Rate-limit event recreation after an approved resume (Spike 3 core hypothesis) | Live/real | blocked |
| Official non-interactive resume history continuity | Live/real | unverified — both scenarios returned `claude_exit=0`, but prompt/transcript continuity was not captured |
| Resume cwd handling | Live/real | unverified — the selected cwd was supplied and the payload reported `cwd_present`, but the path value was excluded |
| Resume Hook execution in `-p` mode | Live/real | verified — both scenarios emitted `SessionStart:resume` and lifecycle Hook evidence |
| Process-present conflict behavior | Live/real | unverified — the present-process run succeeded without a distinct conflict result |
| Process-absent resume behavior | Live/real | verified — the approved absent-process run returned `claude_exit=0` with resume Hook evidence |
| Second Claude Code account isolation and execution | Live/real | verified — isolated configuration directories were distinct and authenticated; one approved safe-mode non-interactive execution returned `claude_exit=0` with a non-error result record |

No result is `contradicted`. Mock and fixture evidence never establishes external Claude behavior; every `verified` live row above is backed by a real Hook payload capture, and the blocked rate-limit rows await a naturally occurring event plus separate approval.

#### Spec Alignment

- PRD `StopFailure(rate_limit)` Hook (§15 Spike 1) and candidate-discovery Hook (§15 Spike 1A) remain Deferred Decisions in PRD §18; they are unverified/blocked, not contradicted.
- Architecture §14.2 and §21 (resume behavior and rate-limit recreation) remain explicitly spike-gated; successful process startup does not establish history continuity or rate-limit recreation.
- Therefore active specs need no edit for this gate. Any follow-up workstream for the blocked rate-limit hypothesis must reflect a contradicted assumption into the specs before MVP Phase 1 begins.

#### Verification

- `python3 -m unittest discover -s tests -v` passes 14 tests.
- `git diff --check` passes.
- Repository docs validator passes.
- The approved second-account execution was limited to one minimal non-interactive call; no token or price telemetry was available, so no spend amount is recorded and no additional attempt is authorized.

#### Next Actions

- Present this matrix at `phase0-results-review`. No MVP implementation begins before human approval; ISSUE-03 remains blocked until a natural rate-limit event is available and separately approved.
- If the human gate requires the blocked rate-limit hypothesis, open a separate follow-up workstream for ISSUE-03 only; ISSUE-04 process-presence scenarios are already complete with bounded unverified conclusions.

#### Human Review Checkpoint

- Point 1 — Phase 0 result validity: verified as internally consistent and acceptable as a bounded evidence report. Verified rows are supported by live Hook captures or fixture/unit tests; unverified and blocked rows remain explicitly labeled and are not treated as proven.
- Point 2 — MVP start readiness: not ready. The candidate lifecycle gate is now verified, but the PRD's natural `StopFailure(rate_limit)` gate remains blocked, so MVP implementation remains deferred.
- Point 3 — Natural rate-limit verification: deferred by human decision; no artificial rate-limit attempt is permitted.
- Point 4 — Second Claude account: verified through Claude Code. The two configuration directories are both authenticated and represent distinct accounts, and one approved safe-mode non-interactive execution succeeded; browser account switching is not required.

## Decisions

- Phase 0 is a feasibility workstream; MVP implementation is intentionally deferred to a later human-authorized workstream.
- Artificially causing a Claude rate limit is prohibited.
- Rate-limit-related tests and live resume invocations require explicit human approval each time.
- Mock or fixture evidence cannot establish real Claude Code behavior.
- ISSUE-01 uses a safe observation contract: evidence contains only field-presence booleans, allowlisted failure classifications, and allowlisted error codes; it never retains payload values.
- The local environment exposes `python3` but not `python`; the unittest gate is recorded and executed as `python3 -m unittest discover -s tests -v`.
- ISSUE-03 remains blocked because a natural rate-limit event and per-run approval are required; ISSUE-04 process-present and process-absent live scenarios are complete, with history continuity, exact cwd equality, and distinct process-conflict behavior recorded as unverified. Phase 0 reaches `phase0-results-review` without forcing an artificial rate-limit event.
- Human decision on 2026-07-21: accept the bounded Phase 0 evidence report for review, defer rate-limit verification, verify second-account isolation through Claude Code, and do not authorize MVP implementation yet.
- Claude Code supports isolated configuration directories through `CLAUDE_CONFIG_DIR`; this is the supported mechanism for running multiple accounts side by side. The primary and second local configurations were verified as distinct authenticated accounts without exposing identity values, and the second configuration completed one approved safe-mode non-interactive execution successfully.

## Completion

- [x] Every issue meets its acceptance criteria (ISSUE-03/04 acceptance is met by recording blocked/unverified conclusions at the gate)
- [x] Every issue records guide impact as required or none
- [x] Required guides describe current implemented behavior (no guide required; feasibility only)
- [x] Specs reflect any changed direction or requirements (no spec claim is contradicted by evidence)
- [x] Next human gate reached or the workstream intentionally stopped (presented at `phase0-results-review`)
- [x] 00_index.md updated
- [ ] Workstream archived when complete (defer to human decision at the gate)
