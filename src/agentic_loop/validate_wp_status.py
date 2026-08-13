#!/usr/bin/env python3
"""Validate the repository's machine-readable work-package status contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


STATES = {
    "DRAFT",
    "APPROVED",
    "DISPATCHED",
    "IMPLEMENTING",
    "READY_FOR_REVIEW",
    "CHANGES_REQUESTED",
    "APPROVED_FOR_MERGE",
    "MERGED",
    "RELEASED",
    "BLOCKED",
}
ROLES = {"Developer", "Reviewer", "Consultant", "ReleaseOwner"}
REQUIRED_TOP_LEVEL_V1 = {
    "schema_version",
    "work_package_id",
    "iteration_id",
    "phase",
    "state",
    "role",
    "executor",
    "orchestrator",
    "reviewer",
    "git",
    "scope",
    "risk",
    "evidence",
    "review",
    "timestamps",
}
# v2 adds the independent Codex merge-gate block. See AGENTS.md double-sign rule:
# entering a merge state requires both review.decision and consult.decision ACCEPT.
REQUIRED_TOP_LEVEL_V2 = REQUIRED_TOP_LEVEL_V1 | {"consult"}
SCHEMA_VERSIONS = {"agentic-wp-status/v1", "agentic-wp-status/v2"}
DECISIONS = {"ACCEPT", "REWORK", "CONSULT"}
# review.decision may additionally be "N/A" ONLY to record the
# implementer-is-reviewer conflict (e.g. Claude implemented because kimi was
# unavailable and therefore cannot be its own independent reviewer). In that
# case independence is carried solely by consult (Codex). Not valid for consult.
REVIEW_DECISIONS = DECISIONS | {"N/A"}
INDEPENDENCE_LEVELS = {"strong", "weak", "none"}

# Built-in tool identifiers that are independent of project config.
# Note: these are *tool* identifiers (claude-code/codex-cli/kimi-cli), not
# adapter bare names (claude/codex/kimi). Only "hermes" overlaps with adapter
# names and has been moved to project config in WP-06.
BUILTIN_TOOLS = {"unassigned", "human", "claude-code", "codex-cli", "kimi-cli"}

# Fail-safe fallback set used when the WP-06 resolver is unavailable.
# The WP-07 contract deliberately opts for "do not falsely reject known-good
# tools" over "fail-closed on unknown tools" here: if config cannot be read,
# we must still accept all legacy tool names (including hermes) so the 112
# existing live status files are not wrongly invalidated. See WP-07 brief
# §Behavioral contract and dispatch prompt "命名口径关键约束".
FALLBACK_TOOLS = BUILTIN_TOOLS | {"hermes"}

# Cache for the resolved allowed tool set. The set is computed once per process.
_ALLOWED_TOOLS: set[str] | None = None


def _resolver_path() -> Path:
    return Path(__file__).resolve().parent / "resolve_paths.py"


def _load_allowed_tools() -> set[str]:
    """Return the allowed tool identifiers: built-ins plus config adapters.

    Reads the adapter list from the WP-06 resolver's read-only interface.
    If the resolver is missing, not a git repo, or returns unusable data,
    fall back to FALLBACK_TOOLS so legacy tool names are not mis-rejected.
    """
    global _ALLOWED_TOOLS
    if _ALLOWED_TOOLS is not None:
        return _ALLOWED_TOOLS

    resolver = _resolver_path()
    if not resolver.is_file():
        _ALLOWED_TOOLS = set(FALLBACK_TOOLS)
        return _ALLOWED_TOOLS

    try:
        proc = subprocess.run(
            [sys.executable, str(resolver), "--config-section", "adapters"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            _ALLOWED_TOOLS = set(FALLBACK_TOOLS)
            return _ALLOWED_TOOLS
        section = json.loads(proc.stdout)
        adapter_names = section.get("names", [])
        if not isinstance(adapter_names, (list, tuple)):
            _ALLOWED_TOOLS = set(FALLBACK_TOOLS)
            return _ALLOWED_TOOLS
        # Adapter bare names are allowed as tool identifiers alongside built-ins.
        # This lets config declare project-specific tools like "hermes".
        _ALLOWED_TOOLS = set(BUILTIN_TOOLS) | set(str(name) for name in adapter_names)
        return _ALLOWED_TOOLS
    except Exception:
        _ALLOWED_TOOLS = set(FALLBACK_TOOLS)
        return _ALLOWED_TOOLS


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_status(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"status file does not exist: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno}: {exc.msg}") from None
    if not isinstance(value, dict):
        raise ValueError("status root must be a JSON object")
    return value


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    allowed_tools = _load_allowed_tools()
    schema_version = data.get("schema_version")
    is_v2 = schema_version == "agentic-wp-status/v2"
    required = REQUIRED_TOP_LEVEL_V2 if is_v2 else REQUIRED_TOP_LEVEL_V1
    missing = sorted(required - data.keys())
    extra = sorted(data.keys() - required)
    if missing:
        fail(errors, f"missing top-level fields: {', '.join(missing)}")
    if extra:
        fail(errors, f"unknown top-level fields: {', '.join(extra)}")
    if schema_version not in SCHEMA_VERSIONS:
        fail(errors, f"schema_version must be one of {sorted(SCHEMA_VERSIONS)}")
    if data.get("state") not in STATES:
        fail(errors, f"invalid state: {data.get('state')!r}")
    if data.get("role") not in ROLES:
        fail(errors, f"invalid role: {data.get('role')!r}")

    for name in ("executor", "orchestrator", "reviewer"):
        actor = data.get(name)
        if not isinstance(actor, dict):
            fail(errors, f"{name} must be an object")
            continue
        if actor.get("tool") not in allowed_tools:
            fail(errors, f"{name}.tool is invalid: {actor.get('tool')!r}")

    # Optional nested semantic validation for redispatch_count (WP-C).
    # Absent is allowed; present must be a non-negative integer.
    executor = data.get("executor")
    if isinstance(executor, dict):
        redispatch_count = executor.get("redispatch_count")
        if redispatch_count is not None:
            if (
                isinstance(redispatch_count, bool)
                or not isinstance(redispatch_count, int)
                or redispatch_count < 0
            ):
                fail(errors, "executor.redispatch_count must be a non-negative integer")

    decision_blocks = ["review", "consult"] if is_v2 else ["review"]
    for name in decision_blocks:
        block = data.get(name)
        if not isinstance(block, dict):
            fail(errors, f"{name} must be an object")
            continue
        decision = block.get("decision")
        allowed_decisions = REVIEW_DECISIONS if name == "review" else DECISIONS
        if decision is not None and decision not in allowed_decisions:
            fail(errors, f"{name}.decision is invalid: {decision!r}")
        # consult.independence is optional in v2. If present, it must be one of
        # the engine-rated independence levels. The engine-side enforcement
        # (recompute on missing / fail-closed) is intentionally left to P3.
        if is_v2 and name == "consult":
            independence = block.get("independence")
            if independence is not None and independence not in INDEPENDENCE_LEVELS:
                fail(errors, f"consult.independence is invalid: {independence!r}")

    git = data.get("git")
    if not isinstance(git, dict):
        fail(errors, "git must be an object")
        git = {}
    if not git.get("base_branch"):
        fail(errors, "git.base_branch is required")

    scope = data.get("scope")
    if not isinstance(scope, dict):
        fail(errors, "scope must be an object")
        scope = {}
    allowed = scope.get("allowed_paths")
    forbidden = scope.get("forbidden_paths")
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        fail(errors, "scope.allowed_paths must be a list of strings")
    if not isinstance(forbidden, list) or not all(isinstance(item, str) for item in forbidden):
        fail(errors, "scope.forbidden_paths must be a list of strings")

    state = data.get("state")
    active_states = STATES - {"DRAFT", "APPROVED"}
    if state in active_states:
        if data.get("executor", {}).get("tool") == "unassigned":
            fail(errors, f"executor.tool must be assigned in state {state}")
        for field in ("base_commit", "branch", "worktree"):
            if not git.get(field):
                fail(errors, f"git.{field} is required in state {state}")
        if not allowed:
            fail(errors, f"scope.allowed_paths must not be empty in state {state}")

    if state in {"READY_FOR_REVIEW", "APPROVED_FOR_MERGE", "MERGED", "RELEASED"}:
        if not git.get("commit"):
            fail(errors, f"git.commit is required in state {state}")
        tests = data.get("evidence", {}).get("tests")
        if not isinstance(tests, list) or not tests:
            fail(errors, f"evidence.tests must not be empty in state {state}")
        elif any(not isinstance(item, dict) or item.get("exit_code") is None for item in tests):
            fail(errors, "each evidence.tests entry requires an exit_code")

    if state in {"APPROVED_FOR_MERGE", "MERGED", "RELEASED"}:
        decision = data.get("review", {}).get("decision")
        consult_decision = data.get("consult", {}).get("decision")
        if decision == "N/A":
            # Implementer-is-reviewer degraded path: no independent Claude review,
            # so independence MUST be carried by an ACCEPT from consult (Codex),
            # which is only representable in schema v2.
            if not is_v2:
                fail(errors, f"review.decision=N/A requires schema v2 (consult block) in state {state}")
            elif consult_decision != "ACCEPT":
                fail(errors, f"review.decision=N/A requires consult.decision=ACCEPT in state {state}")
        elif decision != "ACCEPT":
            fail(errors, f"review.decision must be ACCEPT or N/A in state {state}")
        elif is_v2 and consult_decision != "ACCEPT":
            fail(errors, f"consult.decision must be ACCEPT in state {state}")
    if state in {"MERGED", "RELEASED"} and not git.get("merged_commit"):
        fail(errors, f"git.merged_commit is required in state {state}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("status_file", type=Path)
    parser.add_argument("--field", help="Print one dotted field after validation")
    args = parser.parse_args()
    try:
        data = load_status(args.status_file)
    except ValueError as exc:
        print(f"STATUS_INVALID: {exc}", file=sys.stderr)
        return 2
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"STATUS_INVALID: {error}", file=sys.stderr)
        return 2
    if args.field:
        value: object = data
        for part in args.field.split("."):
            if not isinstance(value, dict) or part not in value:
                print(f"STATUS_INVALID: unknown field {args.field}", file=sys.stderr)
                return 2
            value = value[part]
        if isinstance(value, (dict, list)):
            print(json.dumps(value, ensure_ascii=False))
        elif value is None:
            print("")
        else:
            print(value)
    else:
        print("STATUS_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
