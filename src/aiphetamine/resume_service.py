"""Deterministic local poll-cycle orchestration for resume attempts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from .domain import CandidateSession, ResumeLaunchResult
from .repositories import CandidateRepository, RateLimitEventRepository
from .resume import evaluate_resume
from .selection import InMemorySelectionStore


@dataclass(frozen=True)
class PollOutcome:
    session_id: str
    status: str


class RuntimePollCycle:
    def __init__(
        self,
        candidates_root: Path,
        rate_limits_root: Path,
        selection_store: InMemorySelectionStore,
        executor: object,
        candidate_provider: Callable[[datetime], Iterable[CandidateSession]] | None = None,
        repair_permissions: bool = True,
    ) -> None:
        self._candidate_repository = CandidateRepository(
            candidates_root, repair_permissions=repair_permissions
        )
        self._event_repository = RateLimitEventRepository(
            rate_limits_root, repair_permissions=repair_permissions
        )
        self._selection_store = selection_store
        self._executor = executor
        self._candidate_provider = candidate_provider

    def initialize(self) -> int:
        return self._event_repository.cleanup_on_startup()

    def run(self, now_utc: datetime) -> tuple[PollOutcome, ...]:
        candidate_map, events = self._read_cycle_state(now_utc)
        processing: set[str] = set()
        outcomes: list[PollOutcome] = []

        for event in events:
            decision = evaluate_resume(
                event,
                candidate_map,
                self._selection_store,
                now_utc,
                processing,
            )
            if decision.status != "eligible":
                outcomes.append(PollOutcome(event.session_id, decision.status))
                continue
            processing.add(event.session_id)
            processing_path = self._event_repository.claim(event)
            if processing_path is None:
                processing.remove(event.session_id)
                outcomes.append(PollOutcome(event.session_id, "claim_failed"))
                continue
            try:
                result: ResumeLaunchResult = self._executor.launch(decision.request)
            except Exception:
                self._event_repository.restore(processing_path)
                outcomes.append(PollOutcome(event.session_id, "restored"))
            else:
                if result.launched:
                    self._event_repository.complete(processing_path)
                    outcomes.append(PollOutcome(event.session_id, "completed"))
                else:
                    self._event_repository.restore(processing_path)
                    outcomes.append(PollOutcome(event.session_id, "restored"))
            finally:
                processing.remove(event.session_id)
        return tuple(outcomes)

    def preview(self, now_utc: datetime) -> tuple[PollOutcome, ...]:
        """Return eligibility outcomes without claiming or changing event files."""

        candidate_map, events = self._read_cycle_state(now_utc)
        processing: set[str] = set()
        return tuple(
            PollOutcome(
                event.session_id,
                evaluate_resume(
                    event,
                    candidate_map,
                    self._selection_store,
                    now_utc,
                    processing,
                ).status,
            )
            for event in events
        )

    def _read_cycle_state(self, now_utc: datetime):
        candidates = (
            list(self._candidate_provider(now_utc))
            if self._candidate_provider is not None
            else self._candidate_repository.list_candidates(now=now_utc)
        )
        candidate_map: dict[str, CandidateSession] = {}
        ambiguous: set[str] = set()
        for candidate in candidates:
            if candidate.session_id in ambiguous:
                continue
            if candidate.session_id in candidate_map:
                ambiguous.add(candidate.session_id)
                candidate_map.pop(candidate.session_id, None)
                continue
            candidate_map[candidate.session_id] = candidate
        self._selection_store.expire_due(now_utc)
        events = self._event_repository.list_events(now=now_utc)
        return candidate_map, events
