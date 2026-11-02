import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import codex_hooks
import package_plugin


class HookRegistryTests(unittest.TestCase):
    def payload(self):
        return {"result": {"data": [{"hooks": [{"pluginId": codex_hooks.PLUGIN_ID,
            "eventName": event, "enabled": True, "trustStatus": "trusted"}
            for event in sorted(codex_hooks.EXPECTED_EVENTS)], "errors": []}]}}

    def test_partial_disabled_modified_and_unrelated_hooks_do_not_look_active(self):
        payload = self.payload()
        self.assertEqual(codex_hooks.summarize(payload)["status"], "trusted")
        for field, value, expected in (("trustStatus", "untrusted", "review-required"),
                ("trustStatus", "modified", "review-required"), ("enabled", False, "disabled"),
                ("pluginId", "another-plugin@source", "not-discovered")):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(payload)
                changed["result"]["data"][0]["hooks"][0][field] = value
                self.assertEqual(codex_hooks.summarize(changed)["status"], expected)
        payload["result"]["data"][0]["hooks"].pop()
        self.assertEqual(codex_hooks.summarize(payload)["status"], "not-discovered")

    def test_parse_errors_and_unavailable_cli_are_not_trust(self):
        payload = self.payload()
        payload["result"]["data"][0]["errors"] = [{"path": "playbook-testing/hooks/hooks.json", "message": "invalid"}]
        self.assertEqual(codex_hooks.summarize(payload)["status"], "invalid")
        with patch.object(codex_hooks.shutil, "which", return_value=None):
            self.assertEqual(codex_hooks.inspect(ROOT)["status"], "unknown")


class NativeCodexTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("PLAYBOOK_TEST_CODEX_BIN") or shutil.which("codex"), "Native Codex CLI unavailable")
    def test_packaged_plugin_is_discovered_and_requires_real_user_trust(self):
        executable = os.environ.get("PLAYBOOK_TEST_CODEX_BIN") or shutil.which("codex")
        with tempfile.TemporaryDirectory(prefix="playbook-native-") as temporary:
            target = Path(temporary).resolve()
            home = target / "codex-home"
            home.mkdir()
            package = package_plugin.package(ROOT, target / "plugin.zip")
            with zipfile.ZipFile(package) as archive:
                archive.extractall(target / "install")
            plugin = target / "install/playbook-testing"
            with patch.dict(os.environ, CODEX_HOME=str(home)):
                for arguments in (("plugin", "marketplace", "add", str(plugin)),
                                  ("plugin", "add", codex_hooks.PLUGIN_ID)):
                    process = subprocess.run([executable, *arguments], capture_output=True, text=True,
                                             encoding="utf-8", errors="replace", timeout=30)
                    self.assertEqual(process.returncode, 0, process.stderr)
                result = codex_hooks.inspect(target, executable)
            self.assertEqual(result["status"], "review-required", result)
            self.assertEqual({row["eventName"] for row in result["hooks"]}, codex_hooks.EXPECTED_EVENTS)
            self.assertTrue(all(row["trustStatus"] == "untrusted" for row in result["hooks"]))
            if os.name == "nt":
                self.assertTrue(all(row["command"].startswith("py -3 ") for row in result["hooks"]))
            self.assertFalse((target / ".testing-results/last-hook-event.json").exists())


if __name__ == "__main__":
    unittest.main()
