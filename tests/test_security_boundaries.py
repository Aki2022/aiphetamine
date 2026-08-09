import json
import shlex
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from aiphetamine.app_runtime import ApplicationRuntime
from aiphetamine.domain import CandidateSession, RateLimitEvent, session_key
from aiphetamine.filesystem_security import (
    is_secure_account_directory,
    open_private_directory,
    read_private_text,
    validate_external_executable,
)
from aiphetamine.instance_lock import InstanceLock
from aiphetamine.launch_agent import LaunchAgentManager, LaunchAgentSpec
from aiphetamine.repositories import CandidateRepository, RateLimitEventRepository
from aiphetamine.resume import evaluate_resume
from aiphetamine.selection import InMemorySelectionStore
from aiphetamine.session_metadata import SessionMetadataResolver
from hooks.aiphetamine_hook import apply_event
from scripts.run_candidate_lifecycle_spike import build_lifecycle_command
from scripts.run_resume_spike import build_resume_command


UTC = timezone.utc


class SecurityBoundaryTests(unittest.TestCase):
    def test_session_metadata_rejects_path_traversal_and_symlinked_jsonl(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            projects = root / "projects"
            projects.mkdir()
            outside = root / "outside.jsonl"
            outside.write_text(json.dumps({"customTitle": "must not be read"}) + "\n")
            (projects / "safe-session.jsonl").symlink_to(outside)
            resolver = SessionMetadataResolver((("main", root),))

            self.assertEqual(resolver._session_label("../outside"), (None, None))
            self.assertEqual(resolver._session_label("safe-session"), (None, None))

    def test_hook_fails_closed_when_managed_directory_is_a_symlink(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            outside = root / "outside"
            outside.mkdir()
            data_root = root / "data"
            data_root.symlink_to(outside, target_is_directory=True)
            payload = {"session_id": "safe-session", "cwd": str(root)}

            self.assertEqual(
                apply_event(payload, "SessionStart", data_root, datetime.now(UTC)),
                "filesystem_error",
            )
            self.assertEqual(list(outside.iterdir()), [])

    def test_hook_fails_closed_when_managed_parent_is_a_symlink(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            outside = root / "outside"
            outside.mkdir()
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(outside, target_is_directory=True)
            data_root = linked_parent / "data"
            payload = {"session_id": "safe-session", "cwd": str(root)}

            self.assertEqual(
                apply_event(payload, "SessionStart", data_root, datetime.now(UTC)),
                "filesystem_error",
            )
            self.assertEqual(list(outside.iterdir()), [])

    def test_hook_atomic_write_does_not_follow_existing_file_symlink(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            candidates.mkdir(mode=0o700)
            (candidates / "unknown").mkdir(mode=0o700)
            rate_limits = root / "rate_limits"
            rate_limits.mkdir(mode=0o700)
            outside = root / "outside.json"
            outside.write_text("keep")
            key = session_key("safe-session")
            (candidates / "unknown" / f"{key}.json").symlink_to(outside)
            payload = {"session_id": "safe-session", "cwd": str(root)}

            self.assertEqual(
                apply_event(payload, "SessionStart", root, datetime.now(UTC)),
                "filesystem_error",
            )
            self.assertEqual(outside.read_text(), "keep")

    def test_launch_agent_generation_rejects_symlink_target(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            outside = root / "outside.plist"
            outside.write_text("keep")
            launch_root = root / "launch-agents"
            launch_root.mkdir()
            target = launch_root / "local.aiphetamine.menubar.plist"
            target.symlink_to(outside)

            with self.assertRaises(OSError):
                LaunchAgentManager(launch_root).write_plist(
                    LaunchAgentSpec("/opt/python/bin/python3", "aiphetamine")
                )
            self.assertEqual(outside.read_text(), "keep")

    def test_runtime_fails_closed_when_log_directory_is_a_symlink(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            outside = root / "outside"
            outside.mkdir()
            data_root = root / "data"
            data_root.mkdir()
            (data_root / "candidates").mkdir()
            (data_root / "rate_limits").mkdir()
            (data_root / "logs").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(OSError):
                ApplicationRuntime(data_root)
            self.assertEqual(list(outside.iterdir()), [])

    def test_account_and_executable_boundaries_reject_writable_ancestors(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            unsafe_parent = root / "unsafe"
            unsafe_parent.mkdir()
            unsafe_parent.chmod(0o777)
            account = unsafe_parent / "account"
            account.mkdir()
            account.chmod(0o700)
            executable = unsafe_parent / "claude"
            executable.write_text("#!/bin/sh\n")
            executable.chmod(0o700)

            self.assertFalse(is_secure_account_directory(account))
            self.assertFalse(validate_external_executable(executable))

    def test_private_directory_rejects_filesystem_root(self):
        with self.assertRaises(OSError):
            open_private_directory(Path("/"))

        self.assertFalse(is_secure_account_directory(Path("/")))

    def test_private_directory_rejects_group_readable_account_directory(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            account = Path(temp_dir) / "account"
            account.mkdir(mode=0o755)
            account.chmod(0o755)

            with self.assertRaises(OSError):
                open_private_directory(account)
            self.assertFalse(is_secure_account_directory(account))

    def test_private_text_rejects_group_readable_file(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            private_file = root / "private.json"
            private_file.write_text("{}", encoding="utf-8")
            private_file.chmod(0o644)

            self.assertEqual(read_private_text(private_file), "{}")
            self.assertEqual(private_file.stat().st_mode & 0o777, 0o600)

    def test_repository_rejects_owner_readable_but_not_private_root(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir) / "candidates"
            root.mkdir(mode=0o755)
            root.chmod(0o755)
            candidate_id = "loose-directory"
            record = root / f"{session_key(candidate_id)}.json"
            record.write_text(
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
            record.chmod(0o600)

            self.assertEqual(
                CandidateRepository(root).list_candidates(
                    now=datetime(2026, 7, 21, 12, tzinfo=UTC)
                ),
                [],
            )

    def test_executable_boundary_rejects_group_writable_file(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            executable = root / "claude"
            executable.write_text("#!/bin/sh\n")
            executable.chmod(0o770)

            self.assertFalse(validate_external_executable(executable))

    def test_shell_paths_are_single_quoted_arguments(self):
        lifecycle_root = Path("/private/tmp/lifecycle; touch /tmp/not-created")
        lifecycle_script = Path("/private/tmp/capture script.py")
        lifecycle_command = build_lifecycle_command(
            "claude", lifecycle_script, lifecycle_root, "salt;touch /tmp/not-created"
        )
        command_text = json.loads(lifecycle_command[3])["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertEqual(
            shlex.split(command_text),
            [
                "env",
                "AIPHEMETINE_CAPTURE_SALT=salt;touch /tmp/not-created",
                "AIPHEMETINE_LIFECYCLE_ROOT=/private/tmp/lifecycle; touch /tmp/not-created",
                "python3",
                "/private/tmp/capture script.py",
            ],
        )

        resume_command = build_resume_command(
            "claude",
            "safe-session",
            Path("/private/tmp/capture;script.py"),
            "salt;touch /tmp/not-created",
        )
        resume_text = json.loads(resume_command[5])["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertEqual(
            shlex.split(resume_text),
            [
                "env",
                "AIPHEMETINE_CAPTURE_SALT=salt;touch /tmp/not-created",
                "python3",
                "/private/tmp/capture;script.py",
            ],
        )

    def test_repositories_skip_records_with_unknown_account_names(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            rate_limits = root / "rate_limits"
            candidates.mkdir(mode=0o700)
            rate_limits.mkdir(mode=0o700)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "safe-session"
            common = {
                "schema_version": 1,
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
                "account_name": "attacker",
            }
            (candidates / f"{session_key(session_id)}.json").write_text(
                json.dumps({**common, "record_type": "candidate"})
            )
            (rate_limits / f"{session_key(session_id)}.json").write_text(
                json.dumps({**common, "record_type": "rate_limit", "reason": "rate_limit"})
            )

            self.assertEqual(CandidateRepository(candidates).list_candidates(now=now), [])
            self.assertEqual(RateLimitEventRepository(rate_limits).list_events(now=now), [])

    def test_repositories_fail_closed_for_non_string_account_names(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates" / "main"
            rate_limits = root / "rate_limits" / "main"
            candidates.mkdir(mode=0o700, parents=True)
            rate_limits.mkdir(mode=0o700, parents=True)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "malformed-account"
            common = {
                "schema_version": 1,
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
                "account_name": ["main"],
            }
            (candidates / f"{session_key(session_id)}.json").write_text(
                json.dumps({**common, "record_type": "candidate"})
            )
            (rate_limits / f"{session_key(session_id)}.json").write_text(
                json.dumps({**common, "record_type": "rate_limit", "reason": "rate_limit"})
            )

            self.assertEqual(CandidateRepository(root / "candidates").list_candidates(now=now), [])
            self.assertEqual(RateLimitEventRepository(root / "rate_limits").list_events(now=now), [])

    def test_duplicate_account_scopes_are_not_selected_as_a_winner(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            candidates_root = root / "candidates"
            rate_limits_root = root / "rate_limits"
            for account in ("main", "alias"):
                (candidates_root / account).mkdir(mode=0o700, parents=True)
                (rate_limits_root / account).mkdir(mode=0o700, parents=True)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "duplicate-account-session"
            for account in ("main", "alias"):
                payload = {
                    "schema_version": 1,
                    "record_type": "candidate",
                    "session_id": session_id,
                    "project_path": str(root),
                    "updated_at": "2026-07-21T11:59:00+00:00",
                    "account_name": account,
                }
                (candidates_root / account / f"{session_key(session_id)}.json").write_text(
                    json.dumps(payload)
                )

            self.assertEqual(CandidateRepository(candidates_root).list_candidates(now=now), [])

    def test_unlabeled_event_cannot_inherit_candidate_account(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            from aiphetamine.domain import CandidateSession, RateLimitEvent

            candidate = CandidateSession(1, "candidate", "unlabeled", root, now, account_name="main")
            event = RateLimitEvent(1, "rate_limit", "rate_limit", "unlabeled", root, now)
            store = InMemorySelectionStore()
            store.activate(candidate, now)

            decision = evaluate_resume(event, {candidate.session_id: candidate}, store, now)

            self.assertEqual(decision.status, "account_unknown")

    def test_selection_is_scoped_to_account(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "account-scoped-selection"
            main = CandidateSession(1, "candidate", session_id, root, now, account_name="main")
            alias = CandidateSession(1, "candidate", session_id, root, now, account_name="alias")
            event = RateLimitEvent(1, "rate_limit", "rate_limit", session_id, root, now, account_name="alias")
            store = InMemorySelectionStore()
            store.activate(main, now)

            self.assertEqual(evaluate_resume(event, {session_id: alias}, store, now).status, "unselected")

            store.activate(alias, now)
            self.assertFalse(store.is_selected(session_id, "main"))
            self.assertTrue(store.is_selected(session_id, "alias"))

    def test_instance_lock_allows_only_one_runtime(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            first = InstanceLock(root)
            try:
                with self.assertRaisesRegex(RuntimeError, "instance_already_running"):
                    InstanceLock(root)
            finally:
                first.close()

    def test_private_text_rejects_fifo_without_blocking(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            path = Path(temp_dir) / "not-a-file"
            import os

            os.mkfifo(path, 0o600)
            with self.assertRaises(OSError):
                read_private_text(path)

    def test_duplicate_candidate_does_not_reconstruct_from_rate_limit_event(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            events = root / "rate_limits"
            for account in ("main", "alias"):
                (candidates / account).mkdir(mode=0o700, parents=True)
                (events / account).mkdir(mode=0o700, parents=True)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "duplicate-reconstruct"
            for account in ("main", "alias"):
                candidate = {
                    "schema_version": 1,
                    "record_type": "candidate",
                    "session_id": session_id,
                    "project_path": str(root),
                    "updated_at": "2026-07-21T11:59:00+00:00",
                    "account_name": account,
                }
                (candidates / account / f"{session_key(session_id)}.json").write_text(
                    json.dumps(candidate)
                )
            event = {
                "schema_version": 1,
                "record_type": "rate_limit",
                "reason": "rate_limit",
                "session_id": session_id,
                "project_path": str(root),
                "updated_at": "2026-07-21T11:59:00+00:00",
                "account_name": "main",
            }
            (events / "main" / f"{session_key(session_id)}.json").write_text(json.dumps(event))

            self.assertEqual(ApplicationRuntime(root).candidates(now), ())

    def test_duplicate_rate_limit_event_does_not_reconstruct_candidate(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            root = Path(temp_dir)
            events = root / "rate_limits"
            for account in ("main", "alias"):
                (events / account).mkdir(mode=0o700, parents=True)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            session_id = "duplicate-event-reconstruct"
            for account in ("main", "alias"):
                event = {
                    "schema_version": 1,
                    "record_type": "rate_limit",
                    "reason": "rate_limit",
                    "session_id": session_id,
                    "project_path": str(root),
                    "updated_at": "2026-07-21T11:59:00+00:00",
                    "account_name": account,
                }
                (events / account / f"{session_key(session_id)}.json").write_text(
                    json.dumps(event)
                )

            self.assertEqual(ApplicationRuntime(root).candidates(now), ())


if __name__ == "__main__":
    unittest.main()
