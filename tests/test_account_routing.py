import sys
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.__main__ import _claude2_config_root


class AccountRoutingTests(unittest.TestCase):
    def test_alias_config_root_is_explicit_and_supports_spaces(self):
        home = Path("/tmp/test home with spaces")

        self.assertEqual(_claude2_config_root(home), home / ".claude-seat2")


if __name__ == "__main__":
    unittest.main()
