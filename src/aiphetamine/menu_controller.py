"""Application-facing menu controller without AppKit imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol

from .menu_models import SessionMenuRow, build_session_rows


class MenuRuntime(Protocol):
    selection_store: object

    def candidates(self, now: datetime): ...

    def activate(self, session_id: str, now: datetime) -> None: ...

    def deactivate(self, session_id: str, account_name: str | None = None) -> None: ...


@dataclass(frozen=True)
class MenuState:
    session_rows: tuple[SessionMenuRow, ...]
    unidentified_count: int = 0
    poll_status: object | None = None


class MenuController:
    def __init__(self, runtime: MenuRuntime, *, clock: Callable[[], datetime]) -> None:
        self._runtime = runtime
        self._clock = clock
        self._state = MenuState(())

    @property
    def state(self) -> MenuState:
        return self._state

    def refresh(self) -> MenuState:
        now = self._clock()
        candidates = tuple(self._runtime.candidates(now))
        self._state = MenuState(
            build_session_rows(candidates, self._runtime.selection_store, selectable_only=True),
            unidentified_count=sum(
                1 for candidate in candidates if not (candidate.account_name and candidate.session_name)
            ),
            poll_status=getattr(self._runtime, "last_poll_status", None),
        )
        return self._state

    def toggle(self, session_id: str) -> MenuState:
        now = self._clock()
        candidate = next(
            (candidate for candidate in self._runtime.candidates(now) if candidate.session_id == session_id),
            None,
        )
        account_name = candidate.account_name if candidate is not None else None
        if self._runtime.selection_store.is_selected(session_id, account_name):
            self._runtime.deactivate(session_id, account_name)
        else:
            self._runtime.activate(session_id, now)
        return self.refresh()
