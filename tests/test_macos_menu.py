import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

try:
    import AppKit
except ImportError:
    AppKit = None

from aiphetamine.domain import CandidateSession
from aiphetamine.macos_menu import AppKitMenuBarAdapter
from aiphetamine.menu_controller import MenuController
from aiphetamine.selection import InMemorySelectionStore


UTC = timezone.utc


@unittest.skipIf(AppKit is None, "AppKit is unavailable")
class AppKitMenuTests(unittest.TestCase):
    def test_status_item_is_identifiable_and_toggle_updates_native_check_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "visible-project"
            project.mkdir()
            candidate = CandidateSession(
                1,
                "candidate",
                "private-session-id",
                project,
                datetime(2026, 7, 22, 12, tzinfo=UTC),
                "Visible title",
                "visible-project",
                account_name="main",
            )

            class FakeRuntime:
                def __init__(self):
                    self.selection_store = InMemorySelectionStore()

                def candidates(self, now):
                    return (candidate,)

                def activate(self, session_id, now):
                    self.selection_store.activate(candidate, now)

                def deactivate(self, session_id):
                    self.selection_store.deactivate(session_id)

            AppKit.NSApplication.sharedApplication()
            adapter = AppKitMenuBarAdapter(
                MenuController(FakeRuntime(), clock=lambda: datetime(2026, 7, 22, 12, tzinfo=UTC))
            )
            adapter.start()
            try:
                self.assertEqual(adapter._status_item.button().title(), "AI")
                menu = adapter._status_item.menu()
                self.assertTrue(menu.itemAtIndex_(0).title().startswith("AIphetamine"))
                status_item = menu.itemAtIndex_(1)
                self.assertIn("最終poll: 未実行", status_item.title())
                candidate_item = menu.itemAtIndex_(3)
                self.assertIn("visible-project", candidate_item.title())

                adapter._target.toggle_(candidate_item)

                self.assertEqual(candidate_item.state(), AppKit.NSControlStateValueOn)
            finally:
                AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(adapter._status_item)
