"""Read-only validation of the future Claude executable configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path


def load_claude_executable(config_path: Path) -> Path | None:
    if config_path.is_symlink() or not config_path.is_file():
        return None
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    executable = value.get("claude_executable") if isinstance(value, dict) else None
    if not isinstance(executable, str) or not executable:
        return None
    path = Path(executable)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        return None
    try:
        return path if os.access(path, os.X_OK) else None
    except OSError:
        return None
