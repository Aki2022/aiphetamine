"""Generate a Claude Code Hook settings fragment without editing settings."""

from __future__ import annotations


def build_hook_settings_fragment(command: str, account_name: str | None = None) -> dict[str, object]:
    if not command or "\n" in command or "\r" in command:
        raise ValueError("invalid_hook_command")

    def entry(event: str, *, matcher: str | None = None) -> list[dict[str, object]]:
        item: dict[str, object] = {
            "hooks": [{"type": "command", "command": f"{command} --event {event}" + (f" --account-name {account_name}" if account_name else "")}]
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
