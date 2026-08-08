"""Read-only, allowlisted session labels for the menu bar."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

from .domain import CandidateSession


class SessionMetadataResolver:
    def __init__(self, account_roots: tuple[tuple[str, Path], ...]):
        self._account_roots = account_roots

    def enrich(self, candidate: CandidateSession) -> CandidateSession:
        detected_account, session_name = self._session_label(candidate.session_id)
        return replace(
            candidate,
            account_name=candidate.account_name or detected_account,
            session_name=candidate.session_name or session_name,
            project_name=candidate.project_name or _repository_name(candidate.project_path),
        )

    def _session_label(self, session_id: str) -> tuple[str | None, str | None]:
        for label, root in self._account_roots:
            projects = root / "projects"
            if not projects.is_dir() or projects.is_symlink():
                continue
            try:
                path = next(projects.rglob(f"{session_id}.jsonl"), None)
            except OSError:
                continue
            if path is not None and path.is_file() and not path.is_symlink():
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


def _repository_name(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "config", "--get", "remote.origin.url"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _git_root_name(path)
    if result.returncode == 0:
        name = result.stdout.strip().removesuffix(".git").replace(":", "/").rstrip("/").split("/")[-1]
        if name:
            return name
    return _git_root_name(path)
