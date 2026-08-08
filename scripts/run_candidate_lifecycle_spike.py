#!/usr/bin/env python3
"""Run one approved live candidate-lifecycle spike in an ephemeral repo dir."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Set

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from scripts.run_resume_spike import _collect_safe_records  # noqa: E402


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
                                capture_salt, lifecycle_root, lifecycle_script
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
    records: List[Dict[str, Any]] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        records.append(
            {
                "event_class": value.get("event_class") if isinstance(value.get("event_class"), str) else "other",
                "action": value.get("action") if isinstance(value.get("action"), str) else "other",
                "accepted": bool(value.get("accepted")),
                "error_code": value.get("error_code") if isinstance(value.get("error_code"), str) else None,
                "revision": value.get("revision") if isinstance(value.get("revision"), int) else None,
                "candidate_exists_after": bool(value.get("candidate_exists_after")),
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
        stream_types: Set[str] = set()
        hook_names: Set[str] = set()
        safe_records: List[Dict[str, Any]] = []
        if completed is not None:
            for line in (completed.stdout + "\n" + completed.stderr).splitlines():
                try:
                    parsed = json.loads(line)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                _collect_safe_records(parsed, stream_types, hook_names, safe_records)
        manifest = _read_manifest(lifecycle_root)
        final_candidate_count = len(list((lifecycle_root / "candidates").glob("*.json"))) if (lifecycle_root / "candidates").is_dir() else 0
        print("claude_exit={}".format(completed.returncode if completed is not None else "timeout"))
        print("timed_out={}".format(str(timed_out).lower()))
        print("stream_types={}".format(",".join(sorted(stream_types))))
        print("hook_names={}".format(",".join(sorted(hook_names))))
        print("lifecycle_event_classes={}".format(",".join(record["event_class"] for record in manifest)))
        print("lifecycle_actions={}".format(",".join(record["action"] for record in manifest)))
        print("lifecycle_revisions={}".format(",".join(str(record["revision"]) for record in manifest)))
        print("candidate_exists_after={}".format(",".join(str(record["candidate_exists_after"]).lower() for record in manifest)))
        print("final_candidate_file_count={}".format(final_candidate_count))
        print("sanitized_evidence_records={}".format(len(safe_records)))
        return completed.returncode if completed is not None else 124
    finally:
        shutil.rmtree(lifecycle_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(run())
