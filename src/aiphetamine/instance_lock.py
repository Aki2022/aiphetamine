"""Single-process guard for the per-user AIphetamine runtime."""

from __future__ import annotations

import fcntl
import os
import stat
from pathlib import Path

from .filesystem_security import open_private_directory


class InstanceLock:
    """Hold an advisory lock on a descriptor-relative, private lock file."""

    def __init__(self, data_root: Path):
        self._fd = -1
        parent_fd = open_private_directory(data_root)
        try:
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_CLOEXEC", 0)
            self._fd = os.open("instance.lock", flags, 0o600, dir_fd=parent_fd)
            file_stat = os.fstat(self._fd)
            current_uid = getattr(os, "geteuid", os.getuid)()
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or file_stat.st_uid != current_uid
                or stat.S_IMODE(file_stat.st_mode) & 0o077
            ):
                raise OSError("unsafe_instance_lock")
            os.fchmod(self._fd, 0o600)
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError("instance_already_running") from error
        except BaseException:
            if self._fd >= 0:
                os.close(self._fd)
                self._fd = -1
            raise
        finally:
            os.close(parent_fd)

    def close(self) -> None:
        if self._fd < 0:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = -1
