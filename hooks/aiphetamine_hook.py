"""Best-effort Claude Hook writer for local AIphetamine event records."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aiphetamine.domain import session_key
from aiphetamine.filesystem_security import (
    atomic_write_bytes,
    ensure_private_directory,
    secure_unlink,
)


UTC = timezone.utc
_ALLOWED_ACCOUNT_NAMES = frozenset(("main", "alias"))
_ACCOUNT_SCOPES = _ALLOWED_ACCOUNT_NAMES | {"unknown"}


def apply_event(payload: dict[str, Any], event: str, data_root: Path, now: datetime, account_name: str | None = None) -> str:
    if account_name is not None and (
        not isinstance(account_name, str) or account_name not in _ALLOWED_ACCOUNT_NAMES
    ):
        return "invalid_account_name"
    session_id = payload.get("session_id")
    cwd = payload.get("cwd")
    if not isinstance(session_id, str) or not session_id or not isinstance(cwd, str):
        return "invalid_payload"
    project_path = Path(cwd)
    if not project_path.is_absolute():
        return "invalid_payload"
    key = session_key(session_id)
    candidates_root = data_root / "candidates"
    rate_limits_root = data_root / "rate_limits"
    scope = account_name or "unknown"
    candidates = candidates_root / scope
    rate_limits = rate_limits_root / scope
    try:
        ensure_private_directory(data_root)
        ensure_private_directory(candidates_root)
        ensure_private_directory(rate_limits_root)
        ensure_private_directory(candidates)
        ensure_private_directory(rate_limits)
    except OSError:
        return "filesystem_error"
    if event == "SessionEnd":
        scopes = (scope,) if account_name is not None else tuple(sorted(_ACCOUNT_SCOPES))
        rate_limit_paths = [rate_limits_root / item / f"{key}.json" for item in scopes]
        # Read the legacy flat location only to preserve an event created by an
        # older Hook; new writes always use an account scope.
        rate_limit_paths.append(rate_limits_root / f"{key}.json")
        if any(_is_regular_file(path) for path in rate_limit_paths):
            return "preserved_for_rate_limit"
        for item in scopes:
            target = candidates_root / item / f"{key}.json"
            if not target.parent.is_dir() or target.parent.is_symlink():
                continue
            try:
                secure_unlink(target)
            except FileNotFoundError:
                continue
            except OSError:
                return "filesystem_error"
        try:
            secure_unlink(candidates_root / f"{key}.json")
        except (FileNotFoundError, OSError):
            pass
        return "removed"
    if event not in {"SessionStart", "UserPromptSubmit", "StopFailure"}:
        return "ignored"
    directory = rate_limits if event == "StopFailure" else candidates
    record_type = "rate_limit" if event == "StopFailure" else "candidate"
    record: dict[str, Any] = {
        "schema_version": 1,
        "record_type": record_type,
        "session_id": session_id,
        "project_path": str(project_path),
        "updated_at": now.astimezone(UTC).isoformat(),
    }
    if record_type == "rate_limit":
        record["reason"] = "rate_limit"
    else:
        for field in ("session_name", "project_name"):
            if isinstance(payload.get(field), str):
                record[field] = payload[field]
    if account_name is not None:
        record["account_name"] = account_name
    try:
        _atomic_write(directory / f"{key}.json", record)
    except OSError:
        return "filesystem_error"
    return "written"


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(os.stat(path, follow_symlinks=False).st_mode)
    except OSError:
        return False


def _atomic_write(target: Path, record: dict[str, Any]) -> None:
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
    atomic_write_bytes(target, encoded)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--event", required=True)
    parser.add_argument("--data-root", type=Path, default=Path.home() / ".local/share/aiphetamine")
    parser.add_argument("--account-name")
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        print("invalid_payload", file=sys.stderr)
        return 0
    result = apply_event(payload if isinstance(payload, dict) else {}, args.event, args.data_root, datetime.now(UTC), args.account_name)
    if result not in {"written", "removed", "ignored"}:
        print(result, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
