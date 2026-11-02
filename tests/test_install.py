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
FAKE_CURL = '''import os, shutil, sys
arguments = sys.argv[1:]
assert "https://raw.githubusercontent.com/JingchaoGu/Testing/main/scripts/install_plugin.py" in arguments
destination = arguments[arguments.index("--output") + 1]
# Write a valid payload before failing to prove partial downloads are not run.
shutil.copyfile(os.environ["BOOTSTRAP_PAYLOAD"], destination)
sys.exit(22 if os.environ.get("BOOTSTRAP_DOWNLOAD_FAIL") else 0)
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
        self.environment.update(BOOTSTRAP_PAYLOAD=str(ROOT / "scripts/install_plugin.py"),
                                TEMP=str(self.directory), TMP=str(self.directory), TMPDIR=str(self.directory))
        if os.name != "nt":
            curl = self.directory / "curl"
            implementation = self.directory / "fake_curl.py"
            implementation.write_text(FAKE_CURL, encoding="utf-8")
            curl.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(implementation))} "$@"\n', encoding="utf-8")
            curl.chmod(0o755)

    def run_installer(self, mode="modern", bootstrap=False, download_fail=False):
        self.environment["INSTALL_MODE"] = mode
        self.environment["BOOTSTRAP_DOWNLOAD_FAIL"] = "1" if download_fail else ""
        script_input = None
        if os.name == "nt":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            self.assertIsNotNone(shell, "Windows installer tests require PowerShell")
            if bootstrap:
                command = '''function Invoke-WebRequest {
                    [CmdletBinding()]
                    param($Uri, $OutFile, [switch]$UseBasicParsing)
                    if ($Uri -ne 'https://raw.githubusercontent.com/JingchaoGu/Testing/main/scripts/install_plugin.py') { throw 'Unexpected URL' }
                    Copy-Item -LiteralPath $env:BOOTSTRAP_PAYLOAD -Destination $OutFile
                    if ($env:BOOTSTRAP_DOWNLOAD_FAIL) { throw 'Download failed after writing partial content' }
                }
                '''
                harness = self.directory / "bootstrap-test.ps1"
                harness.write_text(command + (ROOT / "install.ps1").read_text(encoding="utf-8"), encoding="utf-8")
                argv = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)]
            else:
                argv = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/install.ps1")]
        else:
            if bootstrap:
                argv = ["/bin/sh"]
                script_input = (ROOT / "install.sh").read_text(encoding="utf-8")
            else:
                argv = ["/bin/sh", str(ROOT / "scripts/install.sh")]
        result = subprocess.run(argv, cwd=self.directory, env=self.environment, capture_output=True,
                                input=script_input, text=True, encoding="utf-8", errors="replace", timeout=30)
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

    def test_streamed_bootstrap_installs_without_local_sibling_files(self):
        result, calls = self.run_installer(bootstrap=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[-1], ["plugin", "add", "playbook-testing@testing-playbook"])
        self.assertEqual(list(self.directory.glob("playbook-bootstrap-*")), [])

    def test_download_failure_never_executes_partial_payload(self):
        result, calls = self.run_installer(bootstrap=True, download_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])
        self.assertEqual(list(self.directory.glob("playbook-bootstrap-*")), [])

    def test_streamed_bootstrap_propagates_install_failure_and_cleans_up(self):
        result, calls = self.run_installer(mode="plugin-fail", bootstrap=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 3)
        self.assertEqual(list(self.directory.glob("playbook-bootstrap-*")), [])


if __name__ == "__main__":
    unittest.main()
