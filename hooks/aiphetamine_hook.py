"""Best-effort Claude Hook writer for local AIphetamine event records."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aiphetamine.domain import session_key


UTC = timezone.utc


def apply_event(payload: dict[str, Any], event: str, data_root: Path, now: datetime, account_name: str | None = None) -> str:
    session_id = payload.get("session_id")
    cwd = payload.get("cwd")
    if not isinstance(session_id, str) or not session_id or not isinstance(cwd, str):
        return "invalid_payload"
    project_path = Path(cwd)
    if not project_path.is_absolute():
        return "invalid_payload"
    key = session_key(session_id)
    candidates = data_root / "candidates"
    rate_limits = data_root / "rate_limits"
    if event == "SessionEnd":
        target = candidates / f"{key}.json"
        rate_limit = rate_limits / f"{key}.json"
        if rate_limit.is_file() and not rate_limit.is_symlink():
            return "preserved_for_rate_limit"
        try:
            target.unlink(missing_ok=True)
        except OSError:
            return "filesystem_error"
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
    if isinstance(account_name, str) and account_name.strip():
        record["account_name"] = account_name.strip()
    try:
        _atomic_write(directory / f"{key}.json", record)
    except OSError:
        return "filesystem_error"
    return "written"


def _atomic_write(target: Path, record: dict[str, Any]) -> None:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{target.stem}.tmp.", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


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
