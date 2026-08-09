"""Sanitized local logging for the AIphetamine runtime."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import stat
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from .filesystem_security import ensure_private_directory, ensure_private_file, open_private_directory


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


class _SecureTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, *args, **kwargs):
        self._log_dir = Path(filename).absolute().parent
        self._log_name = Path(filename).name
        super().__init__(filename, *args, **kwargs)

    def _open(self):
        parent_fd = open_private_directory(self._log_dir)
        descriptor = -1
        try:
            flags = (
                os.O_WRONLY
                | os.O_APPEND
                | os.O_CREAT
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_CLOEXEC", 0)
            )
            descriptor = os.open(self._log_name, flags, 0o600, dir_fd=parent_fd)
            file_stat = os.fstat(descriptor)
            current_uid = getattr(os, "geteuid", os.getuid)()
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or file_stat.st_uid != current_uid
                or stat.S_IMODE(file_stat.st_mode) & 0o077
            ):
                raise OSError("unsafe_log_file")
            os.fchmod(descriptor, 0o600)
            return os.fdopen(
                descriptor,
                self.mode,
                encoding=self.encoding,
                errors=self.errors,
            )
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            raise
        finally:
            os.close(parent_fd)

    def doRollover(self):
        current_time = int(time.time())
        rollover_time = self.rolloverAt - self.interval
        time_tuple = time.gmtime(rollover_time) if self.utc else time.localtime(rollover_time)
        destination = self.rotation_filename(
            self.baseFilename + "." + time.strftime(self.suffix, time_tuple)
        )
        if self.stream:
            self.stream.close()
            self.stream = None
        parent_fd = open_private_directory(self._log_dir)
        try:
            source_stat = os.stat(self._log_name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_uid != getattr(
                os, "geteuid", os.getuid
            ):
                raise OSError("unsafe_log_file")
            destination_name = Path(destination).name
            try:
                destination_stat = os.stat(
                    destination_name, dir_fd=parent_fd, follow_symlinks=False
                )
            except FileNotFoundError:
                destination_stat = None
            if destination_stat is not None:
                if not stat.S_ISREG(destination_stat.st_mode) or destination_stat.st_uid != getattr(
                    os, "geteuid", os.getuid
                ):
                    raise OSError("unsafe_log_destination")
                os.unlink(destination_name, dir_fd=parent_fd)
            os.replace(
                self._log_name,
                destination_name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            for old_path in self.getFilesToDelete():
                old_name = Path(old_path).name
                try:
                    old_stat = os.stat(old_name, dir_fd=parent_fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if not stat.S_ISREG(old_stat.st_mode) or old_stat.st_uid != getattr(
                    os, "geteuid", os.getuid
                ):
                    raise OSError("unsafe_log_backup")
                os.unlink(old_name, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
        if not self.delay:
            self.stream = self._open()
        self.rolloverAt = self.computeRollover(current_time)


class SanitizedLogger:
    """Write only allowlisted operational fields to seven-day local logs."""

    def __init__(self, logs_root: Path, *, salt: bytes | None = None) -> None:
        ensure_private_directory(logs_root)
        log_path = logs_root / "aiphetamine.log"
        ensure_private_file(log_path)
        self._salt = salt if salt is not None else secrets.token_bytes(32)
        self._handler = _SecureTimedRotatingFileHandler(
            str(log_path),
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
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
