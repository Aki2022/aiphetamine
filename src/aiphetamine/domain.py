"""Domain records for the repository-local Phase 1 foundation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class RateLimitEvent:
    schema_version: int
    record_type: str
    reason: str
    session_id: str
    project_path: Path
    updated_at: datetime
    source_file: Path | None = None
    account_name: str | None = None


@dataclass(frozen=True)
class CandidateSession:
    schema_version: int
    record_type: str
    session_id: str
    project_path: Path
    updated_at: datetime
    session_name: str | None = None
    project_name: str | None = None
    source_file: Path | None = None
    account_name: str | None = None


@dataclass(frozen=True)
class ResumeRequest:
    session_id: str
    project_path: Path
    message: str = "Continue"
    account_name: str | None = None
    expected_project_device: int | None = None
    expected_project_inode: int | None = None


@dataclass(frozen=True)
class ResumeLaunchResult:
    launched: bool
    pid: int | None
    error: str | None


def session_key(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8", errors="surrogatepass")).hexdigest()
