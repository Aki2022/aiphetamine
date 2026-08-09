"""Generate local LaunchAgent artifacts without registering them."""

from __future__ import annotations

import plistlib
from dataclasses import dataclass
from pathlib import Path

from .filesystem_security import atomic_write_bytes, ensure_private_directory, ensure_private_file


LABEL = "local.aiphetamine.menubar"
PLIST_NAME = f"{LABEL}.plist"


@dataclass(frozen=True)
class LaunchAgentSpec:
    python_executable: str
    module: str
    entrypoint: Path | None = None


class LaunchAgentManager:
    """Owns only generated plist files; registration remains a human action."""

    def __init__(self, launch_agents_root: Path) -> None:
        self._root = launch_agents_root

    @property
    def plist_path(self) -> Path:
        return self._root / PLIST_NAME

    def write_plist(self, spec: LaunchAgentSpec) -> Path:
        executable = Path(spec.python_executable)
        if not executable.is_absolute() or not spec.module:
            raise ValueError("invalid_launch_agent_spec")
        arguments = [str(executable), "-m", spec.module]
        if spec.entrypoint is not None:
            if not spec.entrypoint.is_absolute():
                raise ValueError("invalid_launch_agent_spec")
            arguments = [str(executable), str(spec.entrypoint)]
        payload = {
            "Label": LABEL,
            "ProgramArguments": arguments,
            "RunAtLoad": True,
            "KeepAlive": False,
        }
        encoded = plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)
        ensure_private_directory(self._root)
        ensure_private_file(self.plist_path)
        atomic_write_bytes(self.plist_path, encoded)
        return self.plist_path

    def is_generated(self) -> bool:
        try:
            ensure_private_directory(self._root)
            ensure_private_file(self.plist_path)
        except OSError:
            return False
        return self.plist_path.is_file() and not self.plist_path.is_symlink()
