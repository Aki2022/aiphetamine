"""Generate a Claude Code Hook settings fragment without editing settings."""

from __future__ import annotations

import shlex
import re


_ALLOWED_ACCOUNT_NAMES = frozenset(("main", "alias"))
_SHELL_METACHARACTERS = frozenset(";&|<>$`\n\r\x00")
_SHELL_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _normalize_hook_command(command: str) -> str:
    """Return a shell-safe command prefix without allowing shell syntax."""

    if (
        not isinstance(command, str)
        or not command.strip()
        or any(character in command for character in _SHELL_METACHARACTERS)
    ):
        raise ValueError("invalid_hook_command")
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError("invalid_hook_command") from exc
    if not argv:
        raise ValueError("invalid_hook_command")
    if any(_SHELL_ASSIGNMENT.match(argument) for argument in argv):
        raise ValueError("invalid_hook_command")
    return " ".join(shlex.quote(argument) for argument in argv)


def build_hook_settings_fragment(command: str, account_name: str | None = None) -> dict[str, object]:
    safe_command = _normalize_hook_command(command)
    if account_name is not None and (
        not isinstance(account_name, str) or account_name not in _ALLOWED_ACCOUNT_NAMES
    ):
        raise ValueError("invalid_account_name")

    def entry(event: str, *, matcher: str | None = None) -> list[dict[str, object]]:
        account_suffix = f" --account-name {shlex.quote(account_name)}" if account_name is not None else ""
        item: dict[str, object] = {
            "hooks": [
                {
                    "type": "command",
                    "command": f"{safe_command} --event {shlex.quote(event)}{account_suffix}",
                }
            ]
        }
        if matcher is not None:
            item["matcher"] = matcher
        return [item]

    return {
        "hooks": {
            "SessionStart": entry("SessionStart"),
            "UserPromptSubmit": entry("UserPromptSubmit"),
            "SessionEnd": entry("SessionEnd"),
            "StopFailure": entry("StopFailure", matcher="rate_limit"),
        }
    }
