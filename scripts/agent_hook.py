#!/usr/bin/env python3
"""Codex lifecycle adapter. Only runs for explicitly opted-in repositories."""
import hashlib
import json
import os
from pathlib import Path
import sys

import quality


def context(event, message):
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def state_path(repo, event):
    identity = str(repo) + "\0" + str(event.get("session_id", "default"))
    base = Path(os.environ.get("PLUGIN_DATA", repo / quality.RESULTS / "agent"))
    return base / (hashlib.sha256(identity.encode()).hexdigest() + ".json")


def handle(event):
    name = event.get("hook_event_name")
    if name not in ("SessionStart", "PostToolUse", "Stop") or os.environ.get("PLAYBOOK_TESTING_RUNNING"):
        return {}
    try:
        repo = quality.repository(event.get("cwd", "."))
    except quality.QualityError:
        return {}
    if not (repo / quality.POLICY).is_file():
        return (context(name, "Playbook Testing is available. Run $playbook-testing init to plan and build suitable tests by component and delivery stage before enabling hooks.")
                if name == "SessionStart" else {})
    try:
        policy = quality.load_policy(repo)
        if policy.get("agent_hooks") is not True:
            return {}
        snapshot = quality.fingerprint(repo)
        path = state_path(repo, event)
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        if name == "SessionStart":
            # Resume/compaction should not lose outstanding work or a failed check.
            if not state:
                state = {"baseline": snapshot, "last_seen": snapshot, "continuations": 0}
                quality.write_json(path, state)
            return context(name, "Playbook Testing is enabled. Read TESTING.md or the project's existing test plan; map changed components and acceptance criteria to suitable tests, and update tests/stages when risks or boundaries change. Use $playbook-testing plan for gaps. edit gives feedback; task-finish verifies local completion. Preserve failing evidence and add regression coverage for fixes; report outstanding CI/release conditions separately.")
        if name == "PostToolUse":
            if snapshot == state.get("last_seen"):
                return {}
            state.setdefault("baseline", None)
            state["last_seen"] = snapshot
            # Save before running, so failures/timeouts do not trigger on read-only polls.
            quality.write_json(path, state)
            record = quality.run(repo, "edit")
            return context(name, f"edit: {record['status']}; evidence: {repo / quality.RESULTS / 'edit.json'}. A TDD Red state may continue; fix before completion.")
        if snapshot == state.get("baseline"):
            return {}
        if not state and not quality.git(repo, "status", "--porcelain"):
            return {}
        record = quality.run(repo, "task-finish")
        if record["status"] == "passed":
            state.update(baseline=snapshot, last_seen=snapshot, continuations=0)
            quality.write_json(path, state)
            return {}
        attempts = state.get("continuations", 0) if event.get("stop_hook_active") else 0
        state["continuations"] = attempts + 1
        quality.write_json(path, state)
        message = f"task-finish failed. Inspect {repo / quality.RESULTS / 'task-finish.json'}, repair the cause, then rerun. Do not delete tests or weaken assertions."
        if attempts >= 1:
            return {"systemMessage": message + " Automatic continuation limit reached; report verification as incomplete."}
        return {"decision": "block", "reason": message}
    except (quality.QualityError, OSError, ValueError) as exc:
        message = f"Playbook Testing could not verify this stage: {exc}. This is not a passing result."
        # A broken/missing environment must not create an unbounded Stop loop.
        if name == "Stop" and not event.get("stop_hook_active"):
            return {"decision": "block", "reason": message + " Resolve the environment or explain the blocker."}
        return {"systemMessage": message}


def main():
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError("Hook input must be a JSON object")
        output = handle(event)
    except (ValueError, TypeError) as exc:
        output = {"systemMessage": f"Playbook Testing hook input error: {exc}"}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
