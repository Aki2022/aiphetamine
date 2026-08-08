import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.domain import CandidateSession
from aiphetamine.session_metadata import SessionMetadataResolver


UTC = timezone.utc


class SessionMetadataTests(unittest.TestCase):
    def test_explicit_event_account_is_not_overwritten_by_detected_account(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            projects = root / "projects"
            projects.mkdir()
            session_id = "session-explicit-alias"
            (projects / f"{session_id}.jsonl").write_text(
                json.dumps({"customTitle": "Alias session"}) + "\n", encoding="utf-8"
            )
            candidate = CandidateSession(
                1,
                "candidate",
                session_id,
                root,
                datetime(2026, 7, 21, 12, tzinfo=UTC),
                account_name="alias",
            )

            enriched = SessionMetadataResolver((("main", root),)).enrich(candidate)

            self.assertEqual(enriched.account_name, "alias")
            self.assertEqual(enriched.session_name, "Alias session")


if __name__ == "__main__":
    unittest.main()
