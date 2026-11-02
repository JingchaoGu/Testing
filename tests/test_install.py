import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE_CODEX = '''import json, os, pathlib, sys
arguments = sys.argv[1:]
with pathlib.Path(os.environ["INSTALL_CALLS"]).open("a") as stream:
    stream.write(json.dumps(arguments) + "\\n")
mode = os.environ.get("INSTALL_MODE", "modern")
if arguments[:3] == ["plugin", "marketplace", "add"]:
    sys.exit(7 if mode == "marketplace-fail" else 0)
if arguments == ["plugin", "add", "--help"]:
    sys.exit(2 if mode == "legacy" else 0)
if arguments == ["plugin", "add", "playbook-testing@testing-playbook"]:
    sys.exit(9 if mode == "plugin-fail" else 0)
sys.exit(99)
'''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="playbook-install-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "fake tools with spaces"
        self.directory.mkdir()
        fake = self.directory / "fake_codex.py"
        fake.write_text(FAKE_CODEX, encoding="utf-8")
        executable = self.directory / ("codex.cmd" if os.name == "nt" else "codex")
        if os.name == "nt":
            executable.write_text(f'@echo off\n"{sys.executable}" "{fake}" %*\n', encoding="utf-8")
        else:
            executable.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(fake))} "$@"\n', encoding="utf-8")
            executable.chmod(0o755)
        self.calls = self.directory / "calls.jsonl"
        self.environment = dict(os.environ, PATH=str(self.directory) + os.pathsep + os.environ.get("PATH", ""),
                                INSTALL_CALLS=str(self.calls))

    def run_installer(self, mode="modern"):
        self.environment["INSTALL_MODE"] = mode
        if os.name == "nt":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            self.assertIsNotNone(shell, "Windows installer tests require PowerShell")
            argv = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/install.ps1")]
        else:
            argv = ["/bin/sh", str(ROOT / "scripts/install.sh")]
        result = subprocess.run(argv, cwd=self.directory, env=self.environment, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=30)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        return result, calls

    def test_native_wrapper_registers_and_installs_without_touching_trust(self):
        result, calls = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[0], ["plugin", "marketplace", "add", "JingchaoGu/Testing", "--ref", "main"])
        self.assertEqual(calls[-1], ["plugin", "add", "playbook-testing@testing-playbook"])
        self.assertEqual(len(calls), 3)
        self.assertIn("/hooks", result.stdout)

    def test_legacy_cli_reports_registration_only(self):
        result, calls = self.run_installer("legacy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 2)
        self.assertIn("cannot install plugins directly", result.stdout)
        self.assertIn("desktop", result.stdout)

    def test_registration_and_installation_failures_propagate(self):
        for mode, expected, count in (("marketplace-fail", 7, 1), ("plugin-fail", 9, 3)):
            with self.subTest(mode=mode):
                if self.calls.exists():
                    self.calls.unlink()
                result, calls = self.run_installer(mode)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(len(calls), count)
                self.assertIn("failed", result.stderr)

    def test_missing_git_does_not_register_anything(self):
        environment = dict(self.environment, PATH="")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/install_plugin.py")],
                                env=environment, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Git is required", result.stderr)
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
