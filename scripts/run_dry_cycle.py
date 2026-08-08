#!/usr/bin/env python3
"""Inspect local AIphetamine state without changing files or launching Claude."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from aiphetamine.app_runtime import ApplicationRuntime  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path.home() / ".local" / "share" / "aiphetamine",
    )
    args = parser.parse_args()
    try:
        report = ApplicationRuntime(args.data_root).dry_run(datetime.now().astimezone())
    except (OSError, ValueError, TypeError):
        print(json.dumps({"mode": "dry-run", "error": "invalid_data_root"}))
        return 2
    print(json.dumps(report.as_dict(), ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
