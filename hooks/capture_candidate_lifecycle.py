"""Observe candidate snapshot lifecycle using only ephemeral safe evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, Mapping, TextIO

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.spikes.hook_payload import redact_hook_payload  # noqa: E402


_UPSERT_EVENTS = {"SessionStart", "UserPromptSubmit"}
_KNOWN_EVENTS = _UPSERT_EVENTS | {"Stop", "SessionEnd"}


def _event_name(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    for key in ("hook_event_name", "event_type"):
        value = payload.get(key)
        if isinstance(value, str):
            return value.split(":", 1)[0]
    return ""


def _safe_event_class(event_name: str) -> str:
    return event_name if event_name in _KNOWN_EVENTS else "other"


def _append_manifest(root: Path, record: Dict[str, Any]) -> None:
    manifest = root / "lifecycle.jsonl"
    with manifest.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _candidate_path(root: Path, evidence: Mapping[str, Any]) -> Path | None:
    digest = evidence.get("session_id_digest")
    if not isinstance(digest, str) or not digest:
        return None
    return root / "candidates" / ("{}.json".format(digest))


def _read_revision(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, RecursionError):
        return 0
    revision = value.get("revision") if isinstance(value, dict) else None
    return revision if isinstance(revision, int) and revision >= 0 else 0


def _write_candidate(path: Path, evidence: Mapping[str, Any], event_name: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    revision = _read_revision(path) + 1
    record = {
        "schema_version": 1,
        "record_type": "candidate",
        "session_id_digest": evidence.get("session_id_digest"),
        "cwd_present": evidence.get("cwd_present", False),
        "transcript_path_present": evidence.get("transcript_path_present", False),
        "last_event_class": event_name,
        "revision": revision,
    }
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=".candidate-", delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return revision


def process_lifecycle_payload(payload: Any, output: TextIO) -> int:
    """Apply one safe lifecycle transition; Hook stdout remains unused."""

    root_value = os.environ.get("AIPHEMETINE_LIFECYCLE_ROOT", "")
    root = Path(root_value) if root_value else None
    evidence = redact_hook_payload(payload)
    event_name = _event_name(payload)
    event_class = _safe_event_class(event_name)
    action = "ignored"
    revision = None
    candidate_exists_after = False
    candidate = _candidate_path(root, evidence) if root is not None else None

    if root is not None and root.is_absolute() and evidence.get("accepted") and candidate is not None:
        root.mkdir(parents=True, exist_ok=True)
        if event_class in _UPSERT_EVENTS:
            revision = _write_candidate(candidate, evidence, event_class)
            action = "upsert"
            candidate_exists_after = True
        elif event_class == "SessionEnd":
            action = "remove"
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass
            candidate_exists_after = candidate.exists()
        else:
            candidate_exists_after = candidate.exists()
    else:
        action = "reject"

    if root is not None and root.is_absolute():
        root.mkdir(parents=True, exist_ok=True)
        _append_manifest(
            root,
            {
                "event_class": event_class,
                "action": action,
                "accepted": bool(evidence.get("accepted")),
                "error_code": evidence.get("error_code"),
                "revision": revision,
                "candidate_exists_after": candidate_exists_after,
            },
        )
    return 0


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
        payload = None
    raise SystemExit(process_lifecycle_payload(payload, sys.stderr))
