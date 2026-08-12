#!/usr/bin/env python3
"""Run one approved resume spike without printing sensitive CLI output."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Set, Tuple


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

SAFE_KEYS = {
    "schema_version",
    "accepted",
    "error_code",
    "session_id_present",
    "cwd_present",
    "transcript_path_present",
    "event_type_present",
    "failure_reason_class",
    "session_name_present",
    "session_id_digest",
    "is_error",
}

_SAFE_BOOLEAN_KEYS = {
    "accepted",
    "session_id_present",
    "cwd_present",
    "transcript_path_present",
    "event_type_present",
    "session_name_present",
    "is_error",
}
_SAFE_ENUM_KEYS = {
    "failure_reason_class": {"rate_limit", "other", "missing", "invalid"},
    "result_error_class": {
        "cli_argument_validation",
        "authentication",
        "settings_or_hook_config",
        "resume_session",
        "rate_limit",
        "executable_or_hook_not_found",
        "permission",
        "network_or_service",
        "unknown",
    },
}
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


def classify_error(output: str) -> str:
    """Classify CLI output without returning any raw error text."""

    lowered = output.lower()
    patterns = (
        ("cli_argument_validation", ("requires --verbose", "usage:")),
        ("authentication", ("auth", "login", "signed in")),
        ("settings_or_hook_config", ("invalid settings", "hook", "settings")),
        ("resume_session", ("resume", "session", "conversation")),
        ("rate_limit", ("rate limit", "rate_limit")),
        ("executable_or_hook_not_found", ("enoent", "not found", "no such file")),
        ("permission", ("permission denied", "eacces")),
        ("network_or_service", ("network", "connect", "timeout", "overload")),
    )
    for category, needles in patterns:
        if any(needle in lowered for needle in needles):
            return category
    return "unknown"


def _classify_result_error(value: Any) -> str | None:
    """Classify an error result without retaining its message or details."""

    if not isinstance(value, dict) or value.get("is_error") is not True:
        return None

    fragments = []
    for key in ("error", "message", "subtype", "stop_reason"):
        item = value.get(key)
        if isinstance(item, str):
            fragments.append(item)
    if not fragments:
        return "unknown"
    return classify_error(" ".join(fragments))


def _collect_safe_records(
    value: Any,
    stream_types: Set[str],
    hook_names: Set[str],
    records: List[Dict[str, Any]],
    _depth: int = 0,
) -> None:
    if _depth > 64:
        return
    if isinstance(value, dict):
        stream_type = value.get("type")
        if isinstance(stream_type, str):
            # Keep only presence. Claude can place arbitrary labels in this
            # field, so even a short string is not safe diagnostic output.
            stream_types.add("present")
        for key in ("hook_name", "hook_event_name", "event_name"):
            item = value.get(key)
            if isinstance(item, str):
                hook_names.add("present")
        evidence: Dict[str, Any] = {}
        for key in SAFE_KEYS:
            if key not in value:
                continue
            item = value[key]
            if key in _SAFE_BOOLEAN_KEYS and isinstance(item, bool):
                evidence[key] = item
            elif key == "schema_version" and isinstance(item, int) and not isinstance(item, bool):
                evidence["schema_version_present"] = item == 1
            elif key == "error_code" and isinstance(item, str):
                evidence["error_code_class"] = "known" if item in _KNOWN_ERROR_CODES else "other"
            elif key in _SAFE_ENUM_KEYS and isinstance(item, str):
                evidence[key] = item if item in _SAFE_ENUM_KEYS[key] else "other"
            elif key == "session_id_digest":
                evidence["session_id_digest_present"] = isinstance(item, str) and bool(item)
        result_error_class = _classify_result_error(value)
        if result_error_class is not None:
            evidence["result_error_class"] = result_error_class
        if evidence:
            records.append(evidence)
        for item in value.values():
            _collect_safe_records(item, stream_types, hook_names, records, _depth + 1)
    elif isinstance(value, list):
        for item in value:
            _collect_safe_records(item, stream_types, hook_names, records, _depth + 1)
    elif isinstance(value, str) and value.startswith("{") and len(value) <= 2000:
        try:
            nested = json.loads(value)
        except (json.JSONDecodeError, TypeError, RecursionError):
            return
        if isinstance(nested, dict) and set(nested).issubset(SAFE_KEYS):
            _collect_safe_records(nested, stream_types, hook_names, records, _depth + 1)


def build_resume_command(
    executable: str, session_id: str, capture_script: Path, capture_salt: str
) -> List[str]:
    settings = {
        "hooks": {
            event: [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "env AIPHEMETINE_CAPTURE_SALT={} python3 {}".format(
                                shlex.quote(capture_salt), shlex.quote(str(capture_script))
                            ),
                        }
                    ]
                }
            ]
            for event in ("SessionStart", "Stop", "StopFailure")
        }
    }
    return [
        executable,
        "-p",
        "--resume",
        session_id,
        "--settings",
        json.dumps(settings, ensure_ascii=False),
        "--debug",
        "hooks",
        "--output-format",
        "stream-json",
        "--include-hook-events",
        "--verbose",
        "Continue",
    ]


def run() -> int:
    session_id = os.environ.get("AIPHEMETINE_RESUME_SESSION_ID", "")
    project_cwd = os.environ.get("AIPHEMETINE_RESUME_CWD", "")
    process_present = os.environ.get("AIPHEMETINE_ORIGINAL_PROCESS_PRESENT", "unknown")
    if not session_id or not project_cwd:
        print("error=missing_local_resume_inputs")
        return 2

    cwd = Path(project_cwd).expanduser()
    if not cwd.is_absolute() or not cwd.is_dir():
        print("error=invalid_resume_cwd")
        return 2

    executable = os.environ.get(
        "AIPHEMETINE_CLAUDE_EXECUTABLE", str(Path.home() / ".local/bin/claude")
    )
    capture_salt = secrets.token_hex(16)
    command = build_resume_command(
        executable, session_id, REPOSITORY_ROOT / "hooks/capture_sanitized_payload.py", capture_salt
    )
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError, UnicodeError) as error:
        print("claude_exit=launch_error")
        print("error_class={}".format(classify_error(str(error))))
        print("process_present={}".format(process_present if process_present in {"true", "false"} else "unknown"))
        print("stream_types_present=false")
        print("hook_names_present=false")
        print("sanitized_evidence_records=0")
        return 1

    stream_types: Set[str] = set()
    hook_names: Set[str] = set()
    records: List[Dict[str, Any]] = []
    for line in (completed.stdout + "\n" + completed.stderr).splitlines():
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, TypeError, RecursionError):
            continue
        _collect_safe_records(parsed, stream_types, hook_names, records)

    print("claude_exit={}".format(completed.returncode))
    if completed.returncode != 0:
        print("error_class={}".format(classify_error(completed.stdout + "\n" + completed.stderr)))
    print("process_present={}".format(process_present if process_present in {"true", "false"} else "unknown"))
    print("stream_types_present={}".format(str(bool(stream_types)).lower()))
    print("hook_names_present={}".format(str(bool(hook_names)).lower()))
    print("sanitized_evidence_records={}".format(len(records)))
    for record in records:
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(run())
