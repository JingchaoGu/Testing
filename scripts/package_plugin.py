#!/usr/bin/env python3
"""Validate local plugin references and build a distributable ZIP, excluding user data."""
import argparse
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def validate(root):
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    extension = manifest["extensions"]["com.openai"]
    compatibility = root / ".codex-plugin/plugin.json"
    if compatibility.exists():
        fallback = json.loads(compatibility.read_text(encoding="utf-8"))
        if any(fallback.get(key) != manifest.get(key) for key in ("name", "version", "description")) or fallback.get("hooks") != extension["hooks"]:
            raise ValueError("Compatibility manifest is out of sync")
    for value in (extension["hooks"], extension["onboardingSkill"]):
        path = (root / value).resolve()
        if not value.startswith("./") or not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Invalid plugin path: {value}")
    hooks = json.loads((root / extension["hooks"]).read_text(encoding="utf-8"))
    if set(hooks["hooks"]) != {"SessionStart", "PostToolUse", "Stop"}:
        raise ValueError("Unexpected hook event inventory")
    for groups in hooks["hooks"].values():
        for group in groups:
            for handler in group["hooks"]:
                for field in ("command", "command_windows"):
                    for target in re.findall(r"\$\{PLUGIN_ROOT\}/([^\"]+)", handler[field]):
                        if not (root / target).is_file():
                            raise ValueError(f"Missing hook script: {target}")
    for document in (root / "skills").rglob("*.md"):
        text = document.read_text(encoding="utf-8-sig")
        if document.name == "SKILL.md" and (not text.startswith("---\n") or "[TODO:" in text):
            raise ValueError(f"Unfinished skill: {document}")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "#")):
                continue
            path = (document.parent / target.split("#")[0]).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                raise ValueError(f"Missing skill resource: {target}")
    return manifest


def package(root, output):
    manifest = validate(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    include = [root / "plugin.json", root / "README.md", root / "install.sh", root / "install.ps1"]
    for folder in ("skills", "hooks", "scripts", "templates", "docs", ".codex-plugin", ".agents"):
        include.extend(path for path in (root / folder).rglob("*") if path.is_file()
                       and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"))
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(include)):
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"Package resource escapes its root: {path}")
            archive.write(path, Path(manifest["name"]) / path.relative_to(root))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/playbook-testing-0.2.0.zip")
    args = parser.parse_args()
    print(package(ROOT, args.output))
