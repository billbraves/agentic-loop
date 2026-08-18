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
# v3 adds the qoder security third signature as a required top-level block.
# v2 stays frozen (no qoder_security required), so this iteration's own v2 WPs
# and historical MERGED v2 statuses remain valid without backfill.
REQUIRED_TOP_LEVEL_V3 = REQUIRED_TOP_LEVEL_V2 | {"qoder_security"}
SCHEMA_VERSIONS = {"agentic-wp-status/v1", "agentic-wp-status/v2", "agentic-wp-status/v3"}
# qoder_security is a legal top-level key in EVERY schema version (optional in
# v1/v2, required in v3 via REQUIRED_TOP_LEVEL_V3). It must never be flagged as
# an unknown extra key; the v3 *presence* requirement is enforced by `required`.
OPTIONAL_TOP_LEVEL = {"qoder_security", "plan_id"}
DECISIONS = {"ACCEPT", "REWORK", "CONSULT"}
# review.decision may additionally be "N/A" ONLY to record the
# implementer-is-reviewer conflict (e.g. Claude implemented because kimi was
# unavailable and therefore cannot be its own independent reviewer). In that
# case independence is carried solely by consult (Codex). Not valid for consult.
REVIEW_DECISIONS = DECISIONS | {"N/A"}
INDEPENDENCE_LEVELS = {"strong", "weak", "none"}

# qoder_security enums mirror the single source of truth in
# agentic_loop/gate/qoder_security.py (DECISIONS / VALID_SEVERITIES /
# ERROR_KINDS). They are copied here rather than imported because importing the
# gate package pulls in adapters/independence/resolve_paths with import-time
# side effects; keep these in sync with qoder_security.py on any change.
QODER_DECISIONS = {"PASS", "FINDINGS", "ERROR"}
QODER_SEVERITIES = {"high", "medium", "low"}
QODER_ERROR_KINDS = {
    "auth_expired",
    "credits_exhausted",
    "network_not_authorized",
    "parse_failed",
    "preflight_failed",
    "timeout",
}

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


def _override_dict_is_legal(override: object) -> bool:
    """Return True when ``override`` is a complete, human-approved override.

    This is the shared four-field override shape used by both the consult and
    qoder_security gates: an active marker (``approved == True``), a non-empty
    ``approver``, a non-empty ``justification``, and a non-empty ``reviewed_at``.
    An absent or incomplete override resolves to ``False`` so both gates stay
    fail-closed.
    """
    if not isinstance(override, dict):
        return False
    if override.get("approved") is not True:
        return False
    approver = override.get("approver")
    if not isinstance(approver, str) or not approver.strip():
        return False
    justification = override.get("justification")
    if not isinstance(justification, str) or not justification.strip():
        return False
    reviewed_at = override.get("reviewed_at")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        return False
    return True


def _override_is_legal(consult: object) -> bool:
    """Return True when ``consult.override`` is a complete, human-approved override.

    A legal override relaxes *only* the terminal-state ``consult.decision ==
    ACCEPT`` gate. Delegates to :func:`_override_dict_is_legal` so the qoder
    override shares the exact same strictness.
    """
    if not isinstance(consult, dict):
        return False
    return _override_dict_is_legal(consult.get("override"))


def _qoder_security_satisfied(qoder: object) -> bool:
    """True when the ``qoder_security`` block does not block the merge.

    Mirrors ``agentic_loop.gate.qoder_security.blocking``: ``PASS`` never blocks;
    ``FINDINGS`` / ``ERROR`` block unless a complete, approved override is
    present. This is the validator-level predicate consumed by the merge-state
    gate below for the v3 third signature (PASS or a complete approved override),
    and by WP-05 (finalize_merge.sh) when advancing state.
    """
    if not isinstance(qoder, dict):
        return False
    if qoder.get("decision") == "PASS":
        return True
    return _override_dict_is_legal(qoder.get("override"))


def _validate_qoder_security(data: dict, errors: list[str]) -> None:
    """Validate the contents of the ``qoder_security`` block, when present.

    Presence is enforced separately: the block is optional in v2 and required in
    v3 via ``REQUIRED_TOP_LEVEL_V3``. This function only checks content legality,
    for every schema version, so a malformed block never slips through.

    Frozen validator scope (WP-04 brief §51): decision enum; a present ``error``
    is always validated as a complete structure (kind in the six ERROR_KINDS +
    non-empty message), and decision=ERROR additionally requires ``error`` to be
    present; findings severities are {high, medium, low}; each finding's
    ``category`` / ``file`` / ``summary`` must be a non-empty string and the
    ``dataflow`` key must be present with a string or null value; block-level ``level``
    must be a non-empty string; and a present ``override`` must be a complete
    four-field override (fail-closed). Engine runtime fields such as ``scope`` /
    ``suppressed`` / ``requested_level`` / ``detail`` /
    ``scanner_reported_level`` are not hard-gated here (present or absent are
    both accepted).
    """
    qoder = data.get("qoder_security")
    if qoder is None:
        return
    if not isinstance(qoder, dict):
        fail(errors, "qoder_security must be an object")
        return

    decision = qoder.get("decision")
    if decision not in QODER_DECISIONS:
        fail(errors, f"qoder_security.decision is invalid: {decision!r}")

    findings = qoder.get("findings")
    if not isinstance(findings, list):
        fail(errors, "qoder_security.findings must be a list")
    else:
        for idx, finding in enumerate(findings):
            if not isinstance(finding, dict):
                fail(errors, f"qoder_security.findings[{idx}] must be an object")
                continue

            severity = finding.get("severity")
            if severity not in QODER_SEVERITIES:
                fail(
                    errors,
                    f"qoder_security.findings[{idx}].severity is invalid: {severity!r}",
                )

            category = finding.get("category")
            if not isinstance(category, str) or not category.strip():
                fail(
                    errors,
                    f"qoder_security.findings[{idx}].category must be a non-empty string",
                )

            file = finding.get("file")
            if not isinstance(file, str) or not file.strip():
                fail(
                    errors,
                    f"qoder_security.findings[{idx}].file must be a non-empty string",
                )

            summary = finding.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                fail(
                    errors,
                    f"qoder_security.findings[{idx}].summary must be a non-empty string",
                )

            if "dataflow" not in finding:
                fail(
                    errors,
                    f"qoder_security.findings[{idx}].dataflow must be a string or null",
                )
            elif finding["dataflow"] is not None and not isinstance(finding["dataflow"], str):
                fail(
                    errors,
                    f"qoder_security.findings[{idx}].dataflow must be a string or null",
                )

    level = qoder.get("level")
    if not isinstance(level, str) or not level.strip():
        fail(errors, "qoder_security.level must be a non-empty string")

    # brief §52: error is a structured field (kind enum + non-empty message),
    # required when decision=ERROR. The structure is validated whenever error is
    # present — not only under ERROR — so a non-ERROR decision cannot smuggle a
    # malformed error past the schema. ERROR additionally requires it to exist.
    error = qoder.get("error")
    if decision == "ERROR" and not isinstance(error, dict):
        fail(errors, "qoder_security.error must be an object when decision=ERROR")
    elif error is not None:
        if not isinstance(error, dict):
            fail(errors, "qoder_security.error must be an object")
        else:
            kind = error.get("kind")
            if kind not in QODER_ERROR_KINDS:
                fail(errors, f"qoder_security.error.kind is invalid: {kind!r}")
            message = error.get("message")
            if not isinstance(message, str) or not message.strip():
                fail(errors, "qoder_security.error.message must be a non-empty string")

    override = qoder.get("override")
    if override is not None and not _override_dict_is_legal(override):
        fail(
            errors,
            "qoder_security.override must be a complete, approved override "
            "(approved=true + approver/justification/reviewed_at non-empty)",
        )


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
    is_v3 = schema_version == "agentic-wp-status/v3"
    if is_v3:
        required = REQUIRED_TOP_LEVEL_V3
    elif is_v2:
        required = REQUIRED_TOP_LEVEL_V2
    else:
        required = REQUIRED_TOP_LEVEL_V1
    allowed = required | OPTIONAL_TOP_LEVEL
    missing = sorted(required - data.keys())
    extra = sorted(data.keys() - allowed)
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

    # Content validation for the qoder_security block runs whenever the block is
    # present (v2 optional, v3 required). The v3 presence requirement itself is
    # enforced above via REQUIRED_TOP_LEVEL_V3.
    _validate_qoder_security(data, errors)

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
        consult = data.get("consult")
        consult_decision = consult.get("decision") if isinstance(consult, dict) else None
        override_ok = _override_is_legal(consult)
        if decision == "N/A":
            # Implementer-is-reviewer degraded path: no independent Claude review,
            # so independence MUST be carried by an ACCEPT from consult (Codex),
            # which is only representable in schema v2. A legal override does NOT
            # relax this path (independence is a separate, non-decision gate).
            if not is_v2:
                fail(errors, f"review.decision=N/A requires schema v2 (consult block) in state {state}")
            elif consult_decision != "ACCEPT":
                fail(errors, f"review.decision=N/A requires consult.decision=ACCEPT in state {state}")
        elif decision != "ACCEPT":
            fail(errors, f"review.decision must be ACCEPT or N/A in state {state}")
        elif is_v2 and consult_decision != "ACCEPT":
            if not override_ok:
                # No valid override: the honest-REWORK terminal gate stays
                # fail-closed, exactly as before this WP.
                fail(errors, f"consult.decision must be ACCEPT in state {state}")
            elif consult_decision not in DECISIONS:
                # A valid override relaxes "must equal ACCEPT" to "must be a
                # present, valid decision"; it does not permit a missing consult.
                fail(errors, f"consult.decision must be ACCEPT, REWORK, or CONSULT in state {state}")
        # v3 third signature: the qoder_security gate must be satisfied
        # (decision == PASS, or a complete approved override) before a v3 status
        # may enter a merge state. v2 has no third signature (double-sign only),
        # so this branch is v3-only. finalize_merge.sh (WP-05) consumes this
        # validator verdict; the fail-closed condition itself lives here.
        if is_v3 and not _qoder_security_satisfied(data.get("qoder_security")):
            fail(
                errors,
                f"qoder_security must be PASS or carry a complete approved "
                f"override in state {state}",
            )
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
