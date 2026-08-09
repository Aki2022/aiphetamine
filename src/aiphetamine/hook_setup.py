"""Generate a Claude Code Hook settings fragment without editing settings."""

from __future__ import annotations

import shlex


_ALLOWED_ACCOUNT_NAMES = frozenset(("main", "alias"))

def build_hook_settings_fragment(command: str, account_name: str | None = None) -> dict[str, object]:
    if not isinstance(command, str) or not command.strip() or "\n" in command or "\r" in command:
        raise ValueError("invalid_hook_command")
    if account_name is not None and (
        not isinstance(account_name, str) or account_name not in _ALLOWED_ACCOUNT_NAMES
    ):
        raise ValueError("invalid_account_name")

    def entry(event: str, *, matcher: str | None = None) -> list[dict[str, object]]:
        account_suffix = f" --account-name {shlex.quote(account_name)}" if account_name is not None else ""
        item: dict[str, object] = {
            "hooks": [{"type": "command", "command": f"{command} --event {shlex.quote(event)}{account_suffix}"}]
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
