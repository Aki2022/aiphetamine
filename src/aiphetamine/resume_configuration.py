"""Read-only validation of the future Claude executable configuration."""

from __future__ import annotations

import json
from pathlib import Path

from .filesystem_security import (
    ensure_private_file,
    is_secure_account_directory,
    read_private_text,
    validate_external_executable,
)


def load_claude_executable(config_path: Path) -> Path | None:
    if not is_secure_account_directory(config_path.parent):
        return None
    try:
        ensure_private_file(config_path)
    except OSError:
        return None
    if not config_path.is_file() or config_path.is_symlink():
        return None
    try:
        value = json.loads(read_private_text(config_path))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        return None
    executable = value.get("claude_executable") if isinstance(value, dict) else None
    if not isinstance(executable, str) or not executable:
        return None
    path = Path(executable)
    if not path.is_absolute() or not validate_external_executable(path):
        return None
    return path
