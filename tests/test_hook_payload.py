import json
import io
import tempfile
import sys
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.spikes.hook_payload import (  # noqa: E402
    redact_hook_payload,
    validate_hook_payload,
)
from hooks.capture_sanitized_payload import capture_payload  # noqa: E402
from scripts.run_resume_spike import (  # noqa: E402
    _collect_safe_records,
    build_resume_command,
    classify_error,
    run as run_resume_spike,
)
from hooks.capture_candidate_lifecycle import process_lifecycle_payload  # noqa: E402
from scripts.run_candidate_lifecycle_spike import (  # noqa: E402
    _read_manifest,
    build_lifecycle_command,
    run as run_lifecycle_spike,
)


def make_valid_payload() -> dict[str, object]:
    return {
        "session_id": "".join(("fixture", "-session")),
        "cwd": "/fixture/project",
        "transcript_path": "/fixture/transcript.jsonl",
        "hook_event_name": "StopFailure",
        "reason": "rate_limit",
        "session_name": "fixture-session-name",
        "prompt": "".join(("fixture", "-prompt")),
        "api_token": "".join(("secret", "-marker")),
    }


class HookPayloadValidationTests(unittest.TestCase):
    def test_accepts_required_fields_and_classifies_optional_values(self) -> None:
        result = validate_hook_payload(make_valid_payload())

        self.assertTrue(result.accepted)
        self.assertIsNone(result.error_code)
        self.assertEqual(result.evidence["failure_reason_class"], "rate_limit")
        self.assertEqual(result.evidence["event_type_present"], True)
        self.assertEqual(result.evidence["session_name_present"], True)

    def test_rejects_payload_without_required_session_identity(self) -> None:
        payload = make_valid_payload()
        del payload["session_id"]

        result = validate_hook_payload(payload)

        self.assertFalse(result.accepted)
        self.assertEqual(result.error_code, "missing_session_id")

    def test_rejects_payload_with_non_string_required_field(self) -> None:
        payload = make_valid_payload()
        payload["cwd"] = 123

        result = validate_hook_payload(payload)

        self.assertFalse(result.accepted)
        self.assertEqual(result.error_code, "invalid_cwd")

    def test_redaction_never_keeps_sensitive_values_or_unknown_keys(self) -> None:
        payload = make_valid_payload()

        redacted = redact_hook_payload(payload)
        serialized = json.dumps(redacted, ensure_ascii=False, sort_keys=True)

        self.assertNotIn(payload["session_id"], serialized)
        self.assertNotIn(payload["cwd"], serialized)
        self.assertNotIn(payload["transcript_path"], serialized)
        self.assertNotIn(payload["prompt"], serialized)
        self.assertNotIn(payload["api_token"], serialized)
        self.assertNotIn("prompt", redacted)
        self.assertNotIn("api_token", redacted)
        self.assertEqual(redacted["failure_reason_class"], "rate_limit")

    def test_redaction_records_presence_without_retaining_untrusted_event_name(self) -> None:
        payload = make_valid_payload()
        payload["hook_event_name"] = "event-with-sensitive-details"

        redacted = redact_hook_payload(payload)

        self.assertEqual(redacted["event_type_present"], True)
        self.assertNotIn(payload["hook_event_name"], json.dumps(redacted))

    def test_capture_adapter_emits_only_redacted_evidence(self) -> None:
        output = io.StringIO()

        exit_code = capture_payload(
            io.StringIO(json.dumps(make_valid_payload())), output
        )

        self.assertEqual(exit_code, 0)
        captured = json.loads(output.getvalue())
        self.assertTrue(captured["accepted"])
        self.assertNotIn("fixture-session", output.getvalue())
        self.assertNotIn("/fixture/project", output.getvalue())

    def test_capture_adapter_handles_invalid_json_without_echoing_input(self) -> None:
        output = io.StringIO()

        exit_code = capture_payload(
            io.StringIO("not-json-" + "opaque-value"), output
        )

        self.assertEqual(exit_code, 0)
        captured = json.loads(output.getvalue())
        self.assertFalse(captured["accepted"])
        self.assertEqual(captured["error_code"], "invalid_json")
        self.assertNotIn("opaque-value", output.getvalue())

    def test_capture_entrypoint_keeps_stdout_empty_for_hook_control(self) -> None:
        script = Path(__file__).resolve().parents[1] / "hooks" / "capture_sanitized_payload.py"
        completed = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(make_valid_payload()),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn('"accepted": true', completed.stderr)
        self.assertNotIn("fixture-session", completed.stderr)

    def test_redaction_can_correlate_same_session_with_explicit_ephemeral_salt(self) -> None:
        changed_payload = make_valid_payload()
        changed_payload["cwd"] = "/fixture/other-project"

        with patch.dict("os.environ", {"AIPHEMETINE_CAPTURE_SALT": "test-salt"}):
            first = redact_hook_payload(make_valid_payload())
            second = redact_hook_payload(changed_payload)

        self.assertEqual(first["session_id_digest"], second["session_id_digest"])
        self.assertNotIn(make_valid_payload()["session_id"], json.dumps(first))

    def test_redaction_rejects_unencodable_session_id_without_traceback(self) -> None:
        payload = make_valid_payload()
        payload["session_id"] = "\ud800"

        with patch.dict("os.environ", {"AIPHEMETINE_CAPTURE_SALT": "test-salt"}):
            redacted = redact_hook_payload(payload)

        self.assertTrue(redacted["accepted"])
        self.assertNotIn("session_id_digest", redacted)

    def test_resume_command_uses_fixed_message_verbose_and_no_shell_flag(self) -> None:
        command = build_resume_command(
            "/usr/bin/claude",
            "fixture-session-id",
            Path("/repo/hooks/capture_sanitized_payload.py"),
            "fixture-salt",
        )

        self.assertEqual(command[0:4], ["/usr/bin/claude", "-p", "--resume", "fixture-session-id"])
        self.assertIn("--verbose", command)
        self.assertEqual(command[-1], "Continue")
        self.assertNotIn("--shell", command)

    def test_resume_error_classification_never_returns_raw_error(self) -> None:
        self.assertEqual(
            classify_error("Error: When using --print, --output-format=stream-json requires --verbose"),
            "cli_argument_validation",
        )
        self.assertEqual(classify_error("Error: session not found"), "resume_session")
        self.assertEqual(classify_error("permission denied"), "permission")
        self.assertNotIn("permission denied", classify_error("permission denied"))

    def test_resume_result_error_is_classified_without_retaining_raw_text(self) -> None:
        stream_types: set[str] = set()
        hook_names: set[str] = set()
        records: list[dict[str, object]] = []

        _collect_safe_records(
            {
                "type": "result",
                "is_error": True,
                "error": "session secret-session-id not found in private/path",
            },
            stream_types,
            hook_names,
            records,
        )

        self.assertEqual(stream_types, {"present"})
        self.assertEqual(records, [{"is_error": True, "result_error_class": "resume_session"}])
        serialized = json.dumps(records)
        self.assertNotIn("secret-session-id", serialized)
        self.assertNotIn("private/path", serialized)

    def test_resume_collector_never_emits_untrusted_labels_or_digest_values(self) -> None:
        stream_types: set[str] = set()
        hook_names: set[str] = set()
        records: list[dict[str, object]] = []

        _collect_safe_records(
            {
                "type": "arbitrary-stream-secret",
                "hook_event_name": "arbitrary-hook-secret",
                "session_id_digest": "arbitrary-digest-secret",
                "error_code": "arbitrary-error-secret",
            },
            stream_types,
            hook_names,
            records,
        )

        serialized = json.dumps(
            {"stream_types": sorted(stream_types), "hook_names": sorted(hook_names), "records": records}
        )
        self.assertEqual(stream_types, {"present"})
        self.assertEqual(hook_names, {"present"})
        self.assertNotIn("arbitrary-stream-secret", serialized)
        self.assertNotIn("arbitrary-hook-secret", serialized)
        self.assertNotIn("arbitrary-digest-secret", serialized)
        self.assertNotIn("arbitrary-error-secret", serialized)

    def test_candidate_lifecycle_creates_refreshes_and_removes_safe_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = make_valid_payload()
            payload["hook_event_name"] = "SessionStart"

            with patch.dict(
                "os.environ",
                {
                    "AIPHEMETINE_LIFECYCLE_ROOT": directory,
                    "AIPHEMETINE_CAPTURE_SALT": "test-salt",
                },
            ):
                first = io.StringIO()
                self.assertEqual(process_lifecycle_payload(payload, first), 0)
                payload["hook_event_name"] = "UserPromptSubmit"
                second = io.StringIO()
                self.assertEqual(process_lifecycle_payload(payload, second), 0)
                payload["hook_event_name"] = "SessionEnd"
                third = io.StringIO()
                self.assertEqual(process_lifecycle_payload(payload, third), 0)

            events = [json.loads(line) for line in Path(directory, "lifecycle.jsonl").read_text().splitlines()]
            self.assertEqual([event["action"] for event in events], ["upsert", "upsert", "remove"])
            self.assertEqual([event["revision"] for event in events], [1, 2, None])
            self.assertEqual([event["candidate_exists_after"] for event in events], [True, True, False])
            serialized = Path(directory, "lifecycle.jsonl").read_text()
            self.assertNotIn("fixture-session", serialized)
            self.assertNotIn("/fixture/project", serialized)

    def test_lifecycle_command_includes_candidate_events_and_fixed_message(self) -> None:
        command = build_lifecycle_command(
            "/usr/bin/claude",
            Path("/repo/hooks/capture_candidate_lifecycle.py"),
            Path("/repo/.lifecycle"),
            "fixture-salt",
        )

        self.assertIn("--verbose", command)
        self.assertEqual(command[-1], "Respond with OK only.")
        settings = json.loads(command[command.index("--settings") + 1])
        self.assertEqual(
            set(settings["hooks"]),
            {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"},
        )

    def test_lifecycle_manifest_classifies_untrusted_revision_without_echoing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "lifecycle.jsonl").write_text(
                json.dumps(
                    {
                        "event_class": "SessionStart",
                        "action": "upsert",
                        "revision": 987654321,
                        "accepted": True,
                        "candidate_exists_after": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            records = _read_manifest(Path(directory))

            serialized = json.dumps(records)
            self.assertEqual(records[0]["revision_class"], "invalid")
            self.assertNotIn("987654321", serialized)

    def test_lifecycle_manifest_rejects_untyped_fields_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "lifecycle.jsonl").write_text(
                json.dumps(
                    {
                        "event_class": [],
                        "action": {},
                        "error_code": [],
                        "revision": {},
                        "accepted": [],
                        "candidate_exists_after": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            records = _read_manifest(Path(directory))

            self.assertEqual(
                records,
                [
                    {
                        "event_class": "other",
                        "action": "other",
                        "accepted": False,
                        "error_code_class": "none",
                        "revision_class": "invalid",
                        "candidate_exists_after": False,
                    }
                ],
            )

    def test_lifecycle_manifest_ignores_invalid_utf8_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "lifecycle.jsonl").write_bytes(b"\xff\xfe\n")

            self.assertEqual(_read_manifest(Path(directory)), [])

    def test_resume_collector_stops_at_a_safe_nesting_depth(self) -> None:
        value: object = None
        for _ in range(1100):
            value = [value]
        stream_types: set[str] = set()
        hook_names: set[str] = set()
        records: list[dict[str, object]] = []

        _collect_safe_records(value, stream_types, hook_names, records)

        self.assertEqual(records, [])

    def test_resume_spike_classifies_launch_error_without_echoing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.dict(
                "os.environ",
                {
                    "AIPHEMETINE_RESUME_SESSION_ID": "fixture-session",
                    "AIPHEMETINE_RESUME_CWD": directory,
                    "AIPHEMETINE_ORIGINAL_PROCESS_PRESENT": "false",
                    "AIPHEMETINE_CLAUDE_EXECUTABLE": "/private/tmp/review-secret-path/claude",
                },
            ), patch(
                "scripts.run_resume_spike.subprocess.run",
                side_effect=FileNotFoundError(2, "No such file", "/private/tmp/review-secret-path/claude"),
            ), patch("sys.stdout", output):
                exit_code = run_resume_spike()

            self.assertEqual(exit_code, 1)
            self.assertIn("claude_exit=launch_error", output.getvalue())
            self.assertIn("error_class=executable_or_hook_not_found", output.getvalue())
            self.assertNotIn("review-secret-path", output.getvalue())
            self.assertNotIn("Errno 2", output.getvalue())

    def test_lifecycle_spike_classifies_launch_error_without_echoing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.dict(
                "os.environ",
                {
                    "AIPHEMETINE_LIFECYCLE_CWD": directory,
                    "AIPHEMETINE_CLAUDE_EXECUTABLE": "/private/tmp/review-secret-path/claude",
                },
            ), patch(
                "scripts.run_candidate_lifecycle_spike.subprocess.run",
                side_effect=FileNotFoundError(2, "No such file", "/private/tmp/review-secret-path/claude"),
            ), patch("sys.stdout", output):
                exit_code = run_lifecycle_spike()

            self.assertEqual(exit_code, 1)
            self.assertIn("claude_exit=launch_error", output.getvalue())
            self.assertIn("error_class=executable_or_hook_not_found", output.getvalue())
            self.assertNotIn("review-secret-path", output.getvalue())
            self.assertNotIn("Errno 2", output.getvalue())


if __name__ == "__main__":
    unittest.main()
