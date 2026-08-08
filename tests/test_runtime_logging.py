import sys
import tempfile
import unittest
import json
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.runtime_logging import SanitizedLogger
from aiphetamine.app_runtime import ApplicationRuntime
from aiphetamine.domain import ResumeLaunchResult, session_key


UTC = timezone.utc


class RuntimeLoggingTests(unittest.TestCase):
    def test_rotates_daily_and_never_writes_sensitive_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            logger = SanitizedLogger(root, salt=b"test-salt")

            correlation_id = logger.correlation_id("session-private-value")
            logger.record(
                component="resume_service",
                event="poll_started",
                correlation_id=correlation_id,
            )
            logger.record(
                component="resume_service",
                event="poll_failed",
                error_class="unexpected-private-detail",
            )
            logger.close()

            output = (root / "aiphetamine.log").read_text(encoding="utf-8")
            self.assertEqual(len(correlation_id), 12)
            self.assertIn("resume_service", output)
            self.assertIn("poll_started", output)
            self.assertIn("error_class=unknown", output)
            self.assertNotIn("session-private-value", output)
            self.assertNotIn(str(root), output)

    def test_handler_uses_midnight_rotation_and_seven_backups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = SanitizedLogger(Path(temp_dir), salt=b"test-salt")

            self.assertEqual(logger.backup_count, 7)
            self.assertEqual(logger.rotation_when, "MIDNIGHT")

            logger.close()

    def test_runtime_runs_injected_poll_cycle_and_logs_only_safe_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            runtime = ApplicationRuntime(root, log_salt=b"test-salt")
            runtime.startup(now)
            session_id = "session-private-value"
            candidate = {
                "schema_version": 1,
                "record_type": "candidate",
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
            }
            (root / "candidates" / f"{session_key(session_id)}.json").write_text(
                json.dumps(candidate), encoding="utf-8"
            )
            (root / "rate_limits" / f"{session_key(session_id)}.json").write_text(
                json.dumps({**candidate, "record_type": "rate_limit", "reason": "rate_limit"}),
                encoding="utf-8",
            )
            runtime.activate(session_id, now)

            class FakeExecutor:
                def launch(self, request):
                    return ResumeLaunchResult(True, 1, None)

            outcomes = runtime.run_poll(now, FakeExecutor())
            runtime.close()

            self.assertEqual(outcomes[0].status, "completed")
            output = (root / "logs" / "aiphetamine.log").read_text(encoding="utf-8")
            self.assertIn("poll_started", output)
            self.assertIn("poll_completed", output)
            self.assertNotIn(session_id, output)
            self.assertNotIn(str(root), output)


if __name__ == "__main__":
    unittest.main()
