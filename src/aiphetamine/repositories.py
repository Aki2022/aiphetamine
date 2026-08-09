"""Read-only, defensive JSON repositories for Phase 1 local decisions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar

from .domain import CandidateSession, RateLimitEvent, session_key
from .filesystem_security import read_private_text, secure_replace, secure_unlink


UTC = timezone.utc
T = TypeVar("T")
_ALLOWED_ACCOUNT_NAMES = frozenset(("main", "alias"))
_ACCOUNT_SCOPES = _ALLOWED_ACCOUNT_NAMES | {"unknown"}
_INVALID_ACCOUNT = object()


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
        value = json.loads(read_private_text(path))
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
        files: list[Path] = []
        try:
            for path in self.root.iterdir():
                if path.is_symlink():
                    continue
                if path.is_file() and path.suffix == ".json":
                    files.append(path)
                elif path.is_dir() and path.name in _ACCOUNT_SCOPES:
                    for scoped in path.iterdir():
                        if not scoped.is_symlink() and scoped.is_file() and scoped.suffix == ".json":
                            files.append(scoped)
        except OSError:
            return []
        return sorted(files, key=lambda path: str(path))

    def _is_time_valid(self, updated_at: datetime, now: datetime, max_age: timedelta) -> bool:
        current = now.astimezone(UTC)
        delta = updated_at - current
        return delta <= timedelta(minutes=5) and current - updated_at <= max_age

    def _account_name(self, path: Path, payload: dict[str, Any]):
        value = payload.get("account_name")
        if value is not None and (not isinstance(value, str) or value not in _ALLOWED_ACCOUNT_NAMES):
            return _INVALID_ACCOUNT
        if path.parent == self.root:
            # Labeled legacy records used the old shared filename namespace;
            # fail closed instead of treating them as account-routed evidence.
            return None if value is None else _INVALID_ACCOUNT
        scope = path.parent.name
        if scope not in _ACCOUNT_SCOPES:
            return _INVALID_ACCOUNT
        if scope == "unknown":
            return None if value is None else _INVALID_ACCOUNT
        if value is not None and value != scope:
            return _INVALID_ACCOUNT
        return scope

    @staticmethod
    def _deduplicate(records: list[T]) -> list[T]:
        unique: dict[str, T] = {}
        ambiguous: set[str] = set()
        for record in records:
            session_id = record.session_id  # type: ignore[attr-defined]
            if session_id in ambiguous:
                continue
            if session_id in unique:
                # Never let two account scopes or two conflicting files choose
                # an arbitrary winner for the same Claude session.
                ambiguous.add(session_id)
                unique.pop(session_id, None)
                continue
            unique[session_id] = record
        return [unique[key] for key in sorted(unique)]


class CandidateRepository(_Repository[CandidateSession]):
    def list_candidates(
        self, *, now: datetime, max_age: timedelta = timedelta(hours=24)
    ) -> list[CandidateSession]:
        records: list[CandidateSession] = []
        for path in self._files():
            payload = _read_json(path)
            if payload is None:
                continue
            record = self._parse(path, payload, now, max_age)
            if record is not None:
                records.append(record)
        return self._deduplicate(records)

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
        account_name = self._account_name(path, payload)
        if account_name is _INVALID_ACCOUNT:
            return None
        session_name = payload.get("session_name")
        project_name = payload.get("project_name")
        return CandidateSession(
            schema_version=1,
            record_type="candidate",
            session_id=session_id,
            project_path=project_path,
            updated_at=updated_at,
            session_name=session_name if isinstance(session_name, str) else None,
            project_name=project_name if isinstance(project_name, str) else None,
            source_file=path,
            account_name=account_name,
        )


class RateLimitEventRepository(_Repository[RateLimitEvent]):
    def list_events(
        self, *, now: datetime, max_age: timedelta = timedelta(hours=12)
    ) -> list[RateLimitEvent]:
        records: list[RateLimitEvent] = []
        for path in self._files():
            payload = _read_json(path)
            if payload is None:
                continue
            record = self._parse(path, payload, now, max_age)
            if record is not None:
                records.append(record)
        return self._deduplicate(records)

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
            secure_replace(source, processing)
        except OSError:
            return None
        return processing

    def complete(self, processing_path: Path) -> bool:
        if not self._is_artifact(processing_path, ".processing"):
            return False
        try:
            secure_unlink(processing_path)
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
            secure_replace(processing_path, restored)
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
        directories = [self.root]
        try:
            directories.extend(
                path
                for path in self.root.iterdir()
                if path.is_dir() and not path.is_symlink() and path.name in _ACCOUNT_SCOPES
            )
        except OSError:
            return 0
        for directory in directories:
            try:
                entries = list(directory.iterdir())
            except OSError:
                continue
            for path in entries:
                if not path.is_file() and not path.is_symlink():
                    continue
                if path in preserved:
                    continue
                if path.suffix == ".json" or path.suffix == ".processing" or ".tmp." in path.name:
                    try:
                        secure_unlink(path)
                    except OSError:
                        continue
                    removed += 1
        return removed

    def _is_artifact(self, path: Path | None, suffix: str) -> bool:
        if (
            path is None
            or not self.root.is_dir()
            or self.root.is_symlink()
            or path.suffix != suffix
        ):
            return False
        if path.parent == self.root:
            return True
        return (
            path.parent.parent == self.root
            and path.parent.name in _ACCOUNT_SCOPES
            and not path.parent.is_symlink()
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
        account_name = self._account_name(path, payload)
        if account_name is _INVALID_ACCOUNT:
            return None
        return RateLimitEvent(
            schema_version=1,
            record_type="rate_limit",
            reason="rate_limit",
            session_id=session_id,
            project_path=project_path,
            updated_at=updated_at,
            source_file=path,
            account_name=account_name,
        )
