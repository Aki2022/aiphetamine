"""Generate local LaunchAgent artifacts without registering them."""

from __future__ import annotations

import os
import plistlib
import tempfile
from dataclasses import dataclass
from pathlib import Path


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
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{PLIST_NAME}.", dir=self._root)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.plist_path)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        return self.plist_path

    def is_generated(self) -> bool:
        return self.plist_path.is_file() and not self.plist_path.is_symlink()
