import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.domain import session_key
from aiphetamine.domain import CandidateSession
from aiphetamine.domain import ResumeRequest, ResumeLaunchResult
from aiphetamine.executor import (
    AccountRoutedResumeExecutor,
    ClaudeResumeExecutor,
    DisabledResumeExecutor,
    build_resume_spec,
)
from aiphetamine.resume_service import RuntimePollCycle
from aiphetamine.repositories import RateLimitEventRepository
from aiphetamine.selection import InMemorySelectionStore


UTC = timezone.utc


class RuntimeCoreTests(unittest.TestCase):
    def test_resume_spec_uses_fixed_message_cwd_and_detached_devnull_contract(self):
        request = ResumeRequest("session-command", Path("/tmp/project"))

        spec = build_resume_spec("/usr/local/bin/claude", request)

        self.assertEqual(
            spec.args,
            ("/usr/local/bin/claude", "-p", "--resume", "session-command", "Continue"),
        )
        self.assertEqual(spec.cwd, Path("/tmp/project"))
        self.assertFalse(spec.shell)
        self.assertTrue(spec.start_new_session)
        self.assertTrue(spec.devnull_streams)

    def test_resume_executor_uses_injected_process_factory_without_capturing_output(self):
        calls = []

        class FakeProcess:
            pid = 31415

            @staticmethod
            def wait():
                return 0

        def factory(spec):
            calls.append(spec)
            return FakeProcess()

        executor = ClaudeResumeExecutor("/usr/local/bin/claude", process_factory=factory)
        result = executor.launch(ResumeRequest("session-command", Path("/tmp/project")))

        self.assertEqual(result, ResumeLaunchResult(True, 31415, None))
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].devnull_streams)

    def test_real_process_boundary_uses_verified_cwd_and_config(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            executable = root / "claude"
            executable.write_text(
                "#!/bin/sh\n"
                "pwd > child-cwd\n"
                "test -d \"$CLAUDE_CONFIG_DIR\" && touch \"$CLAUDE_CONFIG_DIR/config-seen\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            executable.chmod(0o700)
            config = root / "config"
            config.mkdir(mode=0o700)
            spec = build_resume_spec(
                executable,
                ResumeRequest("session-command", root),
                config_dir=config,
            )
            process = ClaudeResumeExecutor._launch_process(spec)

            self.assertEqual(process.wait(), 0)
            self.assertEqual((root / "child-cwd").read_text().strip(), str(root))
            self.assertTrue((config / "config-seen").exists())

    def test_account_routed_executor_sets_the_selected_config_directory(self):
        calls = []

        class FakeProcess:
            pid = 31416

            @staticmethod
            def wait():
                return 0

        def factory(spec):
            calls.append(spec)
            return FakeProcess()

        executor = AccountRoutedResumeExecutor(
            {"main": ("/usr/local/bin/claude", "/tmp/main-config"), "alias": ("/usr/local/bin/claude", "/tmp/seat2-config")},
            process_factory=factory,
        )

        result = executor.launch(
            ResumeRequest("session-command", Path("/tmp/project"), account_name="alias")
        )

        self.assertEqual(result, ResumeLaunchResult(True, 31416, None))
        self.assertEqual(calls[0].environment["CLAUDE_CONFIG_DIR"], "/tmp/seat2-config")

    def test_account_routed_executor_refuses_unidentified_account(self):
        executor = AccountRoutedResumeExecutor({"main": ("/usr/local/bin/claude", "/tmp/main-config")})

        result = executor.launch(ResumeRequest("session-command", Path("/tmp/project")))

        self.assertEqual(result, ResumeLaunchResult(False, None, "account_unknown"))

    def test_resume_executor_restores_failure_when_claude_exits_nonzero(self):
        class FailedProcess:
            pid = 31415

            @staticmethod
            def wait():
                return 1

        executor = ClaudeResumeExecutor(
            "/usr/local/bin/claude", process_factory=lambda _spec: FailedProcess()
        )

        result = executor.launch(ResumeRequest("session-command", Path("/tmp/project")))

        self.assertEqual(result, ResumeLaunchResult(False, None, "nonzero_exit"))

    def test_resume_executor_classifies_local_launch_error_without_returning_raw_text(self):
        def factory(spec):
            raise OSError("private local detail")

        executor = ClaudeResumeExecutor("/usr/local/bin/claude", process_factory=factory)

        result = executor.launch(ResumeRequest("session-command", Path("/tmp/project")))

        self.assertEqual(result, ResumeLaunchResult(False, None, "os_error"))

    def test_disabled_executor_never_invokes_a_process_factory(self):
        calls = []

        result = DisabledResumeExecutor().launch(ResumeRequest("session-command", Path("/tmp/project")))

        self.assertEqual(result, ResumeLaunchResult(False, None, "launch_disabled"))
        self.assertEqual(calls, [])

    def test_event_repository_claim_complete_restore_and_preserve_recreated_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            event_id = "session-runtime"
            event_path = root / f"{session_key(event_id)}.json"
            payload = {
                "schema_version": 1,
                "record_type": "rate_limit",
                "reason": "rate_limit",
                "session_id": event_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
            }
            event_path.write_text(json.dumps(payload), encoding="utf-8")
            repository = RateLimitEventRepository(root)
            event = repository.list_events(now=now)[0]

            processing_path = repository.claim(event)

            self.assertEqual(processing_path, root / f"{session_key(event_id)}.processing")
            self.assertFalse(event_path.exists())
            self.assertTrue(processing_path.exists())
            self.assertIsNone(repository.claim(event))

            repository.complete(processing_path)
            self.assertFalse(processing_path.exists())

            event_path.write_text(json.dumps(payload), encoding="utf-8")
            event = repository.list_events(now=now)[0]
            processing_path = repository.claim(event)
            event_path.write_text(json.dumps({**payload, "updated_at": "2026-07-21T12:00:00+00:00"}), encoding="utf-8")

            restored_path = repository.restore(processing_path)

            self.assertEqual(restored_path, event_path)
            self.assertTrue(event_path.exists())
            self.assertFalse(processing_path.exists())
            self.assertIn("12:00:00", event_path.read_text(encoding="utf-8"))

    def test_startup_cleanup_only_removes_rate_limit_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_root = root / "candidates"
            candidate_root.mkdir()
            candidate = candidate_root / "candidate.json"
            candidate.write_text("keep", encoding="utf-8")
            (root / "one.json").write_text("event", encoding="utf-8")
            (root / "two.processing").write_text("event", encoding="utf-8")
            (root / "three.tmp.worker").write_text("event", encoding="utf-8")
            (root / "notes.txt").write_text("keep", encoding="utf-8")

            removed = RateLimitEventRepository(root).cleanup_on_startup()

            self.assertEqual(removed, 3)
            self.assertTrue(candidate.exists())
            self.assertTrue((root / "notes.txt").exists())
            self.assertEqual(list(root.iterdir()), [candidate_root, root / "notes.txt"])

    def test_poll_cycle_completes_successful_launch_and_restores_failed_launch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "candidates"
            events_dir = root / "rate_limits"
            candidates_dir.mkdir()
            events_dir.mkdir()
            (events_dir / "alias").mkdir()
            (candidates_dir / "main").mkdir()
            (events_dir / "main").mkdir()
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)

            def write_record(session_id, record_type, **extra):
                payload = {
                    "schema_version": 1,
                    "record_type": record_type,
                    "session_id": session_id,
                    "project_path": str(root),
                    "updated_at": "2026-07-21T11:59:00+00:00",
                    "account_name": "main",
                    **extra,
                }
                target = events_dir / "main" if record_type == "rate_limit" else candidates_dir / "main"
                (target / f"{session_key(session_id)}.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )

            write_record("session-success", "candidate")
            write_record("session-success", "rate_limit", reason="rate_limit")
            write_record("session-failure", "candidate")
            write_record("session-failure", "rate_limit", reason="rate_limit")
            candidates = [
                CandidateSession(1, "candidate", "session-success", root, now, account_name="main"),
                CandidateSession(1, "candidate", "session-failure", root, now, account_name="main"),
            ]

            class FakeExecutor:
                def launch(self, request):
                    return ResumeLaunchResult(request.session_id == "session-success", 1, None)

            from aiphetamine.selection import InMemorySelectionStore

            selection = InMemorySelectionStore()
            for candidate in candidates:
                selection.activate(candidate, now)
            service = RuntimePollCycle(
                candidates_dir,
                events_dir,
                selection,
                FakeExecutor(),
            )

            outcomes = service.run(now)

            self.assertEqual(
                {outcome.session_id: outcome.status for outcome in outcomes},
                {"session-success": "completed", "session-failure": "restored"},
            )
            self.assertFalse((events_dir / "main" / f"{session_key('session-success')}.json").exists())
            self.assertTrue((events_dir / "main" / f"{session_key('session-failure')}.json").exists())

    def test_poll_cycle_uses_enriched_candidate_provider_for_account_routing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "candidates"
            events_dir = root / "rate_limits"
            candidates_dir.mkdir()
            events_dir.mkdir()
            (events_dir / "alias").mkdir()
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "session-provider-alias"
            event = {
                "schema_version": 1,
                "record_type": "rate_limit",
                "reason": "rate_limit",
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
                "account_name": "alias",
            }
            (events_dir / "alias" / f"{session_key(session_id)}.json").write_text(
                json.dumps(event), encoding="utf-8"
            )
            candidate = CandidateSession(
                1, "candidate", session_id, root, now, account_name="alias"
            )
            selection = InMemorySelectionStore()
            selection.activate(candidate, now)
            requests = []

            class FakeExecutor:
                def launch(self, request):
                    requests.append(request)
                    return ResumeLaunchResult(True, 1, None)

            cycle = RuntimePollCycle(
                candidates_dir,
                events_dir,
                selection,
                FakeExecutor(),
                candidate_provider=lambda _now: (candidate,),
            )

            outcomes = cycle.run(now)

            self.assertEqual(outcomes[0].status, "completed")
            self.assertEqual(requests[0].account_name, "alias")

    def test_poll_cycle_restores_event_when_executor_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "candidates"
            events_dir = root / "rate_limits"
            candidates_dir.mkdir()
            events_dir.mkdir()
            (candidates_dir / "main").mkdir()
            (events_dir / "main").mkdir()
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "session-exception"
            payload = {
                "schema_version": 1,
                "record_type": "rate_limit",
                "reason": "rate_limit",
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
                "account_name": "main",
            }
            (events_dir / "main" / f"{session_key(session_id)}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            candidate = CandidateSession(1, "candidate", session_id, root, now, account_name="main")
            (candidates_dir / "main" / f"{session_key(session_id)}.json").write_text(
                json.dumps({**payload, "record_type": "candidate"}), encoding="utf-8"
            )

            class RaisingExecutor:
                def launch(self, request):
                    raise RuntimeError("private local detail")

            from aiphetamine.selection import InMemorySelectionStore

            selection = InMemorySelectionStore()
            selection.activate(candidate, now)
            outcomes = RuntimePollCycle(
                candidates_dir,
                events_dir,
                selection,
                RaisingExecutor(),
            ).run(now)

            self.assertEqual(outcomes[0].status, "restored")
            self.assertTrue((events_dir / "main" / f"{session_key(session_id)}.json").exists())

    def test_poll_cycle_preserves_recreated_event_when_launch_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "candidates"
            events_dir = root / "rate_limits"
            candidates_dir.mkdir()
            events_dir.mkdir()
            (candidates_dir / "main").mkdir()
            (events_dir / "main").mkdir()
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "session-recreated"
            payload = {
                "schema_version": 1,
                "record_type": "rate_limit",
                "reason": "rate_limit",
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
                "account_name": "main",
            }
            (events_dir / "main" / f"{session_key(session_id)}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            candidate = CandidateSession(1, "candidate", session_id, root, now, account_name="main")
            (candidates_dir / "main" / f"{session_key(session_id)}.json").write_text(
                json.dumps({**payload, "record_type": "candidate"}), encoding="utf-8"
            )

            class RecreatingExecutor:
                def launch(self, request):
                    (events_dir / "main" / f"{session_key(session_id)}.json").write_text(
                        json.dumps({**payload, "updated_at": "2026-07-21T12:00:00+00:00"}),
                        encoding="utf-8",
                    )
                    return ResumeLaunchResult(False, None, "os_error")

            from aiphetamine.selection import InMemorySelectionStore

            selection = InMemorySelectionStore()
            selection.activate(candidate, now)
            outcomes = RuntimePollCycle(
                candidates_dir,
                events_dir,
                selection,
                RecreatingExecutor(),
            ).run(now)

            self.assertEqual(outcomes[0].status, "restored")
            self.assertTrue((events_dir / "main" / f"{session_key(session_id)}.json").exists())
            self.assertIn(
                "12:00:00",
                (events_dir / "main" / f"{session_key(session_id)}.json").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
