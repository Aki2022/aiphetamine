"""Read-only, allowlisted session labels for the menu bar."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from .domain import CandidateSession


class SessionMetadataResolver:
    def __init__(self, account_roots: tuple[tuple[str, Path], ...]):
        self._account_roots = account_roots

    def enrich(self, candidate: CandidateSession) -> CandidateSession:
        account_name, session_name = self._session_label(candidate.session_id)
        project_name = candidate.project_name or _git_root_name(candidate.project_path)
        return replace(
            candidate,
            account_name=account_name,
            session_name=candidate.session_name or session_name,
            project_name=project_name,
        )

    def _session_label(self, session_id: str) -> tuple[str | None, str | None]:
        for label, root in self._account_roots:
            projects = root / "projects"
            if not projects.is_dir() or projects.is_symlink():
                continue
            try:
                paths = projects.rglob(f"{session_id}.jsonl")
                path = next(paths, None)
            except OSError:
                continue
            if path is None or path.is_symlink() or not path.is_file():
                continue
            return label, _custom_title(path)
        return None, None


def _custom_title(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                value = json.loads(line)
                title = value.get("customTitle") if isinstance(value, dict) else None
                if isinstance(title, str) and title.strip():
                    return title
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return None


def _git_root_name(path: Path) -> str | None:
    try:
        current = path.resolve(strict=True)
        while current != current.parent:
            if (current / ".git").exists():
                return current.name
            current = current.parent
    except OSError:
        return None
    return None
