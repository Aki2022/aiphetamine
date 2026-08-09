"""Application startup and read-only dry-run wiring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from .domain import CandidateSession
from .filesystem_security import ensure_private_directory
from .instance_lock import InstanceLock
from .repositories import CandidateRepository, RateLimitEventRepository
from .resume_service import RuntimePollCycle
from .runtime_logging import SanitizedLogger
from .scheduling import next_boundary
from .selection import InMemorySelectionStore
from .session_metadata import SessionMetadataResolver


@dataclass(frozen=True)
class StartupSnapshot:
    candidate_count: int
    event_count: int
    cleaned_event_count: int
    next_boundary: datetime


@dataclass(frozen=True)
class PollStatus:
    """Sanitized in-memory result of the most recent live poll."""

    boundary: datetime
    status_counts: tuple[tuple[str, int], ...]

    @classmethod
    def from_outcomes(cls, boundary: datetime, outcomes) -> "PollStatus":
        counts: dict[str, int] = {}
        for outcome in outcomes:
            counts[outcome.status] = counts.get(outcome.status, 0) + 1
        return cls(boundary, tuple(sorted(counts.items())))


@dataclass(frozen=True)
class DryRunReport:
    candidate_count: int
    event_count: int
    next_boundary: datetime
    status_counts: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": "dry-run",
            "candidate_count": self.candidate_count,
            "event_count": self.event_count,
            "next_boundary": self.next_boundary.isoformat(),
            "status_counts": dict(sorted(self.status_counts.items())),
        }


class ApplicationRuntime:
    def __init__(self, data_root: Path, *, log_salt: bytes | None = None, session_metadata=None):
        self.data_root = data_root
        self.candidates_root = data_root / "candidates"
        self.rate_limits_root = data_root / "rate_limits"
        self.logs_root = data_root / "logs"
        ensure_private_directory(self.data_root)
        self._instance_lock = InstanceLock(self.data_root)
        self.selection_store = InMemorySelectionStore()
        self._logger = SanitizedLogger(self.logs_root, salt=log_salt)
        self._session_metadata = session_metadata
        self._poll_status_lock = Lock()
        self._last_poll_status: PollStatus | None = None

    @property
    def last_poll_status(self) -> PollStatus | None:
        with self._poll_status_lock:
            return self._last_poll_status

    def startup(self, now: datetime) -> StartupSnapshot:
        ensure_private_directory(self.data_root)
        for directory in (self.candidates_root, self.rate_limits_root, self.logs_root):
            ensure_private_directory(directory)
        event_repository = RateLimitEventRepository(self.rate_limits_root)
        cleaned = event_repository.cleanup_on_startup(now=now, preserve_fresh=True)
        candidates = CandidateRepository(self.candidates_root).list_candidates(now=now)
        events = event_repository.list_events(now=now)
        snapshot = StartupSnapshot(
            candidate_count=len(candidates),
            event_count=len(events),
            cleaned_event_count=cleaned,
            next_boundary=next_boundary(now),
        )
        self._logger.record(component="runtime", event="startup_completed")
        return snapshot

    def candidates(self, now: datetime):
        candidate_repository = CandidateRepository(self.candidates_root)
        candidates = candidate_repository.list_candidates(now=now)
        known_session_ids = {candidate.session_id for candidate in candidates}
        event_repository = RateLimitEventRepository(self.rate_limits_root)
        events = event_repository.list_events(now=now)
        ambiguous_session_ids = (
            candidate_repository.ambiguous_session_ids
            | event_repository.ambiguous_session_ids
        )
        for event in events:
            if (
                event.session_id in known_session_ids
                or event.session_id in ambiguous_session_ids
            ):
                continue
            candidates.append(
                CandidateSession(
                    schema_version=1,
                    record_type="candidate",
                    session_id=event.session_id,
                    project_path=event.project_path,
                    updated_at=event.updated_at,
                    account_name=event.account_name,
                )
            )
        candidates.sort(key=lambda candidate: candidate.session_id)
        if self._session_metadata is not None:
            candidates = [self._session_metadata.enrich(candidate) for candidate in candidates]
        return tuple(candidates)

    def activate(self, session_id: str, now: datetime) -> None:
        candidate = next(
            (candidate for candidate in self.candidates(now) if candidate.session_id == session_id),
            None,
        )
        if candidate is None:
            raise LookupError("candidate not available")
        self.selection_store.activate(candidate, now)

    def deactivate(self, session_id: str, account_name: str | None = None) -> None:
        self.selection_store.deactivate(session_id, account_name)

    def run_poll(self, now: datetime, executor: object):
        self._logger.record(component="resume_service", event="poll_started")
        try:
            outcomes = RuntimePollCycle(
                self.candidates_root,
                self.rate_limits_root,
                self.selection_store,
                executor,
                candidate_provider=self.candidates,
            ).run(now)
        except Exception:
            with self._poll_status_lock:
                self._last_poll_status = PollStatus(now, (("poll_failed", 1),))
            self._logger.record(
                component="resume_service", event="poll_failed", error_class="unknown"
            )
            raise
        with self._poll_status_lock:
            self._last_poll_status = PollStatus.from_outcomes(now, outcomes)
        self._logger.record(component="resume_service", event="poll_completed")
        return outcomes

    def close(self) -> None:
        self._logger.close()
        self._instance_lock.close()

    def __del__(self):
        try:
            lock = getattr(self, "_instance_lock", None)
            if lock is not None:
                lock.close()
        except Exception:
            pass

    def dry_run(self, now: datetime) -> DryRunReport:
        cycle = RuntimePollCycle(
            self.candidates_root,
            self.rate_limits_root,
            self.selection_store,
            executor=None,
            candidate_provider=self.candidates,
        )
        candidates = self.candidates(now)
        events = RateLimitEventRepository(self.rate_limits_root).list_events(now=now)
        outcomes = cycle.preview(now)
        status_counts: dict[str, int] = {}
        for outcome in outcomes:
            status_counts[outcome.status] = status_counts.get(outcome.status, 0) + 1
        return DryRunReport(
            candidate_count=len(candidates),
            event_count=len(events),
            next_boundary=next_boundary(now),
            status_counts=status_counts,
        )
