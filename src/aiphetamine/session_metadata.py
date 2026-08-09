"""Read-only, allowlisted session labels for the menu bar."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from dataclasses import replace
from pathlib import Path

from .domain import CandidateSession
from .filesystem_security import is_secure_account_directory, open_private_directory


_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class SessionMetadataResolver:
    def __init__(self, account_roots: tuple[tuple[str, Path], ...]):
        self._account_roots = account_roots

    def enrich(self, candidate: CandidateSession) -> CandidateSession:
        account_roots = self._account_roots
        if candidate.account_name is not None:
            account_roots = tuple(
                (label, root) for label, root in account_roots if label == candidate.account_name
            )
        _detected_account, session_name = self._session_label(candidate.session_id, account_roots)
        return replace(
            candidate,
            # Account identity must come from the Hook/repository record.  The
            # Claude transcript tree is presentation metadata only; inferring a
            # label here would turn an unlabeled candidate into a resumable one.
            account_name=candidate.account_name,
            session_name=candidate.session_name or session_name,
            project_name=candidate.project_name or _repository_name(candidate.project_path),
        )

    def _session_label(
        self,
        session_id: str,
        account_roots: tuple[tuple[str, Path], ...] | None = None,
    ) -> tuple[str | None, str | None]:
        if not isinstance(session_id, str) or not _SAFE_SESSION_ID.fullmatch(session_id):
            return None, None
        matches: list[tuple[str, str | None]] = []
        roots = self._account_roots if account_roots is None else account_roots
        for label, root in roots:
            if not is_secure_account_directory(root):
                continue
            projects = root / "projects"
            if not is_secure_account_directory(projects):
                continue
            try:
                projects_fd = open_private_directory(projects)
            except OSError:
                continue
            try:
                for title in _matching_titles(projects_fd, f"{session_id}.jsonl"):
                    matches.append((label, title))
                    if len(matches) > 1:
                        return None, None
            except OSError:
                continue
            finally:
                os.close(projects_fd)
        if len(matches) != 1:
            return None, None
        return matches[0]


def _matching_titles(directory_fd: int, filename: str):
    try:
        entries = list(os.scandir(directory_fd))
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_symlink():
                continue
            if entry.is_file(follow_symlinks=False) and entry.name == filename:
                yield _custom_title_at(directory_fd, entry.name)
                continue
            if not entry.is_dir(follow_symlinks=False):
                continue
            child_fd = os.open(
                entry.name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=directory_fd,
            )
            try:
                child_stat = os.fstat(child_fd)
                current_uid = getattr(os, "geteuid", os.getuid)()
                if child_stat.st_uid not in {current_uid, 0} or stat.S_IMODE(child_stat.st_mode) & 0o022:
                    continue
                yield from _matching_titles(child_fd, filename)
            finally:
                os.close(child_fd)
        except OSError:
            continue


def _custom_title_at(directory_fd: int, filename: str) -> str | None:
    descriptor = -1
    try:
        descriptor = os.open(
            filename,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=directory_fd,
        )
        file_stat = os.fstat(descriptor)
        current_uid = getattr(os, "geteuid", os.getuid)()
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid != current_uid
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise OSError("unsafe_transcript")
        with os.fdopen(descriptor, encoding="utf-8") as stream:
            descriptor = -1
            for line in stream:
                value = json.loads(line)
                title = value.get("customTitle") if isinstance(value, dict) else None
                if isinstance(title, str) and title.strip():
                    return title
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
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
