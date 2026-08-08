"""Sanitized local logging for the AIphetamine runtime."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


_COMPONENTS = frozenset(
    {"runtime", "resume_service", "scheduler", "menu", "launch_agent", "hook"}
)
_EVENTS = frozenset(
    {
        "startup_completed",
        "poll_started",
        "poll_completed",
        "poll_failed",
        "schedule_created",
        "schedule_skipped",
        "menu_refreshed",
        "launch_at_login_changed",
        "hook_record_written",
        "hook_record_removed",
    }
)
_ERROR_CLASSES = frozenset(
    {"config_error", "filesystem_error", "launch_error", "os_error", "unknown"}
)
_CORRELATION_ID = re.compile(r"^[0-9a-f]{12}$")


class SanitizedLogger:
    """Write only allowlisted operational fields to seven-day local logs."""

    def __init__(self, logs_root: Path, *, salt: bytes | None = None) -> None:
        logs_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._salt = salt if salt is not None else secrets.token_bytes(32)
        self._handler = TimedRotatingFileHandler(
            logs_root / "aiphetamine.log",
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        try:
            os.chmod(logs_root / "aiphetamine.log", 0o600)
        except OSError:
            pass
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")
        )
        self._logger = logging.getLogger(f"aiphetamine.runtime.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._logger.addHandler(self._handler)

    @property
    def backup_count(self) -> int:
        return self._handler.backupCount

    @property
    def rotation_when(self) -> str:
        return self._handler.when

    def correlation_id(self, session_id: str) -> str:
        digest = hashlib.sha256(self._salt + session_id.encode("utf-8")).hexdigest()
        return digest[:12]

    def record(
        self,
        *,
        component: str,
        event: str,
        correlation_id: str | None = None,
        error_class: str | None = None,
    ) -> None:
        safe_component = component if component in _COMPONENTS else "runtime"
        safe_event = event if event in _EVENTS else "poll_failed"
        fields = [safe_component, safe_event]
        if correlation_id is not None and _CORRELATION_ID.fullmatch(correlation_id):
            fields.append(f"correlation_id={correlation_id}")
        if error_class is not None:
            safe_error = error_class if error_class in _ERROR_CLASSES else "unknown"
            fields.append(f"error_class={safe_error}")
        self._logger.info(" ".join(fields))

    def close(self) -> None:
        self._logger.removeHandler(self._handler)
        self._handler.close()
