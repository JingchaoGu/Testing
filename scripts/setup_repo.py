#!/usr/bin/env python3
"""Copy a self-contained runner and optional CI template into a chosen repository."""
import argparse
from pathlib import Path
import sys

import quality


def setup(repo, github=False):
    plugin = quality.PLUGIN
    copies = {
        repo / ".testing-tools/quality.py": plugin / "scripts/quality.py",
        repo / ".testing-tools/unittest_junit.py": plugin / "scripts/unittest_junit.py",
        repo / ".testing-tools/install_git_hooks.py": plugin / "scripts/install_git_hooks.py",
    }
    if not (repo / quality.POLICY).exists():
        copies[repo / quality.POLICY] = plugin / "templates/testing-policy.json"
    if github:
        copies[repo / ".github/workflows/playbook-quality.yml"] = plugin / "templates/ci/github-quality.yml"
    for destination, source in copies.items():
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise quality.QualityError(f"Existing file preserved: {destination}. Review an upgrade manually")
    for destination, source in copies.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    ignore = repo / ".gitignore"
    content = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    if ".testing-results/" not in content.splitlines():
        ignore.write_text(content.rstrip("\n") + "\n.testing-results/\n", encoding="utf-8")
    return list(copies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--github-workflow", action="store_true")
    args = parser.parse_args()
    try:
        for destination in setup(quality.repository(args.repo), args.github_workflow):
            print(destination)
        print("Map real check commands in .testing-policy.json before enabling hooks or CI.")
        return 0
    except (quality.QualityError, OSError) as exc:
        print(f"playbook-testing: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
