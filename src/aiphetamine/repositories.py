"""Read-only, defensive JSON repositories for Phase 1 local decisions."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar

from .domain import CandidateSession, RateLimitEvent, session_key


UTC = timezone.utc
T = TypeVar("T")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _parse_absolute_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else None


def _read_json(path: Path) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


class _Repository(Generic[T]):
    directory_name: str

    def __init__(self, root: Path):
        self.root = root

    def _files(self) -> list[Path]:
        if not self.root.is_dir() or self.root.is_symlink():
            return []
        try:
            return sorted(self.root.glob("*.json"), key=lambda path: path.name)
        except OSError:
            return []

    def _is_time_valid(self, updated_at: datetime, now: datetime, max_age: timedelta) -> bool:
        current = now.astimezone(UTC)
        delta = updated_at - current
        return delta <= timedelta(minutes=5) and current - updated_at <= max_age


class CandidateRepository(_Repository[CandidateSession]):
    def list_candidates(
        self, *, now: datetime, max_age: timedelta = timedelta(hours=24)
    ) -> list[CandidateSession]:
        records: dict[str, CandidateSession] = {}
        for path in self._files():
            payload = _read_json(path)
            if payload is None:
                continue
            record = self._parse(path, payload, now, max_age)
            if record is not None:
                records[record.session_id] = record
        return [records[key] for key in sorted(records)]

    def _parse(
        self, path: Path, payload: dict[str, Any], now: datetime, max_age: timedelta
    ) -> CandidateSession | None:
        session_id = payload.get("session_id")
        project_path = _parse_absolute_path(payload.get("project_path"))
        updated_at = _parse_timestamp(payload.get("updated_at"))
        if (
            payload.get("schema_version") != 1
            or payload.get("record_type") != "candidate"
            or not isinstance(session_id, str)
            or not session_id
            or project_path is None
            or updated_at is None
            or path.stem != session_key(session_id)
            or not self._is_time_valid(updated_at, now, max_age)
        ):
            return None
        session_name = payload.get("session_name")
        project_name = payload.get("project_name")
        account_name = payload.get("account_name")
        return CandidateSession(
            schema_version=1,
            record_type="candidate",
            session_id=session_id,
            project_path=project_path,
            updated_at=updated_at,
            session_name=session_name if isinstance(session_name, str) else None,
            project_name=project_name if isinstance(project_name, str) else None,
            source_file=path,
            account_name=account_name if isinstance(account_name, str) else None,
        )


class RateLimitEventRepository(_Repository[RateLimitEvent]):
    def list_events(
        self, *, now: datetime, max_age: timedelta = timedelta(hours=12)
    ) -> list[RateLimitEvent]:
        records: dict[str, RateLimitEvent] = {}
        for path in self._files():
            payload = _read_json(path)
            if payload is None:
                continue
            record = self._parse(path, payload, now, max_age)
            if record is not None:
                records[record.session_id] = record
        return [records[key] for key in sorted(records)]

    def claim(self, event: RateLimitEvent) -> Path | None:
        source = event.source_file
        if not self._is_artifact(source, ".json") or source is None:
            return None
        processing = source.with_suffix(".processing")
        if (
            processing.exists()
            or processing.is_symlink()
            or source.is_symlink()
            or not source.is_file()
        ):
            return None
        try:
            os.replace(source, processing)
        except OSError:
            return None
        return processing

    def complete(self, processing_path: Path) -> bool:
        if not self._is_artifact(processing_path, ".processing"):
            return False
        try:
            processing_path.unlink()
        except FileNotFoundError:
            return False
        except OSError:
            return False
        return True

    def restore(self, processing_path: Path) -> Path | None:
        if not self._is_artifact(processing_path, ".processing"):
            return None
        restored = processing_path.with_suffix(".json")
        if restored.exists():
            self.complete(processing_path)
            return restored
        try:
            os.replace(processing_path, restored)
        except OSError:
            return None
        return restored

    def cleanup_on_startup(
        self,
        *,
        now: datetime | None = None,
        preserve_fresh: bool = False,
    ) -> int:
        if self.root.is_symlink() or not self.root.is_dir():
            return 0
        preserved: set[Path] = set()
        if preserve_fresh and now is not None:
            preserved = {
                event.source_file
                for event in self.list_events(now=now)
                if event.source_file is not None
            }
        removed = 0
        try:
            entries = list(self.root.iterdir())
        except OSError:
            return 0
        for path in entries:
            if not path.is_file() and not path.is_symlink():
                continue
            if path in preserved:
                continue
            if path.suffix == ".json" or path.suffix == ".processing" or ".tmp." in path.name:
                try:
                    path.unlink()
                except OSError:
                    continue
                removed += 1
        return removed

    def _is_artifact(self, path: Path | None, suffix: str) -> bool:
        return (
            path is not None
            and self.root.is_dir()
            and not self.root.is_symlink()
            and path.parent == self.root
            and path.suffix == suffix
        )

    def _parse(
        self, path: Path, payload: dict[str, Any], now: datetime, max_age: timedelta
    ) -> RateLimitEvent | None:
        session_id = payload.get("session_id")
        project_path = _parse_absolute_path(payload.get("project_path"))
        updated_at = _parse_timestamp(payload.get("updated_at"))
        if (
            payload.get("schema_version") != 1
            or payload.get("record_type") != "rate_limit"
            or payload.get("reason") != "rate_limit"
            or not isinstance(session_id, str)
            or not session_id
            or project_path is None
            or updated_at is None
            or path.stem != session_key(session_id)
            or not self._is_time_valid(updated_at, now, max_age)
        ):
            return None
        return RateLimitEvent(
            schema_version=1,
            record_type="rate_limit",
            reason="rate_limit",
            session_id=session_id,
            project_path=project_path,
            updated_at=updated_at,
            source_file=path,
            account_name=(
                payload["account_name"]
                if isinstance(payload.get("account_name"), str)
                else None
            ),
        )
