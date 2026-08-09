"""Ephemeral activation state for candidate sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .domain import CandidateSession


UTC = timezone.utc
_MISSING = object()


@dataclass(frozen=True)
class SessionActivation:
    session_id: str
    activated_at: datetime
    expires_at: datetime
    resolved_project_path: Path
    project_device: int
    project_inode: int
    account_name: str | None = None


class InMemorySelectionStore:
    def __init__(self) -> None:
        self._activations: dict[tuple[str, str | None], SessionActivation] = {}

    def activate(self, candidate: CandidateSession, now: datetime) -> SessionActivation:
        now_utc = now.astimezone(UTC)
        resolved = candidate.project_path.resolve(strict=True)
        stat = resolved.stat()
        if not resolved.is_dir():
            raise NotADirectoryError(str(resolved))
        activation = SessionActivation(
            session_id=candidate.session_id,
            activated_at=now_utc,
            expires_at=now_utc + timedelta(hours=12),
            resolved_project_path=resolved,
            project_device=stat.st_dev,
            project_inode=stat.st_ino,
            account_name=candidate.account_name,
        )
        for key in tuple(key for key in self._activations if key[0] == candidate.session_id):
            self._activations.pop(key, None)
        self._activations[(candidate.session_id, candidate.account_name)] = activation
        return activation

    def deactivate(self, session_id: str, account_name: str | None = None) -> None:
        if account_name is not None:
            self._activations.pop((session_id, account_name), None)
            return
        for key in tuple(key for key in self._activations if key[0] == session_id):
            self._activations.pop(key, None)

    def is_selected(self, session_id: str, account_name: str | None | object = _MISSING) -> bool:
        if account_name is None:
            return (session_id, None) in self._activations
        if account_name is _MISSING:
            return sum(1 for key in self._activations if key[0] == session_id) == 1
        if account_name is not None:
            return (session_id, account_name) in self._activations
        return False

    def is_any_selected(self, session_id: str) -> bool:
        """Return whether this session has any activation for status reporting."""

        return any(key[0] == session_id for key in self._activations)

    def get(self, session_id: str, account_name: str | None | object = _MISSING) -> SessionActivation | None:
        if account_name is None:
            return self._activations.get((session_id, None))
        if account_name is _MISSING:
            matches = [activation for key, activation in self._activations.items() if key[0] == session_id]
            return matches[0] if len(matches) == 1 else None
        if account_name is not None:
            return self._activations.get((session_id, account_name))
        return None

    def is_expired(
        self, session_id: str, now_utc: datetime, account_name: str | None | object = _MISSING
    ) -> bool:
        activation = self.get(session_id, account_name)
        return activation is not None and now_utc.astimezone(UTC) >= activation.expires_at

    def expire_due(self, now_utc: datetime) -> tuple[str, ...]:
        current = now_utc.astimezone(UTC)
        expired = tuple(
            session_id
            for (session_id, _account_name), activation in self._activations.items()
            if current >= activation.expires_at
        )
        for key, activation in tuple(self._activations.items()):
            if current >= activation.expires_at:
                self._activations.pop(key, None)
        return tuple(dict.fromkeys(expired))

    def clear(self) -> None:
        self._activations.clear()
