import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.app_runtime import ApplicationRuntime, PollStatus
from aiphetamine.domain import session_key


UTC = timezone.utc


class AppShellTests(unittest.TestCase):
    def test_poll_status_keeps_only_sanitized_result_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = ApplicationRuntime(root)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)

            class FakeExecutor:
                def launch(self, request):
                    del request
                    from aiphetamine.domain import ResumeLaunchResult

                    return ResumeLaunchResult(True, 1, None)

            runtime.run_poll(now, FakeExecutor())

            self.assertIsInstance(runtime.last_poll_status, PollStatus)
            self.assertEqual(runtime.last_poll_status.status_counts, ())
            self.assertEqual(runtime.last_poll_status.boundary, now)
            runtime.close()

    def test_candidates_reconstruct_from_unmatched_rate_limit_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "candidates").mkdir()
            rate_limits = root / "rate_limits"
            rate_limits.mkdir()
            session_id = "session-alias-rate-limit"
            rate_limits.joinpath(f"{session_key(session_id)}.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": "rate_limit",
                        "reason": "rate_limit",
                        "session_id": session_id,
                        "project_path": str(root),
                        "updated_at": "2026-07-21T11:59:00+00:00",
                        "account_name": "alias",
                    }
                ),
                encoding="utf-8",
            )

            candidates = ApplicationRuntime(root).candidates(
                datetime(2026, 7, 21, 12, tzinfo=UTC)
            )

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].account_name, "alias")
            self.assertEqual(candidates[0].session_id, session_id)

    def test_startup_initializes_directories_cleans_events_and_computes_next_boundary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            rate_limits = root / "rate_limits"
            candidates.mkdir()
            rate_limits.mkdir()
            candidate_id = "session-startup"
            candidate_path = candidates / f"{session_key(candidate_id)}.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": "candidate",
                        "session_id": candidate_id,
                        "project_path": str(root),
                        "updated_at": "2026-07-21T11:59:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            (rate_limits / "old.json").write_text("event", encoding="utf-8")
            now = datetime(2026, 7, 21, 21, 10, tzinfo=ZoneInfo("Asia/Tokyo"))

            snapshot = ApplicationRuntime(root).startup(now)

            self.assertEqual(snapshot.candidate_count, 1)
            self.assertEqual(snapshot.cleaned_event_count, 1)
            self.assertEqual(snapshot.next_boundary.hour, 22)
            self.assertTrue(candidate_path.exists())
            self.assertFalse((rate_limits / "old.json").exists())
            self.assertTrue((root / "logs").is_dir())

    def test_startup_preserves_fresh_valid_rate_limit_events_for_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "candidates").mkdir()
            rate_limits = root / "rate_limits"
            rate_limits.mkdir()
            session_id = "session-preserve-on-restart"
            event_path = rate_limits / f"{session_key(session_id)}.json"
            event_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": "rate_limit",
                        "reason": "rate_limit",
                        "session_id": session_id,
                        "project_path": str(root),
                        "updated_at": "2026-07-21T11:59:00+00:00",
                    }
                ),
                encoding="utf-8",
            )

            snapshot = ApplicationRuntime(root).startup(
                datetime(2026, 7, 21, 12, tzinfo=UTC)
            )

            self.assertEqual(snapshot.cleaned_event_count, 0)
            self.assertEqual(snapshot.event_count, 1)
            self.assertTrue(event_path.exists())

    def test_dry_run_is_read_only_and_reports_only_sanitized_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            rate_limits = root / "rate_limits"
            candidates.mkdir()
            rate_limits.mkdir()
            session_id = "session-dry-run"
            candidate = {
                "schema_version": 1,
                "record_type": "candidate",
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
            }
            event = {
                **candidate,
                "record_type": "rate_limit",
                "reason": "rate_limit",
            }
            candidate_path = candidates / f"{session_key(session_id)}.json"
            event_path = rate_limits / f"{session_key(session_id)}.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            event_path.write_text(json.dumps(event), encoding="utf-8")
            before = (candidate_path.read_bytes(), event_path.read_bytes())

            report = ApplicationRuntime(root).dry_run(
                datetime(2026, 7, 21, 21, 10, tzinfo=UTC)
            )
            output = report.as_dict()

            self.assertEqual(output["mode"], "dry-run")
            self.assertEqual(output["candidate_count"], 1)
            self.assertEqual(output["event_count"], 1)
            self.assertEqual(output["status_counts"], {"unselected": 1})
            self.assertNotIn(session_id, json.dumps(output))
            self.assertNotIn(str(root), json.dumps(output))
            self.assertEqual(before, (candidate_path.read_bytes(), event_path.read_bytes()))

    def test_dry_run_script_outputs_safe_json_without_launching_claude(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "candidates").mkdir()
            (root / "rate_limits").mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_dry_cycle.py",
                    "--data-root",
                    str(root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            output = json.loads(result.stdout)
            self.assertEqual(output["mode"], "dry-run")
            self.assertNotIn(str(root), result.stdout)
            self.assertNotIn("claude", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
