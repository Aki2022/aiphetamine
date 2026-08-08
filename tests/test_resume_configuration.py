import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.resume_configuration import load_claude_executable


class ResumeConfigurationTests(unittest.TestCase):
    def test_accepts_only_existing_absolute_regular_executable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            executable = root / "claude"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(executable, 0o700)
            config = root / "config.json"
            config.write_text(json.dumps({"claude_executable": str(executable)}), encoding="utf-8")

            self.assertEqual(load_claude_executable(config), executable)

    def test_rejects_missing_invalid_and_symlink_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing = root / "missing.json"
            self.assertIsNone(load_claude_executable(missing))
            invalid = root / "invalid.json"
            invalid.write_text("[]", encoding="utf-8")
            self.assertIsNone(load_claude_executable(invalid))
            target = root / "target"
            target.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(target, 0o700)
            link = root / "link"
            link.symlink_to(target)
            config = root / "config.json"
            config.write_text(json.dumps({"claude_executable": str(link)}), encoding="utf-8")
            self.assertIsNone(load_claude_executable(config))


if __name__ == "__main__":
    unittest.main()
