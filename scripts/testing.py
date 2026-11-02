#!/usr/bin/env python3
"""Local commands for Playbook Testing; project reasoning stays in the skill."""
import argparse
import json
from pathlib import Path
import sys

import install_git_hooks
import quality

COMMANDS = {
    "init": "Plan and build risk-based tests, then connect project stage hooks",
    "plan": "Recommend test actions for each component, risk and delivery stage",
    "check": "Run an existing testing stage (default: task-finish)",
    "fix": "Diagnose a failed check, repair and rerun",
    "doctor": "Inspect configuration without running tests or changing files",
    "hooks": "Show or change this project's agent hook opt-in",
    "ci": "Connect PR checks to the existing CI platform",
    "release": "Validate an existing candidate, starting with smoke tests",
}
# Leave room for snapshotting, report parsing and process cleanup within hook timeouts.
AGENT_BUDGETS = {"edit": 100, "task-finish": 150}


def agent_issues(policy):
    issues = []
    for stage, budget in AGENT_BUDGETS.items():
        checks = policy["stages"].get(stage, [])
        if not checks:
            issues.append(f"Configure a nonempty {stage} stage before enabling agent hooks")
        elif sum(policy["checks"][name].get("timeout", 60) for name in checks) > budget:
            issues.append(f"{stage}: total configured timeout must be <= {budget}s; move long checks to Git/CI")
    return issues


def hooks(repo, action):
    repo = repo.resolve()
    policy = quality.load_policy(repo)
    if action == "on":
        issues = agent_issues(policy)
        if issues:
            raise quality.QualityError("; ".join(issues))
    if action != "status":
        path = repo / quality.POLICY
        if path.is_symlink() or not path.resolve().is_relative_to(repo):
            raise quality.QualityError("Refusing to modify a linked policy")
        enabled = action == "on"
        if policy.get("agent_hooks") is not enabled:
            policy["agent_hooks"] = enabled
            quality.write_json(path, policy)
    return {"agent_hooks": policy.get("agent_hooks") is True,
            "codex_trust": "Review current definitions in /hooks; this command does not change trust",
            "git_hooks": "unchanged"}


def doctor(repo):
    result = {"repo": str(repo), "issues": [], "tests_run": False,
              "codex_trust": "not inspected; review /hooks",
              "remote_rules": "not inspected"}
    try:
        policy = quality.load_policy(repo)
        result["stages"] = {name: checks for name, checks in policy["stages"].items() if checks}
        if not result["stages"]:
            result["issues"].append("Initialization incomplete: no executable testing stages. Continue $playbook-testing init to create or map real tests")
        result["required_stages"] = policy.get("required_stages", [])
        result["unconfigured_required_stages"] = [stage for stage in result["required_stages"] if not policy["stages"].get(stage)]
        if result["unconfigured_required_stages"]:
            result["issues"].append("Core stages lack checks: " + ", ".join(result["unconfigured_required_stages"]))
        result["agent_hooks"] = policy.get("agent_hooks") is True
        result["agent_readiness"] = agent_issues(policy)
        if result["agent_hooks"]:
            result["issues"].extend(result["agent_readiness"])
        result["evidence"] = {}
        for stage in result["stages"]:
            path = repo / quality.RESULTS / (stage + ".json")
            if stage in ("commit", "push"):
                status = "requires synchronous Git-hook validation; worktree evidence not assessed"
            elif not path.is_file():
                status = "missing"
            else:
                status = "current pass" if quality.verify(repo, stage, path) else "not a verified current pass"
            result["evidence"][stage] = status
    except quality.QualityError as exc:
        result["issues"].append(str(exc))
    if install_git_hooks.has_custom_hooks_path(repo):
        result["git_hooks"] = "external core.hooksPath; inspect the existing manager's chain"
    else:
        directory = Path(quality.git(repo, "rev-parse", "--git-path", "hooks"))
        if not directory.is_absolute():
            directory = repo / directory
        result["git_hooks"] = {}
        for name in ("pre-commit", "pre-push"):
            path = directory / name
            result["git_hooks"][name] = ("absent" if not path.exists() else
                "playbook wrapper present; execution not verified" if install_git_hooks.MARKER in
                path.read_text(encoding="utf-8", errors="replace") else "existing hook; inspect its chain")
    result["github_workflow_files"] = {
        name: "present; trigger/caller wiring and remote rules need verification" if (repo / path).is_file()
        else "not generated here; inspect existing CI/CD or complete init"
        for name, path in (("pr", ".github/workflows/playbook-quality.yml"),
                           ("delivery", ".github/workflows/playbook-delivery.yml"))}
    return result


def shortcut_text(command):
    return f'''---
name: pt-{command}
description: "显式调用 $pt-{command} 时使用 Playbook Testing 的 {command} 工作流。"
---

<!-- playbook-testing managed shortcut v1 -->

Run the installed `$playbook-testing {command}` workflow for the current repository.
Forward the user's remaining arguments and constraints to that command.
Load the installed playbook-testing skill and only its relevant command reference.
If the core skill is unavailable, report that Playbook Testing must be installed;
do not invent a passing result or download and execute a replacement.
'''


def shortcuts(repo, commands, remove=False):
    repo = repo.resolve()
    paths = []
    for command in dict.fromkeys(commands):
        if command not in COMMANDS:
            raise quality.QualityError(f"Unknown shortcut: {command}")
        path = repo / ".agents" / "skills" / ("pt-" + command) / "SKILL.md"
        current = repo
        for part in path.relative_to(repo).parts:
            current = current / part
            if current.is_symlink() or not current.resolve().is_relative_to(repo):
                raise quality.QualityError(f"Linked shortcut path preserved: {current}")
        if path.exists() and path.read_text(encoding="utf-8") != shortcut_text(command):
            raise quality.QualityError(f"Existing or edited shortcut preserved: {path}")
        paths.append((path, command))
    # Preflight every requested shortcut before changing any file.
    for path, command in paths:
        if remove:
            if path.exists():
                path.unlink()
                if not any(path.parent.iterdir()):
                    path.parent.rmdir()
        elif not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(shortcut_text(command), encoding="utf-8", newline="\n")
    return {"shortcuts": ["$pt-" + command for _, command in paths],
            "action": "unpinned" if remove else "pinned", "scope": "project",
            "discovery": "Start a new Codex session if the skill list has not refreshed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("commands")
    for name in ("check", "doctor", "hooks", "pin", "unpin"):
        command = subparsers.add_parser(name)
        command.add_argument("--repo", default=".")
        if name == "check":
            command.add_argument("--stage", choices=quality.STAGES, default="task-finish")
        elif name == "hooks":
            command.add_argument("action", choices=("on", "off", "status"), default="status", nargs="?")
        elif name in ("pin", "unpin"):
            command.add_argument("names", choices=tuple(COMMANDS), nargs="+")
    args = parser.parse_args()
    try:
        if args.command in (None, "commands"):
            result = {"skill": "$playbook-testing <command>", "commands": COMMANDS,
                      "shortcuts": "$playbook-testing pin check doctor (project scope)"}
        else:
            repo = quality.repository(args.repo)
            if args.command == "check":
                result = quality.run(repo, args.stage)
            elif args.command == "doctor":
                result = doctor(repo)
            elif args.command == "hooks":
                result = hooks(repo, args.action)
            else:
                result = shortcuts(repo, args.names, remove=args.command == "unpin")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("issues") or result.get("status") in ("failed", "error") else 0
    except (quality.QualityError, OSError, ValueError) as exc:
        print(f"playbook-testing: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
