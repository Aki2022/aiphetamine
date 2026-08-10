import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from aiphetamine.domain import session_key
from hooks.aiphetamine_hook import apply_event


UTC = timezone.utc


class ProductionHookTests(unittest.TestCase):
    def test_hook_creates_rate_limit_event_and_removes_candidate_without_echoing_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = {"session_id": "session-private", "cwd": str(root), "session_name": "private"}
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)

            self.assertEqual(apply_event(payload, "SessionStart", root, now), "written")
            key = session_key("session-private")
            self.assertEqual(apply_event(payload, "SessionEnd", root, now), "removed")
            self.assertFalse((root / "candidates" / f"{key}.json").exists())

            self.assertEqual(apply_event(payload, "SessionStart", root, now), "written")
            self.assertEqual(apply_event(payload, "StopFailure", root, now, "alias"), "written")
            rate_limit_record = next((root / "rate_limits" / "alias").glob("*.json"))
            self.assertEqual(json.loads(rate_limit_record.read_text())["account_name"], "alias")
            self.assertTrue((root / "candidates" / "unknown" / f"{key}.json").exists())
            self.assertTrue((root / "rate_limits" / "alias" / f"{key}.json").exists())

    def test_hook_preserves_candidate_when_rate_limit_event_exists_at_session_end(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = {"session_id": "session-rate-limit", "cwd": str(root)}
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            key = session_key(payload["session_id"])

            self.assertEqual(apply_event(payload, "SessionStart", root, now, "alias"), "written")
            self.assertEqual(apply_event(payload, "StopFailure", root, now, "alias"), "written")
            self.assertEqual(
                apply_event(payload, "SessionEnd", root, now), "preserved_for_rate_limit"
            )
            self.assertTrue((root / "candidates" / "alias" / f"{key}.json").exists())

    def test_unlabeled_session_end_does_not_delete_account_scoped_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = {"session_id": "session-ambiguous-end", "cwd": str(root)}
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            key = session_key(payload["session_id"])

            self.assertEqual(apply_event(payload, "SessionStart", root, now, "main"), "written")
            self.assertEqual(apply_event(payload, "SessionStart", root, now, "alias"), "written")
            self.assertEqual(
                apply_event(payload, "SessionEnd", root, now), "preserved_unlabeled"
            )
            self.assertTrue((root / "candidates" / "main" / f"{key}.json").exists())
            self.assertTrue((root / "candidates" / "alias" / f"{key}.json").exists())

    def test_hook_rejects_unallowlisted_account_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = {"session_id": "session-invalid-account", "cwd": str(root)}
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)

            self.assertEqual(
                apply_event(payload, "SessionStart", root, now, "main; touch /tmp/marker"),
                "invalid_account_name",
            )


if __name__ == "__main__":
    unittest.main()
