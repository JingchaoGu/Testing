#!/usr/bin/env python3
"""Copy a self-contained runner and optional CI template into a chosen repository."""
import argparse
from pathlib import Path
import sys

import quality


def prepare_repository(path, init_git=False):
    target = Path(path).resolve()
    if not target.is_dir():
        raise quality.QualityError("Choose an existing project directory before setup")
    try:
        repo = quality.repository(target)
    except quality.QualityError as exc:
        if not init_git:
            raise quality.QualityError("Not a Git worktree. For a new project, choose its stack and purpose, then use --init-git") from exc
        metadata = target / ".git"
        if metadata.exists() or metadata.is_symlink():
            raise quality.QualityError("Existing Git metadata cannot be resolved; inspect it before initializing") from exc
        try:
            quality.git(target, "rev-parse", "--git-dir")
        except quality.QualityError:
            pass
        else:
            raise quality.QualityError("Target is existing Git metadata, not a project worktree; choose a project directory") from exc
        quality.git(target, "init", "--quiet")
        repo = quality.repository(target)
    if init_git and repo != target:
        raise quality.QualityError("Target belongs to a parent Git repository; use its root or choose a directory outside it")
    return repo


def setup(repo, github=False):
    plugin = quality.PLUGIN
    copies = {
        repo / ".testing-tools/quality.py": plugin / "scripts/quality.py",
        repo / ".testing-tools/unittest_junit.py": plugin / "scripts/unittest_junit.py",
        repo / ".testing-tools/install_git_hooks.py": plugin / "scripts/install_git_hooks.py",
        repo / ".testing-tools/testing.py": plugin / "scripts/testing.py",
        repo / ".testing-tools/delivery_hook.py": plugin / "scripts/delivery_hook.py",
    }
    if not (repo / quality.POLICY).exists():
        copies[repo / quality.POLICY] = plugin / "templates/testing-policy.json"
    if github:
        copies[repo / ".github/workflows/playbook-quality.yml"] = plugin / "templates/ci/github-quality.yml"
        copies[repo / ".github/workflows/playbook-delivery.yml"] = plugin / "templates/ci/release-gate.yml"
    for destination, source in copies.items():
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise quality.QualityError(f"Existing file preserved: {destination}. Review an upgrade manually")
    for destination, source in copies.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    ignore = repo / ".gitignore"
    content = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    missing = [entry for entry in (".testing-results/", "__pycache__/") if entry not in content.splitlines()]
    if missing:
        ignore.write_text(content.rstrip("\n") + "\n" + "\n".join(missing) + "\n", encoding="utf-8")
    return list(copies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--init-git", action="store_true", help="Initialize Git in this exact directory for an explicitly requested new project")
    parser.add_argument("--github-workflow", action="store_true", help="Add PR/merge-queue and reusable deployed/release/production workflows")
    args = parser.parse_args()
    try:
        for destination in setup(prepare_repository(args.repo, args.init_git), args.github_workflow):
            print(destination)
        print("Testing scaffold copied. Map and run real checks before declaring init complete or enabling hooks/CI.")
        return 0
    except (quality.QualityError, OSError) as exc:
        print(f"playbook-testing: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
