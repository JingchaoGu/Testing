#!/usr/bin/env python3
"""Register the Playbook marketplace and install the plugin when the CLI supports it."""
import shutil
import subprocess
import sys

SOURCE = "JingchaoGu/Testing"
PLUGIN = "playbook-testing@testing-playbook"


def main():
    if sys.version_info < (3, 10):
        print("Python 3.10+ is required.", file=sys.stderr)
        return 1
    if not shutil.which("git"):
        print("Git is required. Install Git before running this installer.", file=sys.stderr)
        return 1
    codex = shutil.which("codex")
    if not codex:
        print("Codex CLI is not on PATH. Install or expose the CLI first.", file=sys.stderr)
        return 1
    try:
        registered = subprocess.run([codex, "plugin", "marketplace", "add", SOURCE, "--ref", "main"])
        if registered.returncode:
            print("Marketplace registration failed. Check repository access and the Codex CLI version.", file=sys.stderr)
            return registered.returncode
        supported = subprocess.run([codex, "plugin", "add", "--help"], capture_output=True)
        if supported.returncode:
            print("Marketplace registered; this CLI cannot install plugins directly.")
            print("Open the desktop Plugins Directory, select Testing Playbook, and install Playbook Testing.")
        else:
            installed = subprocess.run([codex, "plugin", "add", PLUGIN])
            if installed.returncode:
                print("Marketplace registered, but plugin installation failed; it is not installed.", file=sys.stderr)
                return installed.returncode
            print("Playbook Testing installed.")
        print("Start a new Codex chat, run the plugin setup for your project, then review and trust hooks with /hooks.")
        return 0
    except OSError as exc:
        print(f"Could not execute Codex CLI: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
