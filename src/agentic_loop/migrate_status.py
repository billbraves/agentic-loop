#!/usr/bin/env python3
"""agentic migrate-status — convert a legacy in-repo WP status to v2.

The pre-portable in-repo workflow (``docs/wp/*.brief.md`` +
``.wp/WP-<id>.status.json``, states ``DISPATCHED/IMPLEMENTING/DONE/BLOCKED``)
predates the portable ``agentic-wp-status/v1..v3`` schema. This converts the
machine-readable status file into a valid v2 status, preserving every mechanical
field and flagging what a human must supply to reach a merge state
(``review``/``consult``/``evidence``).

Best-effort by design: the legacy status carries no review/consult/evidence
blocks, so a terminal ``DONE`` maps to ``READY_FOR_REVIEW`` (implementation done,
review pending) unless ``--merged-commit`` is given, which maps it to ``MERGED``.
Dropped legacy fields (``title``/``brief``/``concerns``/``blocker``) are reported
as warnings, never silently discarded.

Pure stdlib; no network, no git mutation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

V2 = "agentic-wp-status/v2"

# legacy state -> v2 state. Terminal DONE is handled specially (READY_FOR_REVIEW
# by default, MERGED when --merged-commit is supplied).
_LEGACY_STATE_MAP = {
    "DISPATCHED": "DISPATCHED",
    "IMPLEMENTING": "IMPLEMENTING",
    "DONE": "READY_FOR_REVIEW",
    "BLOCKED": "BLOCKED",
}

# legacy risk keys map 1:1 onto the v2 risk block.
_RISK_KEYS = ("production_writes", "network", "notifications", "data_access")


def migrate(
    old: dict,
    *,
    iteration_id: str,
    phase: str = "P1",
    merged_commit: str | None = None,
    base_branch: str = "main",
) -> tuple[dict, list[str]]:
    """Return ``(new_v2_status, warnings)`` for a parsed legacy status dict."""
    warnings: list[str] = []

    wp_id = old.get("wp_id", "")
    state = old.get("state", "")
    if state not in _LEGACY_STATE_MAP:
        raise ValueError(
            "legacy status has unknown state {!r} (expected DISPATCHED/"
            "IMPLEMENTING/DONE/BLOCKED)".format(state)
        )

    new_state = _LEGACY_STATE_MAP[state]
    if state == "DONE" and merged_commit:
        new_state = "MERGED"

    for key in ("title", "brief", "concerns", "blocker"):
        if key in old and old.get(key) not in (None, "", []):
            warnings.append(
                "legacy field {!r} has no v2 equivalent; dropped (value: {!r})".format(
                    key, old.get(key)
                )
            )

    git = dict(old.get("git") or {})
    git.setdefault("base_branch", base_branch)
    if new_state == "MERGED":
        git["merged_commit"] = merged_commit
        if not git.get("commit"):
            warnings.append("MERGED requires git.commit; legacy status left it empty")

    executor = dict(old.get("executor") or {})
    orchestrator = dict(old.get("orchestrator") or {})
    reviewer = dict(old.get("reviewer") or {})

    new: dict = {
        "schema_version": V2,
        "work_package_id": wp_id,
        "iteration_id": iteration_id,
        "phase": phase,
        "state": new_state,
        "role": "Developer",
        "executor": executor,
        "orchestrator": orchestrator,
        "reviewer": reviewer,
        "git": git,
        "scope": {
            "allowed_paths": list(old.get("scope", {}).get("allowed_paths") or []),
            "forbidden_paths": list(old.get("scope", {}).get("forbidden_paths") or []),
        },
        "risk": {
            key: old.get("risk", {}).get(key)
            for key in _RISK_KEYS
        },
        "evidence": {"tests": []},
        "review": {},
        "consult": {},
        "timestamps": {
            "dispatched_at": (old.get("timestamps") or {}).get("dispatched_at", ""),
        },
    }

    if new_state in ("READY_FOR_REVIEW", "APPROVED_FOR_MERGE", "MERGED", "RELEASED"):
        warnings.append(
            "state={} requires review.decision=ACCEPT, consult.decision=ACCEPT and "
            "evidence.tests (non-empty) before it passes the merge gate; the "
            "converted status leaves these empty — fill them before running "
            "`agentic finalize`".format(new_state)
        )

    return new, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agentic migrate-status")
    ap.add_argument("status_file", type=Path, help="legacy .wp/WP-<id>.status.json")
    ap.add_argument("--iteration", required=True, help="iteration_id for the v2 status")
    ap.add_argument("--phase", default="P1", help="phase for the v2 status (default P1)")
    ap.add_argument("--merged-commit", default=None, help="stamp MERGED + merged_commit for DONE")
    ap.add_argument("--base-branch", default="main", help="git.base_branch (default main)")
    ap.add_argument("--out", type=Path, default=None, help="write v2 status here (default stdout)")
    args = ap.parse_args(argv)

    try:
        old = json.loads(args.status_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("migrate-status: not found: {}".format(args.status_file), file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print("migrate-status: invalid JSON: {}".format(exc), file=sys.stderr)
        return 2

    try:
        new, warnings = migrate(
            old,
            iteration_id=args.iteration,
            phase=args.phase,
            merged_commit=args.merged_commit,
            base_branch=args.base_branch,
        )
    except ValueError as exc:
        print("migrate-status: {}".format(exc), file=sys.stderr)
        return 2

    for w in warnings:
        print("migrate-status: WARN {}".format(w), file=sys.stderr)

    text = json.dumps(new, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print("migrate-status: wrote {}".format(args.out))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
