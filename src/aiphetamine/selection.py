"""Ephemeral activation state for candidate sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .domain import CandidateSession


UTC = timezone.utc


@dataclass(frozen=True)
class SessionActivation:
    session_id: str
    activated_at: datetime
    expires_at: datetime
    resolved_project_path: Path
    project_device: int
    project_inode: int


class InMemorySelectionStore:
    def __init__(self) -> None:
        self._activations: dict[str, SessionActivation] = {}

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
        )
        self._activations[candidate.session_id] = activation
        return activation

    def deactivate(self, session_id: str) -> None:
        self._activations.pop(session_id, None)

    def is_selected(self, session_id: str) -> bool:
        return session_id in self._activations

    def get(self, session_id: str) -> SessionActivation | None:
        return self._activations.get(session_id)

    def is_expired(self, session_id: str, now_utc: datetime) -> bool:
        activation = self._activations.get(session_id)
        return activation is not None and now_utc.astimezone(UTC) >= activation.expires_at

    def expire_due(self, now_utc: datetime) -> tuple[str, ...]:
        current = now_utc.astimezone(UTC)
        expired = tuple(
            session_id
            for session_id, activation in self._activations.items()
            if current >= activation.expires_at
        )
        for session_id in expired:
            self._activations.pop(session_id, None)
        return expired

    def clear(self) -> None:
        self._activations.clear()
