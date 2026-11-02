#!/usr/bin/env python3
"""Validate an existing deployment candidate from a CD hook; never deploy or publish."""
import argparse
import json
import os
import re
import sys

import quality

PHASES = {"deployed": ("deployed",), "release": ("deployed", "release"), "production": ("production",)}


def run_delivery(repo, stage, environment, artifact, revision=None):
    if stage not in PHASES or not environment.strip() or not artifact.strip():
        raise quality.QualityError("Choose a delivery stage and provide the real environment and immutable artifact ID")
    actual = quality.git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    if revision is not None and (not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", revision) or revision.lower() != actual):
        raise quality.QualityError("Checked-out revision does not match the expected full candidate commit ID")
    if quality.git(repo, "status", "--porcelain"):
        raise quality.QualityError("Delivery validation requires a clean candidate checkout")
    snapshot = quality.fingerprint(repo)
    values = {"TESTING_ENVIRONMENT": environment, "TESTING_ARTIFACT": artifact}
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    result = {"status": "passed", "stage": stage, "revision": actual,
              "environment": environment, "artifact": artifact, "checks": []}
    try:
        for phase in PHASES[stage]:
            record = quality.run(repo, phase)
            verified = (record["status"] == "passed" and record["snapshot"] == snapshot
                and quality.git(repo, "rev-parse", "HEAD") == actual
                and quality.verify(repo, phase, repo / quality.RESULTS / (phase + ".json")))
            result["checks"].append({"stage": phase, "run_id": record["run_id"], "verified": verified})
            if not verified:
                result["status"] = "failed"
                break
        return result
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--stage", choices=tuple(PHASES), required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--revision", help="Full commit ID of the code belonging to the deployed artifact")
    args = parser.parse_args()
    try:
        result = run_delivery(quality.repository(args.repo), args.stage, args.environment, args.artifact, args.revision)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "passed" else 1
    except (quality.QualityError, OSError, ValueError) as exc:
        print(f"playbook-testing: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
