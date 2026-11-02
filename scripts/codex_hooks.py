"""Read Codex's hook registry. Never changes hook trust, config, or project files."""
import json
import queue
import shutil
import subprocess
import threading
import time

PLUGIN_ID = "playbook-testing@testing-playbook"
EXPECTED_EVENTS = {"sessionStart", "postToolUse", "stop"}


def summarize(payload):
    if "error" in payload:
        raise ValueError(payload["error"].get("message", "hooks/list failed"))
    entries = payload["result"]["data"]
    hooks = [hook for entry in entries for hook in entry.get("hooks", []) if hook.get("pluginId") == PLUGIN_ID]
    errors = [error for entry in entries for error in entry.get("errors", []) if "playbook-testing" in error.get("path", "")]
    events = {hook["eventName"] for hook in hooks}
    if errors:
        status = "invalid"
    elif not EXPECTED_EVENTS.issubset(events):
        status = "not-discovered"
    elif any(not hook["enabled"] for hook in hooks):
        status = "disabled"
    elif any(hook["trustStatus"] not in ("trusted", "managed") for hook in hooks):
        status = "review-required"
    else:
        status = "trusted"
    return {"status": status, "hooks": [{key: hook.get(key) for key in
        ("key", "eventName", "enabled", "trustStatus", "sourcePath", "command")} for hook in hooks], "errors": errors}


def inspect(repo, executable=None):
    executable = executable or shutil.which("codex")
    if not executable:
        return {"status": "unknown", "reason": "Codex CLI is unavailable; inspect /hooks in the current host"}
    process = None
    reader = None
    version = ""
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
        process = subprocess.Popen([executable, "app-server", "--stdio"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        messages = queue.Queue()

        def read():
            for line in process.stdout:
                try:
                    messages.put(json.loads(line))
                except ValueError:
                    pass
            messages.put(None)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()

        def request(identity, method, params):
            process.stdin.write(json.dumps({"id": identity, "method": method, "params": params}) + "\n")
            process.stdin.flush()
            deadline = time.monotonic() + 10
            while True:
                item = messages.get(timeout=max(0.01, deadline - time.monotonic()))
                if item is None:
                    raise ValueError("Codex app-server exited before hooks/list completed")
                if item.get("id") == identity:
                    if "error" in item:
                        raise ValueError(item["error"].get("message", "Codex request failed"))
                    return item
                if time.monotonic() >= deadline:
                    raise queue.Empty

        request(1, "initialize", {"clientInfo": {"name": "playbook-testing", "version": "0.6.0"},
            "capabilities": {"experimentalApi": True}})
        process.stdin.write('{"method":"initialized"}\n')
        process.stdin.flush()
        result = summarize(request(2, "hooks/list", {"cwds": [str(repo)]}))
        result.update(executable=str(executable), version=version)
        if result["status"] == "review-required":
            result["next_step"] = "In the same Codex host, open /hooks and review Playbook Testing. Then rerun hooks status. No trust was changed."
        elif result["status"] == "not-discovered":
            result["next_step"] = "Reload the plugin/session and inspect /hooks; confirm this CLI matches the active host version."
        return result
    except (OSError, ValueError, KeyError, TypeError, queue.Empty, subprocess.TimeoutExpired) as exc:
        return {"status": "unknown", "executable": str(executable), "version": version,
                "reason": str(exc) or "Codex hook inspection timed out"}
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if reader:
                reader.join(timeout=1)
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()
