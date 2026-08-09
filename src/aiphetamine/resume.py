"""Local resume eligibility decisions; no Claude process is started here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .domain import CandidateSession, RateLimitEvent, ResumeRequest
from .selection import InMemorySelectionStore


UTC = timezone.utc


@dataclass(frozen=True)
class ResumeDecision:
    status: str
    request: ResumeRequest | None = None


def _same_project_identity(left: Path, right: Path) -> tuple[bool, Path | None]:
    try:
        left_resolved = left.resolve(strict=True)
        right_resolved = right.resolve(strict=True)
        if not left_resolved.is_dir() or not right_resolved.is_dir():
            return False, None
        left_stat = left_resolved.stat()
        right_stat = right_resolved.stat()
    except OSError:
        return False, None
    if left_resolved != right_resolved:
        return False, None
    if (left_stat.st_dev, left_stat.st_ino) != (right_stat.st_dev, right_stat.st_ino):
        return False, None
    return True, left_resolved


def evaluate_resume(
    event: RateLimitEvent,
    candidates: dict[str, CandidateSession],
    selection_store: InMemorySelectionStore,
    now_utc: datetime,
    processing_session_ids: set[str] | None = None,
) -> ResumeDecision:
    processing = processing_session_ids or set()
    if not selection_store.is_selected(event.session_id):
        return ResumeDecision("unselected")
    if selection_store.is_expired(event.session_id, now_utc):
        return ResumeDecision("expired")
    if event.session_id in processing:
        return ResumeDecision("processing")
    candidate = candidates.get(event.session_id)
    if candidate is None:
        return ResumeDecision("candidate_missing")
    if event.account_name is None or candidate.account_name is None:
        return ResumeDecision("account_unknown")
    if event.account_name != candidate.account_name:
        return ResumeDecision("account_mismatch")
    if now_utc.astimezone(UTC) - candidate.updated_at > timedelta(hours=24):
        return ResumeDecision("candidate_stale")
    if now_utc.astimezone(UTC) - event.updated_at > timedelta(hours=12):
        return ResumeDecision("event_stale")
    matches, resolved = _same_project_identity(candidate.project_path, event.project_path)
    if not matches or resolved is None:
        return ResumeDecision("path_mismatch")
    activation = selection_store.get(event.session_id)
    if activation is None:
        return ResumeDecision("unselected")
    try:
        stat = resolved.stat()
    except OSError:
        return ResumeDecision("path_mismatch")
    if (
        activation.resolved_project_path != resolved
        or activation.project_device != stat.st_dev
        or activation.project_inode != stat.st_ino
    ):
        return ResumeDecision("path_mismatch")
    return ResumeDecision(
        "eligible",
        ResumeRequest(
            session_id=event.session_id,
            project_path=resolved,
            account_name=event.account_name,
        ),
    )
