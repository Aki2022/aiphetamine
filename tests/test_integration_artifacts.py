import json
import plistlib
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from aiphetamine.hook_setup import build_hook_settings_fragment
from aiphetamine.launch_agent import LaunchAgentManager, LaunchAgentSpec


class IntegrationArtifactTests(unittest.TestCase):
    def test_launch_agent_plist_is_generated_without_registration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = LaunchAgentManager(root)
            spec = LaunchAgentSpec("/opt/python/bin/python3", "aiphetamine")

            plist_path = manager.write_plist(spec)
            payload = plistlib.loads(plist_path.read_bytes())

            self.assertEqual(payload["Label"], "local.aiphetamine.menubar")
            self.assertEqual(payload["ProgramArguments"], ["/opt/python/bin/python3", "-m", "aiphetamine"])
            self.assertTrue(payload["RunAtLoad"])
            self.assertFalse(payload["KeepAlive"])
            self.assertTrue(manager.is_generated())

    def test_hook_fragment_is_json_and_does_not_include_existing_settings_content(self):
        fragment = build_hook_settings_fragment("python3 /safe/aiphetamine_hook.py")
        encoded = json.dumps(fragment)

        self.assertEqual(fragment["hooks"]["SessionStart"][0]["hooks"][0]["type"], "command")
        self.assertIn("SessionEnd", fragment["hooks"])
        self.assertIn("StopFailure", fragment["hooks"])
        self.assertNotIn("existing", encoded.lower())

    def test_hook_fragment_rejects_untrusted_account_name(self):
        with self.assertRaisesRegex(ValueError, "invalid_account_name"):
            build_hook_settings_fragment("python3 /safe/aiphetamine_hook.py", "main; touch /tmp/marker")

    def test_hook_fragment_accepts_only_allowlisted_account_names(self):
        fragment = build_hook_settings_fragment("python3 /safe/aiphetamine_hook.py", "alias")
        command = fragment["hooks"]["SessionStart"][0]["hooks"][0]["command"]

        self.assertTrue(command.endswith("--account-name alias"))

    def test_hook_fragment_normalizes_safe_argv_and_rejects_shell_syntax(self):
        fragment = build_hook_settings_fragment('python3 "/safe path/aiphetamine hook.py"')
        command = fragment["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertEqual(
            shlex.split(command),
            ["python3", "/safe path/aiphetamine hook.py", "--event", "SessionStart"],
        )

        for unsafe in (
            "python3 /safe/hook.py; touch /tmp/marker",
            "python3 /safe/hook.py && touch /tmp/marker",
            "python3 /safe/hook.py $(touch /tmp/marker)",
            "python3 /safe/hook.py `touch /tmp/marker`",
            "PATH=/tmp/evil python3 /safe/hook.py",
            "PATH+=:/tmp/evil python3 /safe/hook.py",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaisesRegex(ValueError, "invalid_hook_command"):
                build_hook_settings_fragment(unsafe)


if __name__ == "__main__":
    unittest.main()
