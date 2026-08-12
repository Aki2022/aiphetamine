#!/usr/bin/env python3
"""Run one approved live candidate-lifecycle spike in an ephemeral repo dir."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Set

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

_KNOWN_ERROR_CODES = {
    "payload_not_object",
    "invalid_json",
    "missing_session_id",
    "invalid_session_id",
    "missing_cwd",
    "invalid_cwd",
    "missing_transcript_path",
    "invalid_transcript_path",
    "missing_event_type",
    "invalid_event_type",
    "invalid_failure_reason",
}

from scripts.run_resume_spike import _collect_safe_records, classify_error  # noqa: E402


def build_lifecycle_command(
    executable: str, lifecycle_script: Path, lifecycle_root: Path, capture_salt: str
) -> List[str]:
    settings = {
        "hooks": {
            event: [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "env AIPHEMETINE_CAPTURE_SALT={} AIPHEMETINE_LIFECYCLE_ROOT={} python3 {}".format(
                                shlex.quote(capture_salt),
                                shlex.quote(str(lifecycle_root)),
                                shlex.quote(str(lifecycle_script)),
                            ),
                        }
                    ]
                }
            ]
            for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd")
        }
    }
    return [
        executable,
        "-p",
        "--settings",
        json.dumps(settings, ensure_ascii=False),
        "--debug",
        "hooks",
        "--output-format",
        "stream-json",
        "--include-hook-events",
        "--verbose",
        "Respond with OK only.",
    ]


def _read_manifest(root: Path) -> List[Dict[str, Any]]:
    manifest = root / "lifecycle.jsonl"
    if not manifest.is_file():
        return []
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []
    records: List[Dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
            continue
        if not isinstance(value, dict):
            continue
        event_class = value.get("event_class")
        action = value.get("action")
        error_code = value.get("error_code")
        revision = value.get("revision")
        if revision is None:
            revision_class = "missing"
        elif (
            isinstance(revision, int)
            and not isinstance(revision, bool)
            and 0 <= revision <= 1000000
        ):
            revision_class = "present"
        else:
            revision_class = "invalid"
        records.append(
            {
                "event_class": (
                    event_class
                    if isinstance(event_class, str)
                    and event_class in {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd", "other"}
                    else "other"
                ),
                "action": (
                    action
                    if isinstance(action, str)
                    and action in {"upsert", "remove", "ignored", "reject", "other"}
                    else "other"
                ),
                "accepted": value.get("accepted") if isinstance(value.get("accepted"), bool) else False,
                "error_code_class": (
                    "known"
                    if isinstance(error_code, str) and error_code in _KNOWN_ERROR_CODES
                    else "other"
                    if isinstance(error_code, str)
                    else "none"
                ),
                "revision_class": revision_class,
                "candidate_exists_after": (
                    value.get("candidate_exists_after")
                    if isinstance(value.get("candidate_exists_after"), bool)
                    else False
                ),
            }
        )
    return records


def run() -> int:
    project_cwd = Path(os.environ.get("AIPHEMETINE_LIFECYCLE_CWD", str(REPOSITORY_ROOT))).expanduser()
    if not project_cwd.is_absolute() or not project_cwd.is_dir():
        print("error=invalid_lifecycle_cwd")
        return 2
    executable = os.environ.get(
        "AIPHEMETINE_CLAUDE_EXECUTABLE", str(Path.home() / ".local/bin/claude")
    )
    lifecycle_root = Path(tempfile.mkdtemp(prefix=".aiphetamine-lifecycle-", dir=REPOSITORY_ROOT))
    capture_salt = secrets.token_hex(16)
    command = build_lifecycle_command(
        executable,
        REPOSITORY_ROOT / "hooks/capture_candidate_lifecycle.py",
        lifecycle_root,
        capture_salt,
    )
    timed_out = False
    completed: subprocess.CompletedProcess[str] | None = None
    try:
        try:
            completed = subprocess.run(
                command,
                cwd=str(project_cwd),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
        except (OSError, ValueError, UnicodeError) as error:
            launch_error_class = classify_error(str(error))
        else:
            launch_error_class = None
        stream_types: Set[str] = set()
        hook_names: Set[str] = set()
        safe_records: List[Dict[str, Any]] = []
        if completed is not None:
            for line in (completed.stdout + "\n" + completed.stderr).splitlines():
                try:
                    parsed = json.loads(line)
                except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
                    continue
                _collect_safe_records(parsed, stream_types, hook_names, safe_records)
        manifest = _read_manifest(lifecycle_root)
        final_candidate_count = len(list((lifecycle_root / "candidates").glob("*.json"))) if (lifecycle_root / "candidates").is_dir() else 0
        if completed is not None:
            exit_label = completed.returncode
        elif timed_out:
            exit_label = "timeout"
        else:
            exit_label = "launch_error"
        print("claude_exit={}".format(exit_label))
        if completed is None and not timed_out:
            print("error_class={}".format(launch_error_class))
        print("timed_out={}".format(str(timed_out).lower()))
        print("stream_types_present={}".format(str(bool(stream_types)).lower()))
        print("hook_names_present={}".format(str(bool(hook_names)).lower()))
        print("lifecycle_event_classes={}".format(",".join(record["event_class"] for record in manifest)))
        print("lifecycle_actions={}".format(",".join(record["action"] for record in manifest)))
        print("lifecycle_revision_classes={}".format(",".join(record["revision_class"] for record in manifest)))
        print("candidate_exists_after={}".format(",".join(str(record["candidate_exists_after"]).lower() for record in manifest)))
        print("final_candidate_file_count={}".format(final_candidate_count))
        print("sanitized_evidence_records={}".format(len(safe_records)))
        return completed.returncode if completed is not None else 124 if timed_out else 1
    finally:
        shutil.rmtree(lifecycle_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(run())
