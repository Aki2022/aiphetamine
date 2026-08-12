"""Emit sanitized Hook evidence without retaining the original payload."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

# Allow the Hook command to run from Claude's current working directory without
# requiring a shell-specific PYTHONPATH assignment.
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.spikes.hook_payload import redact_hook_payload


def capture_payload(stdin: TextIO, stdout: TextIO) -> int:
    """Read one JSON payload and write only safe evidence to stdout."""

    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
        evidence = {
            "schema_version": 1,
            "accepted": False,
            "error_code": "invalid_json",
        }
    else:
        evidence = redact_hook_payload(payload)

    json.dump(evidence, stdout, ensure_ascii=False, sort_keys=True)
    stdout.write("\n")
    return 0


if __name__ == "__main__":
    # Hook stdout is a control channel. Keep evidence on stderr so Stop and
    # other lifecycle hooks cannot mistake it for a hook decision response.
    raise SystemExit(capture_payload(sys.stdin, sys.stderr))
