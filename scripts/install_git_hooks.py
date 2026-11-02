#!/usr/bin/env python3
"""Install repository-local wrappers; refuse to overwrite unrelated hooks."""
import argparse
from pathlib import Path
import shlex
import sys

import quality

MARKER = "# playbook-testing generated hook v1"


def install(repo, events):
    quality.load_policy(repo)
    custom = quality.git(repo, "config", "--get-regexp", "^core\\.hooksPath$") if has_custom_hooks_path(repo) else ""
    if custom:
        raise quality.QualityError("core.hooksPath is already configured; chain the quality.py git-hook command in that manager instead")
    hooks = Path(quality.git(repo, "rev-parse", "--git-path", "hooks"))
    if not hooks.is_absolute():
        hooks = repo / hooks
    hooks = hooks.resolve()
    for event in events:
        stage = "commit" if event == "pre-commit" else "push"
        if not quality.load_policy(repo)["stages"].get(stage):
            raise quality.QualityError(f"Configure a nonempty {stage} stage before installing")
        path = hooks / event
        if path.exists() and MARKER not in path.read_text(encoding="utf-8", errors="replace"):
            raise quality.QualityError(f"Existing {event} preserved. Manually chain the quality.py git-hook command")
    hooks.mkdir(parents=True, exist_ok=True)
    python = shlex.quote(sys.executable.replace("\\", "/"))
    runner = shlex.quote(str(Path(__file__).resolve().with_name("quality.py")).replace("\\", "/"))
    for event in events:
        path = hooks / event
        path.write_text(f"#!/bin/sh\n{MARKER}\nexec {python} {runner} git-hook {event}\n", encoding="utf-8", newline="\n")
        path.chmod(0o755)
    return hooks


def has_custom_hooks_path(repo):
    import subprocess
    return subprocess.run(["git", "-C", str(repo), "config", "--get", "core.hooksPath"],
                          capture_output=True).returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--events", nargs="+", choices=("pre-commit", "pre-push"),
                        default=["pre-commit", "pre-push"])
    args = parser.parse_args()
    try:
        print(install(quality.repository(args.repo), args.events))
        return 0
    except (quality.QualityError, OSError) as exc:
        print(f"playbook-testing: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
