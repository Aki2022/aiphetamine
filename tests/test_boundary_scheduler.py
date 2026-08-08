import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.boundary_scheduler import OneShotBoundaryScheduler


JST = ZoneInfo("Asia/Tokyo")


class FakeTimer:
    def __init__(self, callback):
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.callback()


class FakeTimerFactory:
    def __init__(self):
        self.calls = []

    def schedule(self, delay_seconds, callback):
        timer = FakeTimer(callback)
        self.calls.append((delay_seconds, timer))
        return timer


class BoundarySchedulerTests(unittest.TestCase):
    def test_start_waits_for_next_boundary_then_runs_off_ui_thread_and_reschedules(self):
        times = iter(
            [
                datetime(2026, 7, 21, 21, 10, tzinfo=JST),
                datetime(2026, 7, 21, 22, 0, tzinfo=JST),
                datetime(2026, 7, 21, 22, 0, tzinfo=JST),
            ]
        )
        timer_factory = FakeTimerFactory()
        poll_calls = []
        worker_calls = []

        def submit(work):
            worker_calls.append(work)
            work()

        scheduler = OneShotBoundaryScheduler(
            clock=lambda: next(times),
            timer_factory=timer_factory,
            worker_submit=submit,
            poll=lambda now: poll_calls.append(now),
        )

        scheduler.start()

        self.assertEqual(poll_calls, [])
        self.assertEqual(timer_factory.calls[0][0], 50 * 60)
        timer_factory.calls[0][1].fire()

        self.assertEqual(len(worker_calls), 1)
        self.assertEqual(poll_calls, [datetime(2026, 7, 21, 22, 0, tzinfo=JST)])
        self.assertEqual(timer_factory.calls[1][0], 2 * 60 * 60)

    def test_wake_cancels_previous_timer_and_does_not_replay_a_missed_cycle(self):
        times = iter(
            [
                datetime(2026, 7, 21, 21, 10, tzinfo=JST),
                datetime(2026, 7, 21, 23, 45, tzinfo=JST),
            ]
        )
        timer_factory = FakeTimerFactory()
        poll_calls = []
        scheduler = OneShotBoundaryScheduler(
            clock=lambda: next(times),
            timer_factory=timer_factory,
            worker_submit=lambda work: work(),
            poll=lambda now: poll_calls.append(now),
        )

        scheduler.start()
        original = timer_factory.calls[0][1]
        scheduler.on_wake()

        self.assertTrue(original.cancelled)
        self.assertEqual(poll_calls, [])
        self.assertEqual(timer_factory.calls[1][0], 15 * 60)

    def test_overlapping_timer_callback_is_skipped_while_worker_is_pending(self):
        now = datetime(2026, 7, 21, 21, 10, tzinfo=JST)
        timer_factory = FakeTimerFactory()
        queued = []
        scheduler = OneShotBoundaryScheduler(
            clock=lambda: now,
            timer_factory=timer_factory,
            worker_submit=queued.append,
            poll=lambda _: None,
        )

        scheduler.start()
        timer_factory.calls[0][1].fire()
        timer_factory.calls[0][1].fire()

        self.assertEqual(len(queued), 1)


if __name__ == "__main__":
    unittest.main()
