"""macOS menu-bar entry point for AIphetamine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import subprocess
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
    account_roots = (("main", Path.home() / ".claude"), ("alias", _claude2_config_root()))
    runtime = ApplicationRuntime(data_root, session_metadata=SessionMetadataResolver(account_roots))
    runtime.startup(datetime.now().astimezone())
    claude_path = load_claude_executable(data_root / "config.json")
    if claude_path is None:
        resume_executor = DisabledResumeExecutor()
    else:
        resume_executor = AccountRoutedResumeExecutor(
            {
                "main": (claude_path, Path.home() / ".claude"),
                "alias": (claude_path, _claude2_config_root()),
            }
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


def _claude2_config_root() -> Path:
    """Read the configured second-account root without retaining shell output."""
    try:
        result = subprocess.run(
            ["zsh", "-xic", "claude2 --version >/dev/null"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            check=False,
        )
        match = re.search(r"CLAUDE_CONFIG_DIR=([^\\s]+)", result.stderr)
        path = Path(match.group(1).strip("'\"")) if match else Path()
        if result.returncode == 0 and path.is_absolute() and path.is_dir() and not path.is_symlink():
            return path
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path.home() / ".claude-seat2"


if __name__ == "__main__":
    raise SystemExit(main())
