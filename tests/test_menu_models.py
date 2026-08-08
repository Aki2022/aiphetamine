import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.domain import CandidateSession, session_key
from aiphetamine.app_runtime import PollStatus
from aiphetamine.menu_controller import MenuController
from aiphetamine.menu_models import build_session_rows
from aiphetamine.macos_menu import _poll_status_title
from aiphetamine.resume_service import PollOutcome
from aiphetamine.selection import InMemorySelectionStore


UTC = timezone.utc


class MenuModelTests(unittest.TestCase):
    def test_poll_status_title_is_sanitized_and_human_readable(self):
        status = PollStatus.from_outcomes(
            datetime(2026, 7, 21, 21, 10, tzinfo=UTC),
            (
                PollOutcome("private-session-id", "completed"),
                PollOutcome("another-private-id", "restored"),
            ),
        )

        title = _poll_status_title(status)

        expected_time = status.boundary.astimezone().strftime("%H:%M")
        self.assertEqual(title, f"最終poll: {expected_time}（成功1／復元1）")
        self.assertNotIn("private-session-id", title)

    def test_rows_normalize_bound_and_label_candidate_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = CandidateSession(
                1,
                "candidate",
                "session-private",
                root,
                datetime(2026, 7, 21, 12, tzinfo=UTC),
                "  実装\u0000   作業  " + "長" * 50,
                " project\nname ",
            )

            row = build_session_rows([candidate], InMemorySelectionStore())[0]

            self.assertFalse(row.checked)
            self.assertEqual(row.status, "")
            self.assertIn("実装 作業", row.title)
            self.assertIn("project name", row.title)
            self.assertIn("…", row.title)
            self.assertNotIn("\u0000", row.title)

    def test_duplicate_visible_labels_include_short_session_discriminator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            candidates = [
                CandidateSession(1, "candidate", "alpha-12345678", root, now, "same", "project"),
                CandidateSession(1, "candidate", "bravo-12345678", root, now, "same", "project"),
            ]

            rows = build_session_rows(candidates, InMemorySelectionStore())

            self.assertIn("alpha-12", rows[0].title)
            self.assertIn("bravo-12", rows[1].title)

    def test_rows_use_project_directory_and_session_discriminator_when_hook_names_are_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "example-project"
            project.mkdir()
            candidate = CandidateSession(
                1,
                "candidate",
                "session-12345678",
                project,
                datetime(2026, 7, 21, 12, tzinfo=UTC),
            )

            row = build_session_rows([candidate], InMemorySelectionStore())[0]

            self.assertIn("example-project", row.title)
            self.assertIn(session_key(candidate.session_id)[:8], row.title)
            self.assertNotIn("名称なし", row.title)
            self.assertNotIn("プロジェクト不明", row.title)

    def test_controller_toggles_only_in_memory_selection_and_refreshes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = CandidateSession(
                1,
                "candidate",
                "session-toggle",
                root,
                datetime(2026, 7, 21, 12, tzinfo=UTC),
                "build",
                "project",
                account_name="main",
            )

            class FakeRuntime:
                def __init__(self):
                    self.selection_store = InMemorySelectionStore()
                    self.calls = []

                def candidates(self, now):
                    return (candidate,)

                def activate(self, session_id, now):
                    self.calls.append(("activate", session_id))
                    self.selection_store.activate(candidate, now)

                def deactivate(self, session_id):
                    self.calls.append(("deactivate", session_id))
                    self.selection_store.deactivate(session_id)

            runtime = FakeRuntime()
            controller = MenuController(runtime, clock=lambda: candidate.updated_at)

            initial = controller.refresh()
            enabled = controller.toggle("session-toggle")
            disabled = controller.toggle("session-toggle")

            self.assertFalse(initial.session_rows[0].checked)
            self.assertTrue(enabled.session_rows[0].checked)
            self.assertFalse(disabled.session_rows[0].checked)
            self.assertEqual(runtime.calls, [("activate", "session-toggle"), ("deactivate", "session-toggle")])

    def test_selectable_rows_exclude_candidates_without_human_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 22, 12, tzinfo=UTC)
            known = CandidateSession(1, "candidate", "known", root, now, "title", "repo", account_name="main")
            unknown = CandidateSession(1, "candidate", "unknown", root, now)

            rows = build_session_rows([known, unknown], InMemorySelectionStore(), selectable_only=True)

            self.assertEqual(len(rows), 1)
            self.assertIn("title", rows[0].title)


if __name__ == "__main__":
    unittest.main()
