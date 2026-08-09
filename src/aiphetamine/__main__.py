"""macOS menu-bar entry point for AIphetamine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Thread, Timer

from .app_runtime import ApplicationRuntime
from .boundary_scheduler import OneShotBoundaryScheduler
from .executor import AccountRoutedResumeExecutor, DisabledResumeExecutor
from .macos_menu import AppKitMenuBarAdapter
from .menu_controller import MenuController
from .resume_configuration import load_claude_executable
from .session_metadata import SessionMetadataResolver


def main() -> int:
    try:
        import AppKit
    except ImportError:
        return 2
    AppKit.NSApplication.sharedApplication()
    data_root = Path.home() / ".local" / "share" / "aiphetamine"
    main_config_root = Path.home() / ".claude"
    alias_config_root = _claude2_config_root()
    account_roots = (("main", main_config_root), ("alias", alias_config_root))
    runtime = ApplicationRuntime(data_root, session_metadata=SessionMetadataResolver(account_roots))
    runtime.startup(datetime.now().astimezone())
    claude_path = load_claude_executable(data_root / "config.json")
    if claude_path is None:
        resume_executor = DisabledResumeExecutor()
    else:
        account_configs = {"main": (claude_path, main_config_root)}
        if alias_config_root.is_dir() and not alias_config_root.is_symlink():
            account_configs["alias"] = (claude_path, alias_config_root)
        resume_executor = AccountRoutedResumeExecutor(
            account_configs
        )
    adapter = AppKitMenuBarAdapter(MenuController(runtime, clock=lambda: datetime.now().astimezone()))
    adapter.start()
    scheduler = OneShotBoundaryScheduler(
        clock=lambda: datetime.now().astimezone(),
        timer_factory=_ThreadingTimerFactory(),
        worker_submit=lambda work: Thread(target=work, daemon=True).start(),
        poll=lambda now: runtime.run_poll(now, resume_executor),
    )
    scheduler.start()
    AppKit.NSApp.run()
    scheduler.stop()
    runtime.close()
    return 0


class _ThreadingTimerFactory:
    def schedule(self, delay_seconds: float, callback):
        timer = Timer(delay_seconds, callback)
        timer.daemon = True
        timer.start()
        return timer


def _claude2_config_root(home: Path | None = None) -> Path:
    """Return the explicit second-account config root without running a shell."""
    return (home or Path.home()) / ".claude-seat2"


if __name__ == "__main__":
    raise SystemExit(main())
