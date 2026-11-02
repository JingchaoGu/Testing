#!/usr/bin/env python3
"""Stage-based checks and snapshot-bound evidence. Python 3.10+, stdlib only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

POLICY = ".testing-policy.json"
RESULTS = ".testing-results"
STAGES = ("edit", "task-finish", "commit", "push", "pr", "deployed", "release", "production")
PLUGIN = Path(__file__).resolve().parent.parent


class QualityError(Exception):
    pass


def git(repo, *args, binary=False):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if result.returncode:
        raise QualityError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout if binary else result.stdout.decode("utf-8", "replace").strip()


def repository(path):
    return Path(git(Path(path).resolve(), "rev-parse", "--show-toplevel")).resolve()


def load_policy(repo):
    try:
        policy = json.loads((repo / POLICY).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise QualityError(f"Cannot read {POLICY}: {exc}") from exc
    if not isinstance(policy, dict) or type(policy.get("version")) is not int or policy["version"] != 1:
        raise QualityError("Policy version must be 1")
    checks, stages = policy.get("checks"), policy.get("stages")
    if not isinstance(checks, dict) or not isinstance(stages, dict):
        raise QualityError("Policy needs checks and stages objects")
    for name, check in checks.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name) or not isinstance(check, dict):
            raise QualityError("Invalid check definition")
        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
            raise QualityError(f"{name}: argv must be a nonempty string array")
        if check.get("kind") not in ("command", "test"):
            raise QualityError(f"{name}: kind must be command or test")
        timeout = check.get("timeout", 60)
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not 0 < timeout <= 3600:
            raise QualityError(f"{name}: timeout must be in (0, 3600]")
        if check["kind"] == "test":
            if not any("{report}" in arg for arg in argv):
                raise QualityError(f"{name}: test argv must write JUnit XML to {{report}}")
            minimum = check.get("min_executed", 1)
            if type(minimum) is not int or minimum < 1:
                raise QualityError(f"{name}: min_executed must be a positive integer")
    for name, selected in stages.items():
        if name not in STAGES or not isinstance(selected, list) or any(not isinstance(x, str) or x not in checks for x in selected):
            raise QualityError(f"Invalid stage: {name}")
        if len(set(selected)) != len(selected):
            raise QualityError(f"Duplicate checks in {name}")
    return policy


def fingerprint(repo):
    # Include tracked and nonignored untracked inputs, not only HEAD or diff names.
    entries = git(repo, "ls-files", "--stage", "-z", binary=True).split(b"\0")
    if any(entry.startswith(b"160000 ") for entry in entries):
        raise QualityError("Submodules need project-specific snapshot support")
    names = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z", binary=True)
    digest = hashlib.sha256()
    for raw in sorted((set(names.split(b"\0")) | {POLICY.encode()}) - {b""}):
        relative = os.fsdecode(raw)
        if relative.split("/")[0] == RESULTS:
            continue
        path = repo / relative
        digest.update(raw + b"\0")
        if path.is_symlink():
            raise QualityError(f"Symlink input needs project-specific snapshot support: {relative}")
        elif path.is_file():
            digest.update(b"file:" + str(path.stat().st_mode & 0o111).encode())
            data = path.read_bytes()
            if data.partition(b"\n")[0].rstrip(b"\r") == b"version https://git-lfs.github.com/spec/v1":
                raise QualityError(f"Unexpanded Git LFS pointer: {relative}")
            digest.update(hashlib.sha256(data).digest())
        elif not path.exists():
            digest.update(b"deleted")
        else:
            raise QualityError(f"Unsupported input: {relative}")
        digest.update(b"\0")
    return digest.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def runtime_id():
    return hashlib.sha256(Path(__file__).read_bytes() + sys.version.encode()).hexdigest()


@contextmanager
def execution_lock(repo):
    directory = repo / RESULTS
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / "run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise QualityError(f"Another check is running, or an interrupted run left {lock}; verify before removing it") from exc
    os.write(descriptor, str(os.getpid()).encode())
    os.close(descriptor)
    try:
        yield
    finally:
        lock.unlink()


def parse_junit(path):
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise QualityError(f"Missing or invalid JUnit report: {exc}") from exc
    cases = [node for node in root.iter() if node.tag.split("}")[-1] == "testcase"]
    counts = {"collected": len(cases), "executed": 0, "failed": 0, "skipped": 0}
    for case in cases:
        tags = {node.tag.split("}")[-1] for node in case}
        counts["skipped"] += "skipped" in tags
        counts["executed"] += "skipped" not in tags
        counts["failed"] += bool(tags & {"failure", "error"})
    # Some tools report suite-level discovery/setup errors without a testcase.
    for node in root.iter():
        if node.tag.split("}")[-1] in ("testsuite", "testsuites"):
            try:
                if int(node.get("failures", "0")) + int(node.get("errors", "0")) > 0:
                    counts["failed"] = max(counts["failed"], 1)
            except ValueError as exc:
                raise QualityError("Invalid JUnit summary counts") from exc
    return counts


def check_command(repo, check, report):
    substitutions = {"{python}": sys.executable, "{repo}": str(repo),
                     "{plugin}": str(PLUGIN), "{report}": str(report)}
    argv = list(check["argv"])
    for token, replacement in substitutions.items():
        argv = [argument.replace(token, replacement) for argument in argv]
    return argv


def run_check(repo, name, check, directory):
    report = directory / f"{name}.xml"
    argv = check_command(repo, check, report)
    record = {"check_id": name, "kind": check["kind"], "argv": argv,
              "cwd": str(repo), "status": "error", "exit_code": None}
    started = time.monotonic()
    environment = dict(os.environ, PLAYBOOK_TESTING_RUNNING="1", PYTHONUTF8="1")
    try:
        # shell=False avoids turning policy arguments into shell source.
        with (directory / f"{name}.log").open("wb") as log:
            process = subprocess.Popen(argv, cwd=repo, env=environment, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=os.name != "nt")
            try:
                process.wait(timeout=check.get("timeout", 60))
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                else:
                    import signal
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                record.update(status="timed_out", reason="Check exceeded its timeout")
                return record
        record["exit_code"] = process.returncode
        record["status"] = "passed" if process.returncode == 0 else "failed"
        if check["kind"] == "test":
            record["counts"] = parse_junit(report)
            record["report"] = str(report)
            if record["counts"]["failed"] or record["counts"]["executed"] < check.get("min_executed", 1):
                record.update(status="failed", reason="Tests failed or too few tests actually executed")
    except (OSError, QualityError) as exc:
        record.update(status="error", reason=str(exc))
    finally:
        record["duration_seconds"] = round(time.monotonic() - started, 3)
        record["log"] = str(directory / f"{name}.log")
    return record


def run_stage(repo, stage, output_repo=None, revision=None):
    output_repo = output_repo or repo
    policy = load_policy(repo)
    selected = policy["stages"].get(stage)
    if not selected:
        raise QualityError(f"Stage {stage} has no required checks; configure it before running")
    if stage in ("deployed", "release", "production"):
        if "smoke" not in selected or selected[0] != "smoke":
            raise QualityError(f"{stage} must begin with a check named smoke")
        if not os.environ.get("TESTING_ENVIRONMENT") or not os.environ.get("TESTING_ARTIFACT"):
            raise QualityError("Deployment checks require TESTING_ENVIRONMENT and TESTING_ARTIFACT")
    with execution_lock(output_repo):
        before = fingerprint(repo)
        run_id = uuid.uuid4().hex
        directory = output_repo / RESULTS / "runs" / run_id
        directory.mkdir(parents=True)
        record = {"version": 1, "run_id": run_id, "stage": stage,
                  "snapshot": before, "revision": revision,
                  "runtime": runtime_id(), "status": "pending",
                  "started_at": datetime.now(timezone.utc).isoformat(),
                  "environment": os.environ.get("TESTING_ENVIRONMENT"),
                  "artifact": os.environ.get("TESTING_ARTIFACT"), "checks": []}
        write_json(output_repo / RESULTS / f"{stage}.json", record)
        for name in selected:
            result = run_check(repo, name, policy["checks"][name], directory)
            record["checks"].append(result)
            if result["status"] != "passed":
                break
        record["snapshot_after"] = fingerprint(repo)
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        record["status"] = "passed" if (len(record["checks"]) == len(selected)
            and all(item["status"] == "passed" for item in record["checks"])
            and before == record["snapshot_after"]) else "failed"
        if before != record["snapshot_after"]:
            record["reason"] = "Inputs changed during verification; rerun on stable inputs"
        write_json(directory / "evidence.json", record)
        write_json(output_repo / RESULTS / f"{stage}.json", record)
        return record


@contextmanager
def exported_snapshot(repo, treeish):
    # git archive does not include gitlinks. Refuse rather than silently omit them.
    if any(line.startswith(b"160000 ") for line in git(repo, "ls-tree", "-r", treeish, "-z", binary=True).split(b"\0")):
        raise QualityError("Submodule snapshots are not supported")
    archive = git(repo, "archive", "--format=tar", treeish, binary=True)
    with tempfile.TemporaryDirectory(prefix="playbook-snapshot-") as temporary:
        target = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            for member in bundle:
                destination = (target / member.name).resolve()
                if not destination.is_relative_to(target) or member.issym() or member.islnk():
                    raise QualityError("Snapshot paths/links require project-specific support")
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(bundle.extractfile(member).read())
                    destination.chmod(member.mode)
                else:
                    raise QualityError("Unsupported snapshot entry")
        # Hooks can export an absolute GIT_INDEX_FILE/GIT_DIR. Never let a
        # foreign snapshot's `git add` update the user's real index.
        variables = git(repo, "rev-parse", "--local-env-vars").splitlines()
        saved = {key: os.environ.pop(key) for key in variables if key in os.environ}
        try:
            git(target, "init", "--quiet")
            git(target, "add", "--all", "--force")
            yield target
        finally:
            os.environ.update(saved)


def run_snapshot(repo, stage, treeish):
    with exported_snapshot(repo, treeish) as snapshot:
        return run_stage(snapshot, stage, output_repo=repo, revision=treeish)


def run(repo, stage):
    if stage == "commit":
        return run_snapshot(repo, stage, git(repo, "write-tree"))
    if stage == "push":
        raise QualityError("Use git-hook pre-push with Git's ref input, or run other stages explicitly")
    return run_stage(repo, stage)


def pre_push(repo, lines):
    results, seen = [], set()
    for line in lines.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise QualityError("Invalid pre-push ref input")
        local_ref, local_sha, remote_ref, remote_sha = fields
        if not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", local_sha):
            raise QualityError("Invalid candidate object id")
        if set(local_sha) == {"0"}:
            continue  # Deletion has no candidate code to test.
        commit = git(repo, "rev-parse", "--verify", local_sha + "^{commit}")
        if commit not in seen:
            results.append(run_snapshot(repo, "push", commit))
            seen.add(commit)
    return results


def verify(repo, stage, evidence_path):
    try:
        record = json.loads(evidence_path.read_text(encoding="utf-8"))
        policy = load_policy(repo)
        selected = policy["stages"].get(stage, [])
        if not selected or record["stage"] != stage or record["status"] != "passed":
            return False
        if record.get("runtime") != runtime_id():
            return False
        if record["snapshot"] != record["snapshot_after"] or record["snapshot"] != fingerprint(repo):
            return False
        if [item["check_id"] for item in record["checks"]] != selected:
            return False
        for item in record["checks"]:
            if item["status"] != "passed" or item["exit_code"] != 0:
                return False
            if policy["checks"][item["check_id"]]["kind"] == "test":
                counts = parse_junit(Path(item["report"]))
                if counts != item["counts"] or counts["failed"] or counts["executed"] < policy["checks"][item["check_id"]].get("min_executed", 1):
                    return False
        if stage in ("deployed", "release", "production"):
            return bool(record.get("artifact") and record.get("environment")
                and record["artifact"] == os.environ.get("TESTING_ARTIFACT")
                and record["environment"] == os.environ.get("TESTING_ENVIRONMENT"))
        return True
    except (OSError, ValueError, KeyError, TypeError, QualityError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("run", "verify", "git-hook"):
        command = subparsers.add_parser(action)
        command.add_argument("--repo", default=".")
        if action == "git-hook":
            command.add_argument("event", choices=("pre-commit", "pre-push"))
        else:
            command.add_argument("--stage", required=True, choices=STAGES)
        if action == "verify":
            command.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        repo = repository(args.repo)
        if args.action == "verify":
            valid = verify(repo, args.stage, args.evidence or repo / RESULTS / f"{args.stage}.json")
            print(json.dumps({"stage": args.stage, "verified": valid}))
            return 0 if valid else 1
        if args.action == "git-hook":
            records = ([run(repo, "commit")] if args.event == "pre-commit"
                       else pre_push(repo, sys.stdin.read()))
        else:
            records = [run(repo, args.stage)]
        for record in records:
            print(json.dumps({"stage": record["stage"], "status": record["status"],
                              "run_id": record["run_id"], "snapshot": record["snapshot"]}))
        return 0 if all(record["status"] == "passed" for record in records) else 1
    except (QualityError, OSError) as exc:
        print(f"playbook-testing: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
