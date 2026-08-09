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

            enriched = SessionMetadataResolver((("alias", root),)).enrich(candidate)

            self.assertEqual(enriched.account_name, "alias")
            self.assertEqual(enriched.session_name, "Alias session")

    def test_duplicate_session_id_across_accounts_is_not_assigned(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            session_id = "duplicate-session"
            account_roots = []
            for label in ("main", "alias"):
                account_root = root / label
                projects = account_root / "projects"
                projects.mkdir(parents=True)
                (projects / f"{session_id}.jsonl").write_text(
                    json.dumps({"customTitle": f"{label} session"}) + "\n", encoding="utf-8"
                )
                account_roots.append((label, account_root))

            resolver = SessionMetadataResolver(tuple(account_roots))

            self.assertEqual(resolver._session_label(session_id), (None, None))

    def test_explicit_account_scopes_metadata_lookup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main_projects = root / "main" / "projects"
            alias_projects = root / "alias" / "projects"
            main_projects.mkdir(parents=True)
            alias_projects.mkdir(parents=True)
            session_id = "scoped-session"
            (main_projects / f"{session_id}.jsonl").write_text(
                json.dumps({"customTitle": "wrong account"}) + "\n", encoding="utf-8"
            )
            (alias_projects / f"{session_id}.jsonl").write_text(
                json.dumps({"customTitle": "alias account"}) + "\n", encoding="utf-8"
            )
            candidate = CandidateSession(
                1,
                "candidate",
                session_id,
                root,
                datetime(2026, 7, 21, 12, tzinfo=UTC),
                account_name="alias",
            )

            enriched = SessionMetadataResolver(
                (("main", root / "main"), ("alias", root / "alias"))
            ).enrich(candidate)

            self.assertEqual(enriched.account_name, "alias")
            self.assertEqual(enriched.session_name, "alias account")


if __name__ == "__main__":
    unittest.main()
