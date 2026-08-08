"""Print a Claude Code Hook settings fragment without editing settings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.hook_setup import build_hook_settings_fragment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hook-command", required=True)
    parser.add_argument("--account-name")
    args = parser.parse_args()
    print(json.dumps(build_hook_settings_fragment(args.hook_command, args.account_name), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
