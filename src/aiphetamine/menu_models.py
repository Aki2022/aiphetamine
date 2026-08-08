"""Pure presentation models for the macOS menu bar."""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .domain import CandidateSession, session_key
from .selection import InMemorySelectionStore


@dataclass(frozen=True)
class SessionMenuRow:
    session_id: str
    title: str
    checked: bool
    status: str = ""


def sanitize_menu_text(value: str | None, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = unicodedata.normalize("NFC", value)
    visible = "".join(
        char
        for char in normalized
        if char.isspace() or not unicodedata.category(char).startswith("C")
    )
    compact = " ".join(visible.split())
    if not compact:
        return fallback
    return compact if len(compact) <= 40 else f"{compact[:39]}…"


def build_session_rows(
    candidates: Iterable[CandidateSession], selection_store: InMemorySelectionStore, *, selectable_only: bool = False
) -> tuple[SessionMenuRow, ...]:
    candidate_list = tuple(
        candidate
        for candidate in candidates
        if not selectable_only or candidate.account_name
    )
    base_titles = {
        candidate.session_id: _base_title(candidate)
        for candidate in candidate_list
    }
    duplicates = Counter(base_titles.values())
    rows = []
    for candidate in candidate_list:
        title = base_titles[candidate.session_id]
        if duplicates[title] > 1:
            title = f"{title} · {candidate.session_id[:8]}"
        rows.append(
            SessionMenuRow(
                session_id=candidate.session_id,
                title=title,
                checked=selection_store.is_selected(candidate.session_id),
            )
        )
    return tuple(rows)


def _base_title(candidate: CandidateSession) -> str:
    session_name = sanitize_menu_text(
        candidate.session_name,
        fallback=f"セッション {session_key(candidate.session_id)[:8]}",
    )
    project_name = sanitize_menu_text(
        candidate.project_name,
        fallback=sanitize_menu_text(candidate.project_path.name, fallback="プロジェクト不明"),
    )
    account_name = sanitize_menu_text(candidate.account_name, fallback="アカウント不明")
    return f"{account_name} / {project_name} — {session_name}"
