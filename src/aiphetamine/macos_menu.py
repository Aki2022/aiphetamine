"""Optional AppKit adapter; all menu policy remains in ``menu_controller``."""

from __future__ import annotations

from .menu_controller import MenuController


_POLL_STATUS_LABELS = {
    "completed": "成功",
    "restored": "復元",
    "unselected": "未選択",
    "expired": "期限切れ",
    "candidate_missing": "候補なし",
    "account_mismatch": "アカウント不一致",
    "path_mismatch": "パス不一致",
    "event_stale": "イベント期限切れ",
    "candidate_stale": "候補期限切れ",
    "claim_failed": "取得失敗",
    "processing": "処理中",
    "poll_failed": "poll失敗",
}


def _poll_status_title(status) -> str:
    if status is None:
        return "最終poll: 未実行"
    boundary = status.boundary.astimezone().strftime("%H:%M")
    counts = tuple(
        f"{_POLL_STATUS_LABELS.get(name, 'その他')}{count}"
        for name, count in status.status_counts
        if count > 0
    )
    return f"最終poll: {boundary}（{'／'.join(counts) or '対象なし'}）"


class AppKitMenuBarAdapter:
    """Render a ``MenuController`` only when PyObjC is available at runtime."""

    def __init__(self, controller: MenuController) -> None:
        self._controller = controller
        self._status_item = None
        self._appkit = None

    def start(self) -> None:
        try:
            import AppKit
            import Foundation
        except ImportError as error:
            raise RuntimeError("appkit_unavailable") from error
        self._appkit = AppKit
        adapter = self

        class MenuTarget(Foundation.NSObject):
            def toggle_(self, sender):
                state = adapter._controller.toggle(str(sender.representedObject()))
                selected = next(
                    (
                        row.checked
                        for row in state.session_rows
                        if row.session_id == str(sender.representedObject())
                    ),
                    False,
                )
                sender.setState_(
                    AppKit.NSControlStateValueOn
                    if selected
                    else AppKit.NSControlStateValueOff
                )

            def quit_(self, _sender):
                AppKit.NSApp.terminate_(None)

            def menuWillOpen_(self, _menu):
                adapter.refresh()

        self._target = MenuTarget.alloc().init()
        self._status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        button = self._status_item.button()
        button.setTitle_("AI")
        button.setToolTip_("AIphetamine")
        button.setAccessibilityLabel_("AIphetamine")
        self.refresh()

    def refresh(self) -> None:
        if self._status_item is None or self._appkit is None:
            raise RuntimeError("menu_not_started")
        menu = self._appkit.NSMenu.alloc().init()
        state = self._controller.refresh()
        heading = self._appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "AIphetamine — 自動resume対象を選択", None, ""
        )
        heading.setEnabled_(False)
        menu.addItem_(heading)
        poll_status = self._appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            _poll_status_title(state.poll_status), None, ""
        )
        poll_status.setEnabled_(False)
        menu.addItem_(poll_status)
        if state.unidentified_count:
            unavailable = self._appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"未識別候補: {state.unidentified_count}件（選択不可）", None, ""
            )
            unavailable.setEnabled_(False)
            menu.addItem_(unavailable)
        menu.addItem_(self._appkit.NSMenuItem.separatorItem())
        for row in state.session_rows:
            item = self._appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                row.title, "toggle:", ""
            )
            item.setTarget_(self._target)
            item.setRepresentedObject_(row.session_id)
            item.setState_(
                self._appkit.NSControlStateValueOn
                if row.checked
                else self._appkit.NSControlStateValueOff
            )
            menu.addItem_(item)
        menu.addItem_(self._appkit.NSMenuItem.separatorItem())
        login_item = self._appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Launch at Login (設定生成のみ)", None, ""
        )
        login_item.setEnabled_(False)
        menu.addItem_(login_item)
        menu.addItem_(self._appkit.NSMenuItem.separatorItem())
        quit_item = self._appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit AIphetamine", "quit:", "")
        quit_item.setTarget_(self._target)
        menu.addItem_(quit_item)
        menu.setDelegate_(self._target)
        self._status_item.setMenu_(menu)
