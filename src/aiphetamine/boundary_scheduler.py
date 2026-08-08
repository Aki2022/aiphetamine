"""UI-loop-neutral scheduling for fixed two-hour poll boundaries."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Protocol

from .scheduling import next_boundary


class CancellableTimer(Protocol):
    def cancel(self) -> None: ...


class TimerFactory(Protocol):
    def schedule(self, delay_seconds: float, callback: Callable[[], None]) -> CancellableTimer: ...


class OneShotBoundaryScheduler:
    """Schedule a single future boundary and run work outside the UI loop."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime],
        timer_factory: TimerFactory,
        worker_submit: Callable[[Callable[[], None]], None],
        poll: Callable[[datetime], None],
    ) -> None:
        self._clock = clock
        self._timer_factory = timer_factory
        self._worker_submit = worker_submit
        self._poll = poll
        self._timer: CancellableTimer | None = None
        self._running = False

    def start(self) -> None:
        self._schedule_next()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def on_wake(self) -> None:
        self.stop()
        self._schedule_next()

    def _schedule_next(self) -> None:
        now = self._clock()
        target = next_boundary(now)
        delay = max(0.0, (target - now.astimezone(target.tzinfo)).total_seconds())
        self._timer = self._timer_factory.schedule(delay, self._on_timer)

    def _on_timer(self) -> None:
        self._timer = None
        if self._running:
            return
        self._running = True

        def run_once() -> None:
            try:
                self._poll(self._clock())
            finally:
                self._running = False
                self._schedule_next()

        self._worker_submit(run_once)
