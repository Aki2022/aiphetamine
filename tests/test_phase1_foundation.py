import json
import os
import tempfile
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.domain import CandidateSession, RateLimitEvent, session_key
from aiphetamine.repositories import CandidateRepository, RateLimitEventRepository
from aiphetamine.resume import evaluate_resume
from aiphetamine.scheduling import next_boundary
from aiphetamine.selection import InMemorySelectionStore


UTC = timezone.utc


class Phase1FoundationTests(unittest.TestCase):
    def test_session_key_is_deterministic_without_retaining_session_id(self):
        self.assertEqual(
            session_key("session-alpha"),
            "99b1d23983d285eb64aa2e321f429dd6678a40ec15149dc258098ed6a5bd536d",
        )

    def test_candidate_repository_reads_valid_fresh_records_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            candidate = {
                "schema_version": 1,
                "record_type": "candidate",
                "session_id": "session-alpha",
                "project_path": str(root),
                "updated_at": "2026-07-21T11:00:00+00:00",
                "session_name": "Build",
                "project_name": "Demo",
            }
            (root / f"{session_key('session-alpha')}.json").write_text(
                json.dumps(candidate), encoding="utf-8"
            )
            (root / "wrong-name.json").write_text(
                json.dumps({**candidate, "session_id": "session-beta"}),
                encoding="utf-8",
            )

            records = CandidateRepository(root).list_candidates(now=now)

            self.assertEqual([record.session_id for record in records], ["session-alpha"])
            self.assertEqual(records[0].project_path, root)
            self.assertEqual(records[0].session_name, "Build")

    def test_repositories_skip_stale_malformed_future_and_symlink_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            base = {
                "schema_version": 1,
                "record_type": "candidate",
                "project_path": str(root),
                "session_name": "safe",
            }
            stale_id = "session-stale"
            stale = {
                **base,
                "session_id": stale_id,
                "updated_at": "2026-07-20T11:59:59+00:00",
            }
            (root / f"{session_key(stale_id)}.json").write_text(
                json.dumps(stale), encoding="utf-8"
            )
            future_id = "session-future"
            future = {
                **base,
                "session_id": future_id,
                "updated_at": "2026-07-21T12:06:00+00:00",
            }
            (root / f"{session_key(future_id)}.json").write_text(
                json.dumps(future), encoding="utf-8"
            )
            malformed_id = "session-malformed"
            (root / f"{session_key(malformed_id)}.json").write_text(
                "not-json", encoding="utf-8"
            )
            symlink_target = root / "target.json"
            symlink_target.write_text(json.dumps(stale), encoding="utf-8")
            symlink_path = root / f"{session_key('session-link')}.json"
            try:
                symlink_path.symlink_to(symlink_target)
            except OSError as error:
                self.skipTest(f"symlink unavailable: {error}")

            self.assertEqual(CandidateRepository(root).list_candidates(now=now), [])

    def test_rate_limit_repository_requires_rate_limit_record_and_valid_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            event = {
                "schema_version": 1,
                "record_type": "rate_limit",
                "reason": "rate_limit",
                "session_id": "session-alpha",
                "project_path": str(root),
                "updated_at": "2026-07-21T11:30:00+00:00",
            }
            (root / f"{session_key('session-alpha')}.json").write_text(
                json.dumps(event), encoding="utf-8"
            )
            (root / "other.json").write_text(
                json.dumps({**event, "reason": "other"}), encoding="utf-8"
            )

            records = RateLimitEventRepository(root).list_events(now=now)

            self.assertEqual([record.session_id for record in records], ["session-alpha"])

    def test_selection_is_in_memory_and_expires_after_twelve_hours(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            candidate = CandidateSession(
                schema_version=1,
                record_type="candidate",
                session_id="session-alpha",
                project_path=project,
                updated_at=now,
            )
            store = InMemorySelectionStore()

            activation = store.activate(candidate, now)

            self.assertTrue(store.is_selected(candidate.session_id))
            self.assertEqual(activation.expires_at, now + timedelta(hours=12))
            self.assertEqual(store.expire_due(now + timedelta(hours=12)), ("session-alpha",))
            self.assertFalse(store.is_selected(candidate.session_id))

    def test_next_boundary_skips_current_boundary_and_rolls_over_day(self):
        local = ZoneInfo("Asia/Tokyo")
        self.assertEqual(
            next_boundary(datetime(2026, 7, 21, 21, 10, tzinfo=local)),
            datetime(2026, 7, 21, 22, tzinfo=local),
        )
        self.assertEqual(
            next_boundary(datetime(2026, 7, 21, 22, 0, tzinfo=local)),
            datetime(2026, 7, 22, 0, 0, tzinfo=local),
        )

    def test_resume_eligibility_requires_selection_freshness_and_path_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            candidate = CandidateSession(
                schema_version=1,
                record_type="candidate",
                session_id="session-alpha",
                project_path=project,
                updated_at=now - timedelta(minutes=5),
                account_name="main",
            )
            event = RateLimitEvent(
                schema_version=1,
                record_type="rate_limit",
                reason="rate_limit",
                session_id="session-alpha",
                project_path=project,
                updated_at=now - timedelta(minutes=5),
                account_name="main",
            )
            store = InMemorySelectionStore()
            store.activate(candidate, now)

            decision = evaluate_resume(event, {candidate.session_id: candidate}, store, now)

            self.assertEqual(decision.status, "eligible")
            self.assertEqual(decision.request.session_id, "session-alpha")
            self.assertEqual(decision.request.message, "Continue")

    def test_resume_eligibility_carries_account_and_rejects_conflicting_account(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            candidate = CandidateSession(
                1, "candidate", "session-account", root, now, account_name="alias"
            )
            event = RateLimitEvent(
                1, "rate_limit", "rate_limit", "session-account", root, now, account_name="alias"
            )
            store = InMemorySelectionStore()
            store.activate(candidate, now)

            decision = evaluate_resume(event, {candidate.session_id: candidate}, store, now)

            self.assertEqual(decision.status, "eligible")
            self.assertEqual(decision.request.account_name, "alias")

            conflicting = RateLimitEvent(
                1, "rate_limit", "rate_limit", "session-account", root, now, account_name="main"
            )
            self.assertEqual(
                evaluate_resume(conflicting, {candidate.session_id: candidate}, store, now).status,
                "account_mismatch",
            )

    def test_repository_records_flow_into_resume_eligibility(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "candidates"
            events_dir = root / "rate_limits"
            candidates_dir.mkdir(mode=0o700)
            events_dir.mkdir(mode=0o700)
            (candidates_dir / "main").mkdir(mode=0o700)
            (events_dir / "main").mkdir(mode=0o700)
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)
            candidate = {
                "schema_version": 1,
                "record_type": "candidate",
                "session_id": "session-integrated",
                "project_path": str(root),
                "updated_at": "2026-07-21T11:55:00+00:00",
                "account_name": "main",
            }
            event = {
                "schema_version": 1,
                "record_type": "rate_limit",
                "reason": "rate_limit",
                "session_id": "session-integrated",
                "project_path": str(root),
                "updated_at": "2026-07-21T11:58:00+00:00",
                "account_name": "main",
            }
            key = session_key("session-integrated")
            (candidates_dir / "main" / f"{key}.json").write_text(
                json.dumps(candidate), encoding="utf-8"
            )
            (events_dir / "main" / f"{key}.json").write_text(
                json.dumps(event), encoding="utf-8"
            )

            candidate_records = CandidateRepository(candidates_dir).list_candidates(now=now)
            event_records = RateLimitEventRepository(events_dir).list_events(now=now)
            selection_store = InMemorySelectionStore()
            selection_store.activate(candidate_records[0], now)

            decision = evaluate_resume(
                event_records[0],
                {record.session_id: record for record in candidate_records},
                selection_store,
                now,
            )

            self.assertEqual(decision.status, "eligible")
            self.assertEqual(decision.request.project_path, root.resolve())

    def test_resume_eligibility_rejects_unselected_expired_stale_mismatch_and_processing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            other = root / "other"
            other.mkdir()
            now = datetime(2026, 7, 21, 12, tzinfo=UTC)

            def make_candidate(session_id, project_path, updated_at):
                return CandidateSession(
                    1, "candidate", session_id, project_path, updated_at, account_name="main"
                )

            candidate = make_candidate("session-alpha", root, now)
            event = RateLimitEvent(
                1, "rate_limit", "rate_limit", "session-alpha", root, now, account_name="main"
            )
            store = InMemorySelectionStore()

            self.assertEqual(
                evaluate_resume(event, {candidate.session_id: candidate}, store, now).status,
                "unselected",
            )
            store.activate(candidate, now)
            self.assertEqual(
                evaluate_resume(event, {candidate.session_id: candidate}, store, now, {"session-alpha"}).status,
                "processing",
            )
            store.deactivate("session-alpha")
            store.activate(candidate, now - timedelta(hours=12))
            self.assertEqual(
                evaluate_resume(event, {candidate.session_id: candidate}, store, now).status,
                "expired",
            )
            store.activate(make_candidate("session-alpha", root, now - timedelta(hours=25)), now)
            self.assertEqual(
                evaluate_resume(event, {candidate.session_id: make_candidate("session-alpha", root, now - timedelta(hours=25))}, store, now).status,
                "candidate_stale",
            )
            fresh_candidate = make_candidate("session-alpha", other, now)
            store.activate(fresh_candidate, now)
            self.assertEqual(
                evaluate_resume(event, {candidate.session_id: fresh_candidate}, store, now).status,
                "path_mismatch",
            )


if __name__ == "__main__":
    unittest.main()
