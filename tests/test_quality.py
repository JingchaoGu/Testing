import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import agent_hook
import install_git_hooks
import package_plugin
import quality
import setup_repo

FIXTURE = '''import pathlib, sys, time, xml.etree.ElementTree as E
mode = pathlib.Path("value.txt").read_text().strip()
if mode == "sleep": time.sleep(5)
if mode == "missing": sys.exit(0)
if mode == "mutate": pathlib.Path("value.txt").write_text("pass")
root = E.Element("testsuite")
if mode == "suite-error": root.set("errors", "1")
if mode != "zero":
    case = E.SubElement(root, "testcase", name="behavior")
    if mode == "fail": E.SubElement(case, "failure")
    if mode == "skip": E.SubElement(case, "skipped")
path = pathlib.Path(sys.argv[1]); path.parent.mkdir(parents=True, exist_ok=True)
E.ElementTree(root).write(path)
'''


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "PLAYBOOK_TESTING_RUNNING": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.temporary = tempfile.TemporaryDirectory(prefix="playbook-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo with spaces"
        os.environ["PLUGIN_DATA"] = str(Path(self.temporary.name) / "plugin-data")
        self.repo.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.name", "Test Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        (self.repo / ".gitignore").write_text(".testing-results/\n__pycache__/\n", encoding="utf-8")
        (self.repo / "fixture.py").write_text(FIXTURE, encoding="utf-8")
        (self.repo / "value.txt").write_text("pass", encoding="utf-8")
        self.policy = {"version": 1, "agent_hooks": True,
            "checks": {"unit": {"kind": "test", "argv": ["{python}", "fixture.py", "{report}"], "timeout": 20}},
            "stages": {name: ["unit"] for name in ("edit", "task-finish", "commit", "push", "pr")}}
        self.save_policy()
        self.git("add", "--all")
        self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture")

    def git(self, *args, success=True):
        process = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, encoding="utf-8")
        if success:
            self.assertEqual(process.returncode, 0, process.stderr)
        return process

    def save_policy(self):
        (self.repo / quality.POLICY).write_text(json.dumps(self.policy), encoding="utf-8")

    def mode(self, value):
        (self.repo / "value.txt").write_text(value, encoding="utf-8")

    def test_passing_evidence_and_verify(self):
        result = quality.run(self.repo, "pr")
        self.assertEqual(result["status"], "passed")
        self.assertTrue(quality.verify(self.repo, "pr", self.repo / quality.RESULTS / "pr.json"))

    def test_failures_zero_all_skipped_missing_and_suite_errors_are_not_green(self):
        for mode in ("fail", "zero", "skip", "missing", "suite-error"):
            with self.subTest(mode=mode):
                self.mode(mode)
                result = quality.run(self.repo, "pr")
                self.assertEqual(result["status"], "failed")

    def test_stale_report_is_not_reused(self):
        quality.run(self.repo, "pr")
        self.mode("missing")
        result = quality.run(self.repo, "pr")
        self.assertEqual(result["checks"][0]["status"], "error")

    def test_modified_and_untracked_inputs_invalidate_evidence(self):
        for filename in ("value.txt", "new source.txt"):
            with self.subTest(filename=filename):
                quality.run(self.repo, "pr")
                (self.repo / filename).write_text("changed", encoding="utf-8")
                self.assertFalse(quality.verify(self.repo, "pr", self.repo / quality.RESULTS / "pr.json"))

    def test_inputs_mutated_during_check_do_not_pass(self):
        self.mode("mutate")
        result = quality.run(self.repo, "pr")
        self.assertEqual(result["status"], "failed")
        self.assertNotEqual(result["snapshot"], result["snapshot_after"])

    def test_timeout_and_missing_program_are_not_passes(self):
        self.mode("sleep")
        self.policy["checks"]["unit"]["timeout"] = 0.05
        self.save_policy()
        self.assertEqual(quality.run(self.repo, "pr")["checks"][0]["status"], "timed_out")
        self.policy["checks"]["unit"]["argv"][0] = "nonexistent-playbook-command-12345"
        self.save_policy()
        self.assertEqual(quality.run(self.repo, "pr")["checks"][0]["status"], "error")

    def test_empty_missing_unknown_and_duplicate_stages_fail(self):
        for selected in ([], ["missing"], ["unit", "unit"]):
            with self.subTest(selected=selected):
                self.policy["stages"]["pr"] = selected
                self.save_policy()
                with self.assertRaises(quality.QualityError):
                    quality.run(self.repo, "pr")

    def test_test_without_report_contract_is_rejected(self):
        self.policy["checks"]["unit"]["argv"] = ["echo", "success"]
        self.save_policy()
        with self.assertRaises(quality.QualityError):
            quality.load_policy(self.repo)

    def test_command_check_has_no_test_count_requirement(self):
        self.policy["checks"]["unit"] = {"kind": "command", "argv": ["{python}", "-c", "pass"]}
        self.save_policy()
        self.assertEqual(quality.run(self.repo, "pr")["status"], "passed")

    def test_missing_or_tampered_evidence_is_rejected(self):
        evidence = self.repo / quality.RESULTS / "pr.json"
        self.assertFalse(quality.verify(self.repo, "pr", evidence))
        quality.run(self.repo, "pr")
        record = json.loads(evidence.read_text())
        record["checks"] = []
        quality.write_json(evidence, record)
        self.assertFalse(quality.verify(self.repo, "pr", evidence))

    def test_lock_prevents_concurrent_execution(self):
        with quality.execution_lock(self.repo):
            with self.assertRaises(quality.QualityError):
                quality.run(self.repo, "pr")
        self.assertFalse((self.repo / quality.RESULTS / "run.lock").exists())

    def test_commit_uses_index_and_preserves_unstaged_fix(self):
        self.mode("fail")
        self.git("add", "value.txt")
        self.mode("pass")
        before = self.git("diff", "--binary").stdout
        result = quality.run(self.repo, "commit")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.git("show", ":value.txt").stdout, "fail")
        self.assertEqual(self.git("diff", "--binary").stdout, before)

    def test_commit_ignores_untracked_working_tree_inputs(self):
        (self.repo / "not committed.txt").write_text("local only", encoding="utf-8")
        result = quality.run(self.repo, "commit")
        self.assertEqual(result["status"], "passed")
        self.assertTrue((self.repo / "not committed.txt").exists())

    def test_snapshot_clears_foreign_git_environment_and_restores_it(self):
        index = self.repo / ".git/index"
        original = index.read_bytes()
        with patch.dict(os.environ, {"GIT_INDEX_FILE": str(index), "GIT_DIR": str(self.repo / ".git")}):
            self.assertEqual(quality.run(self.repo, "commit")["status"], "passed")
            self.assertEqual(os.environ["GIT_INDEX_FILE"], str(index))
        self.assertEqual(index.read_bytes(), original)

    def test_unexpanded_lfs_is_rejected(self):
        (self.repo / "asset.dat").write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1\n")
        with self.assertRaises(quality.QualityError):
            quality.run(self.repo, "pr")

    def test_push_checks_non_head_and_handles_deletion_multiple_refs(self):
        self.mode("fail")
        self.git("add", "value.txt")
        self.git("commit", "--quiet", "-m", "bad candidate")
        candidate = self.git("rev-parse", "HEAD").stdout.strip()
        self.mode("pass")
        self.git("add", "value.txt")
        self.git("commit", "--quiet", "-m", "good head")
        line = f"refs/heads/candidate {candidate} refs/heads/remote {'0' * 40}\n"
        results = quality.pre_push(self.repo, line + line + f"(delete) {'0' * 40} refs/heads/deleted {candidate}\n")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(quality.pre_push(self.repo, ""), [])

    def test_real_git_pre_commit_and_pre_push(self):
        install_git_hooks.install(self.repo, ["pre-commit", "pre-push"])
        self.mode("fail")
        self.git("add", "value.txt")
        rejected = self.git("commit", "-m", "must fail", success=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.mode("pass")
        (self.repo / "new.txt").write_text("candidate", encoding="utf-8")
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "must pass")
        remote = Path(self.temporary.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True)
        self.git("push", str(remote), "HEAD:refs/heads/passing")
        self.mode("fail")
        self.git("add", "value.txt")
        self.git("-c", "core.hooksPath=disabled-fixture-hooks", "commit", "--quiet", "-m", "bypass local commit test")
        self.assertNotEqual(self.git("push", str(remote), "HEAD:refs/heads/failing", success=False).returncode, 0)

    def test_existing_hook_and_hooks_path_are_preserved(self):
        hook = self.repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\necho existing\n", encoding="utf-8")
        with self.assertRaises(quality.QualityError):
            install_git_hooks.install(self.repo, ["pre-commit", "pre-push"])
        self.assertIn("existing", hook.read_text())
        self.assertFalse((hook.parent / "pre-push").exists())
        self.git("config", "core.hooksPath", "custom-hooks")
        with self.assertRaises(quality.QualityError):
            install_git_hooks.install(self.repo, ["pre-push"])
        self.assertEqual(self.git("config", "--get", "core.hooksPath").stdout.strip(), "custom-hooks")

    def test_vendored_setup_and_actual_commit_hook(self):
        setup_repo.setup(self.repo, github=True)
        installer = self.repo / ".testing-tools/install_git_hooks.py"
        installed = subprocess.run([sys.executable, str(installer), "--repo", str(self.repo), "--events", "pre-commit"], capture_output=True, text=True)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertIn(".testing-tools/quality.py", (self.repo / ".git/hooks/pre-commit").read_text())
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "vendored runtime works")
        self.mode("fail")
        self.git("add", "value.txt")
        self.assertNotEqual(self.git("commit", "-m", "must fail", success=False).returncode, 0)
        installed = (self.repo / ".testing-tools/quality.py")
        installed.write_text("custom implementation", encoding="utf-8")
        with self.assertRaises(quality.QualityError):
            setup_repo.setup(self.repo)
        self.assertEqual(installed.read_text(), "custom implementation")

    def test_distribution_has_runtime_and_no_project_data(self):
        import zipfile
        target = Path(self.temporary.name) / "plugin.zip"
        package_plugin.package(SCRIPTS.parent, target)
        with zipfile.ZipFile(target) as archive:
            names = archive.namelist()
            self.assertIn("playbook-testing/plugin.json", names)
            self.assertIn("playbook-testing/hooks/hooks.json", names)
            self.assertIn("playbook-testing/.agents/plugins/marketplace.json", names)
            self.assertTrue(all("/.git/" not in name and "/.testing-results/" not in name and "/__pycache__/" not in name for name in names))
            self.assertNotIn("playbook-testing/.testing-policy.json", names)

    def test_unittest_report_handles_subtest_and_class_setup_errors(self):
        directory = self.repo / "isolated-tests"
        directory.mkdir()
        (directory / "test_example.py").write_text('''import unittest
class Example(unittest.TestCase):
    def test_subtest(self):
        with self.subTest(number=1): self.assertEqual(1, 2)
class SetupError(unittest.TestCase):
    @classmethod
    def setUpClass(cls): raise RuntimeError("fixture setup failed")
    def test_never_runs(self): pass
''', encoding="utf-8")
        report = self.repo / ".testing-results/helper.xml"
        result = subprocess.run([sys.executable, str(SCRIPTS / "unittest_junit.py"), "--start", str(directory), "--report", str(report)], cwd=self.repo, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        counts = quality.parse_junit(report)
        self.assertGreaterEqual(counts["failed"], 2)

    def test_smoke_failure_prevents_expensive_check(self):
        self.policy["checks"]["smoke"] = self.policy["checks"]["unit"]
        self.policy["checks"]["expensive"] = {"kind": "command", "argv": ["{python}", "-c", "open('unexpected.txt','w').write('ran')"]}
        self.policy["stages"]["release"] = ["smoke", "expensive"]
        self.save_policy()
        self.mode("fail")
        with patch.dict(os.environ, {"TESTING_ENVIRONMENT": "staging", "TESTING_ARTIFACT": "sha256:fixture"}):
            result = quality.run(self.repo, "release")
        self.assertEqual([item["check_id"] for item in result["checks"]], ["smoke"])
        self.assertFalse((self.repo / "unexpected.txt").exists())

    def test_release_requires_environment_artifact_and_smoke_first(self):
        self.policy["stages"]["release"] = ["unit"]
        self.save_policy()
        with self.assertRaises(quality.QualityError):
            quality.run(self.repo, "release")
        self.policy["checks"]["smoke"] = self.policy["checks"]["unit"]
        self.policy["stages"]["release"] = ["smoke"]
        self.save_policy()
        with patch.dict(os.environ, {"TESTING_ENVIRONMENT": "", "TESTING_ARTIFACT": ""}):
            with self.assertRaises(quality.QualityError):
                quality.run(self.repo, "release")

    def test_snapshot_rejects_traversal_and_links(self):
        for name, kind in (("../outside", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)):
            with self.subTest(name=name):
                output = io.BytesIO()
                with tarfile.open(fileobj=output, mode="w") as archive:
                    item = tarfile.TarInfo(name)
                    item.type = kind
                    item.linkname = "../../outside"
                    archive.addfile(item)
                real_git = quality.git
                def fake_git(repo, *args, **kwargs):
                    return output.getvalue() if args[0] == "archive" else real_git(repo, *args, **kwargs)
                with patch.object(quality, "git", side_effect=fake_git):
                    with self.assertRaises(quality.QualityError):
                        with quality.exported_snapshot(self.repo, "HEAD"):
                            self.fail("Unsafe archive accepted")

    def event(self, name, **values):
        return dict(cwd=str(self.repo), session_id="fixture", hook_event_name=name, **values)

    def test_agent_unchanged_and_disabled_repositories_do_not_run(self):
        self.assertIn("hookSpecificOutput", agent_hook.handle(self.event("SessionStart")))
        self.assertEqual(agent_hook.handle(self.event("PostToolUse")), {})
        self.assertEqual(agent_hook.handle(self.event("Stop")), {})
        self.policy["agent_hooks"] = False
        self.save_policy()
        self.mode("fail")
        self.assertEqual(agent_hook.handle(self.event("Stop")), {})

    def test_agent_red_feedback_and_bounded_stop_continuation(self):
        agent_hook.handle(self.event("SessionStart"))
        self.mode("fail")
        feedback = agent_hook.handle(self.event("PostToolUse"))
        self.assertIn("failed", feedback["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("decision", feedback)
        self.assertEqual(agent_hook.handle(self.event("PostToolUse")), {})
        self.assertEqual(agent_hook.handle(self.event("Stop"))["decision"], "block")
        continuation = agent_hook.handle(self.event("Stop", stop_hook_active=True))
        self.assertNotIn("decision", continuation)
        self.assertIn("incomplete", continuation["systemMessage"])
        self.mode("pass")
        self.assertEqual(agent_hook.handle(self.event("Stop", stop_hook_active=True)), {})

    def test_agent_config_errors_are_visible_and_do_not_loop(self):
        (self.repo / quality.POLICY).write_text("{invalid", encoding="utf-8")
        self.assertEqual(agent_hook.handle(self.event("Stop"))["decision"], "block")
        self.assertNotIn("decision", agent_hook.handle(self.event("Stop", stop_hook_active=True)))


if __name__ == "__main__":
    unittest.main()
