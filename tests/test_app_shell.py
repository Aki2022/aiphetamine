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

from aiphetamine.app_runtime import ApplicationRuntime, PollStatus, read_only_dry_run
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
            (root / "candidates").mkdir(mode=0o700)
            rate_limits = root / "rate_limits"
            rate_limits.mkdir(mode=0o700)
            (rate_limits / "alias").mkdir(mode=0o700)
            session_id = "session-alias-rate-limit"
            rate_limits.joinpath("alias", f"{session_key(session_id)}.json").write_text(
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

    def test_candidates_do_not_reconstruct_deleted_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "candidates").mkdir(mode=0o700)
            rate_limits = root / "rate_limits"
            rate_limits.mkdir(mode=0o700)
            (rate_limits / "alias").mkdir(mode=0o700)
            session_id = "session-deleted-project"
            (rate_limits / "alias" / f"{session_key(session_id)}.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": "rate_limit",
                        "reason": "rate_limit",
                        "session_id": session_id,
                        "project_path": str(root / "deleted-project"),
                        "updated_at": "2026-07-21T11:59:00+00:00",
                        "account_name": "alias",
                    }
                ),
                encoding="utf-8",
            )

            candidates = ApplicationRuntime(root).candidates(
                datetime(2026, 7, 21, 12, tzinfo=UTC)
            )

            self.assertEqual(candidates, ())

    def test_candidates_do_not_reconstruct_symlinked_project(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            (root / "candidates").mkdir(mode=0o700)
            rate_limits = root / "rate_limits"
            rate_limits.mkdir(mode=0o700)
            (rate_limits / "alias").mkdir(mode=0o700)
            project = root / "project"
            project.mkdir(mode=0o700)
            project_link = root / "project-link"
            project_link.symlink_to(project, target_is_directory=True)
            session_id = "session-symlink-project"
            (rate_limits / "alias" / f"{session_key(session_id)}.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": "rate_limit",
                        "reason": "rate_limit",
                        "session_id": session_id,
                        "project_path": str(project_link),
                        "updated_at": "2026-07-21T11:59:00+00:00",
                        "account_name": "alias",
                    }
                ),
                encoding="utf-8",
            )

            candidates = ApplicationRuntime(root).candidates(
                datetime(2026, 7, 21, 12, tzinfo=UTC)
            )

            self.assertEqual(candidates, ())

    def test_unavailable_candidate_blocks_same_id_event_reconstruction(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates" / "main"
            events = root / "rate_limits" / "main"
            candidates.mkdir(parents=True, mode=0o700)
            events.mkdir(parents=True, mode=0o700)
            session_id = "session-unavailable-candidate"
            candidate = {
                "schema_version": 1,
                "record_type": "candidate",
                "session_id": session_id,
                "project_path": str(root / "deleted-project"),
                "updated_at": "2026-07-21T11:59:00+00:00",
                "account_name": "main",
            }
            event = {
                **candidate,
                "record_type": "rate_limit",
                "reason": "rate_limit",
                "project_path": str(root),
            }
            key = session_key(session_id)
            (candidates / f"{key}.json").write_text(json.dumps(candidate), encoding="utf-8")
            (events / f"{key}.json").write_text(json.dumps(event), encoding="utf-8")

            runtime = ApplicationRuntime(root)
            try:
                self.assertEqual(
                    runtime.candidates(datetime(2026, 7, 21, 12, tzinfo=UTC)), ()
                )
            finally:
                runtime.close()

    def test_malformed_project_path_is_ignored_without_runtime_crash(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates" / "main"
            candidates.mkdir(parents=True, mode=0o700)
            session_id = "session-malformed-project"
            payload = {
                "schema_version": 1,
                "record_type": "candidate",
                "session_id": session_id,
                "project_path": f"{root}\ud800",
                "updated_at": "2026-07-21T11:59:00+00:00",
                "account_name": "main",
            }
            (candidates / f"{session_key(session_id)}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

            runtime = ApplicationRuntime(root)
            try:
                self.assertEqual(
                    runtime.candidates(datetime(2026, 7, 21, 12, tzinfo=UTC)), ()
                )
            finally:
                runtime.close()

    def test_startup_initializes_directories_cleans_events_and_computes_next_boundary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            rate_limits = root / "rate_limits"
            candidates.mkdir(mode=0o700)
            rate_limits.mkdir(mode=0o700)
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
            (root / "candidates").mkdir(mode=0o700)
            rate_limits = root / "rate_limits"
            rate_limits.mkdir(mode=0o700)
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
            candidates.mkdir(mode=0o700)
            rate_limits.mkdir(mode=0o700)
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
            candidate_path.chmod(0o600)
            event_path.chmod(0o600)
            before = (candidate_path.read_bytes(), event_path.read_bytes())

            report = read_only_dry_run(
                root,
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

    def test_dry_run_does_not_repair_loose_file_permissions(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            rate_limits = root / "rate_limits"
            candidates.mkdir(mode=0o700)
            rate_limits.mkdir(mode=0o700)
            session_id = "session-dry-permissions"
            payload = {
                "schema_version": 1,
                "record_type": "candidate",
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
            }
            candidate_path = candidates / f"{session_key(session_id)}.json"
            event_path = rate_limits / f"{session_key(session_id)}.json"
            candidate_path.write_text(json.dumps(payload), encoding="utf-8")
            event_path.write_text(
                json.dumps({**payload, "record_type": "rate_limit", "reason": "rate_limit"}),
                encoding="utf-8",
            )
            candidate_path.chmod(0o644)
            event_path.chmod(0o644)

            read_only_dry_run(root, datetime(2026, 7, 21, 12, tzinfo=UTC))

            self.assertEqual(candidate_path.stat().st_mode & 0o777, 0o644)
            self.assertEqual(event_path.stat().st_mode & 0o777, 0o644)

    def test_dry_run_script_outputs_safe_json_without_launching_claude(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "missing-data-root"
            before = list(root.parent.iterdir())
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
            self.assertEqual(list(root.parent.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
