#!/usr/bin/env python3
"""Engine-orchestrated independent Codex merge-gate for a work package.

This is the P3 generalization of the formerly bash-welded
``scripts/agentic/codex_merge_gate.sh``. The bash script is now a thin shell
that execs this module. All safety semantics are migrated verbatim:
resolver-driven root resolution, worktree refusal, schema v2 gate,
review.decision ∈ {ACCEPT, N/A}, base/commit/branch validation,
branch-tip diff endpoint with ancestor integrity, brief-introducing-commit
fall-back, effort tiering, and verdict persistence.

New P3 observability:
- ``[review_policy].hard_rules`` is injected into the consultant contract
  (replacing the hard-coded investment rule in the old bash prompt).
- WP-09 independence evaluation is invoked and the rated level is written to
  ``consult.independence``.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

# Make ``adapters/`` and ``independence.py`` importable on the bare python3 path.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.base import Verdict
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.independence import evaluate
from agentic_loop.independence import meets_threshold
from agentic_loop.resolve_paths import get_adapters
from agentic_loop.resolve_paths import get_review_policy
from agentic_loop.resolve_paths import iterations_dir
from agentic_loop.resolve_paths import main_repo


VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "rationale", "findings"],
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["ACCEPT", "REWORK", "CONSULT"],
        },
        "rationale": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
}


class GateError(SystemExit):
    """Raised to emit a GATE_FAIL line and exit with code 2."""

    def __init__(self, message: str) -> None:
        print(f"GATE_FAIL: {message}", file=sys.stderr)
        super().__init__(2)


def gate_log(message: str) -> None:
    print(f"GATE: {message}", file=sys.stderr)


def gate_warn(message: str) -> None:
    print(f"GATE_WARN: {message}", file=sys.stderr)


def run_validator(validator: Path, status_file: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(validator), str(status_file)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        raise GateError(f"validator rejected status: {err}")


def read_field(validator: Path, status_file: Path, dotted: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(validator), str(status_file), "--field", dotted],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        raise GateError(f"validator field read failed for {dotted}: {err}")
    return proc.stdout.strip()


def git_output(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GateError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def git_is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise GateError(
        f"git merge-base --is-ancestor {ancestor} {descendant} failed: "
        f"{proc.stderr.strip()}"
    )


def resolve_gate_effort(iteration_dir: Path, phase: str) -> str:
    """Fail-safe phase tier resolution: only ``architecture`` maps to ``high``."""
    tiers_file = iteration_dir / "phase-tiers.json"
    if not tiers_file.is_file():
        return "medium"
    try:
        cfg = json.loads(tiers_file.read_text(encoding="utf-8"))
    except Exception:
        return "medium"
    if not isinstance(cfg, dict):
        return "medium"

    phases = cfg.get("phases") or {}
    default = cfg.get("default", "routine")
    tier: Any = None
    if isinstance(phases, dict):
        if phase in phases:
            tier = phases[phase]
        else:
            stripped = re.sub(r"[a-z]+$", "", phase)
            if stripped in phases:
                tier = phases[stripped]
    if tier is None:
        tier = default
    return "high" if tier == "architecture" else "medium"


def load_status_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateError(f"invalid JSON in status file: {exc}") from None


def build_notes(verdict: Verdict) -> str:
    notes = verdict.rationale
    if verdict.findings:
        notes = notes + "\n\nFindings:\n" + "\n".join(
            f"- {finding}" for finding in verdict.findings
        )
    return notes


def persist_answer(iteration_dir: Path, wp_id: str, verdict: Verdict) -> Path:
    """Persist the codex answer artifact; ``CodexAdapter.review`` only writes its
    own tempdir, so the gate re-materializes the answer file verbatim here."""
    answer_file = iteration_dir / f"{wp_id}-codex-merge-gate.answer.md"
    answer_file.write_text(
        json.dumps(
            {
                "decision": verdict.decision,
                "rationale": verdict.rationale,
                "findings": list(verdict.findings),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return answer_file


def write_consult_block(
    status_file: Path,
    verdict: Verdict,
    independence_level: str,
    independence_reasons: list[str],
    reviewed_at: str,
) -> None:
    data = load_status_json(status_file)
    consult = data.get("consult", {})
    if not isinstance(consult, dict):
        consult = {}
    notes = build_notes(verdict)
    if independence_reasons:
        notes = (
            notes
            + "\n\nIndependence: "
            + independence_level
            + "\n"
            + "\n".join(f"- {reason}" for reason in independence_reasons)
        )
    consult["decision"] = verdict.decision
    consult["reviewed_by"] = "codex-cli"
    consult["reviewed_at"] = reviewed_at
    consult["notes"] = notes
    consult["independence"] = independence_level
    data["consult"] = consult
    ts = data.get("timestamps")
    if isinstance(ts, dict):
        ts["updated_at"] = reviewed_at
    status_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: gate.py <work-package-status.json>", file=sys.stderr)
        return 64

    status_arg = argv[0]

    repo_root = main_repo()
    iterations_dir_path = iterations_dir()
    # Sibling module inside the agentic_loop package (moved in WP-18).
    validator = Path(__file__).resolve().parent / "validate_wp_status.py"

    # Resolve status path against main repo root, not cwd (which may be a worktree).
    if status_arg.startswith("/"):
        status_file = Path(status_arg)
    else:
        status_file = repo_root / status_arg

    if not status_file.is_file():
        raise GateError(
            f"status file not found at {status_file} "
            f"(resolved against main repo root {repo_root})"
        )

    if "/.worktrees/" in str(status_file):
        raise GateError(
            f"status file resolves inside a worktree ({status_file}); "
            "pass the main-repo copy (single source of truth)"
        )

    gate_log(f"using status file {status_file} (main repo root: {repo_root})")

    run_validator(validator, status_file)

    schema_version = read_field(validator, status_file, "schema_version")
    if schema_version != "agentic-wp-status/v2":
        raise GateError(
            f"codex merge-gate requires schema v2, got {schema_version}"
        )

    review_decision = read_field(validator, status_file, "review.decision")
    if review_decision not in ("ACCEPT", "N/A"):
        raise GateError(
            f"precondition unmet — review.decision is '{review_decision}', "
            "expected ACCEPT or N/A"
        )

    wp_id = read_field(validator, status_file, "work_package_id")
    iteration_id = read_field(validator, status_file, "iteration_id")
    phase = read_field(validator, status_file, "phase")
    base_commit = read_field(validator, status_file, "git.base_commit")
    head_commit = read_field(validator, status_file, "git.commit")
    branch = read_field(validator, status_file, "git.branch")

    if not base_commit or not head_commit:
        raise GateError(
            "git.base_commit and git.commit are required for the diff"
        )

    if not branch:
        raise GateError(
            "git.branch is required to resolve the diff endpoint (branch tip)"
        )

    try:
        tip_commit = git_output(
            repo_root,
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}^{{commit}}",
        )
    except GateError:
        raise GateError(
            f"cannot resolve branch '{branch}' tip from main repo — "
            "is the WP branch present?"
        ) from None

    if not git_is_ancestor(repo_root, head_commit, tip_commit):
        raise GateError(
            f"git.commit ({head_commit}) is not an ancestor of branch tip "
            f"({tip_commit}); status records a commit off the branch"
        )
    if not git_is_ancestor(repo_root, base_commit, tip_commit):
        raise GateError(
            f"git.base_commit ({base_commit}) is not an ancestor of branch tip "
            f"({tip_commit}); diff range is invalid"
        )

    gate_log(
        f"diff endpoint = branch '{branch}' tip {tip_commit} "
        f"(git.commit={head_commit} recorded separately)"
    )

    iteration_dir = iterations_dir_path / iteration_id
    brief_path = iteration_dir / f"{wp_id}-brief.md"
    if brief_path.is_file():
        brief_text = brief_path.read_text(encoding="utf-8")
    else:
        gate_warn(f"brief not found at {brief_path}; proceeding with diff-only review")
        brief_text = ""

    # Diff start: prefer the commit that introduced this WP brief, fail-closed.
    brief_rel = str(Path(iterations_dir_path.relative_to(repo_root)) / iteration_id / f"{wp_id}-brief.md")
    diff_start = ""
    fallback_reason = ""
    brief_in_repo = repo_root / brief_rel
    if not brief_in_repo.is_file():
        fallback_reason = f"brief file missing on disk: {brief_rel}"
    else:
        log_output = git_output(
            repo_root,
            "log",
            "--diff-filter=A",
            "--format=%H",
            f"{base_commit}..{tip_commit}",
            "--",
            brief_rel,
        )
        candidates = log_output.splitlines()
        if candidates:
            diff_start = candidates[-1]
        if not diff_start:
            fallback_reason = (
                f"brief not added in {base_commit}..{tip_commit} "
                "(predates base or no setup commit)"
            )
        elif not (
            git_is_ancestor(repo_root, base_commit, diff_start)
            and git_is_ancestor(repo_root, diff_start, tip_commit)
        ):
            fallback_reason = (
                f"integrity check failed for brief-introducing commit {diff_start}"
            )
            diff_start = ""

    if diff_start:
        gate_log(
            f"diff start moved to brief-introducing commit {diff_start} "
            f"(was base_commit {base_commit})"
        )
    else:
        diff_start = base_commit
        gate_log(f"diff start = base_commit {base_commit} ({fallback_reason})")

    gate_effort = resolve_gate_effort(iteration_dir, phase)
    gate_log(f"phase={phase} → model_reasoning_effort={gate_effort}")

    diff_text = git_output(repo_root, "diff", f"{diff_start}..{tip_commit}")

    # ------------------------------------------------------------------
    # Consultant selection and contract construction (INV-3 / INV-7)
    # ------------------------------------------------------------------
    review_policy = get_review_policy(repo_root)
    hard_rules = review_policy.get("hard_rules", [])
    hard_rules_text = "\n".join(str(rule) for rule in hard_rules) if hard_rules else ""

    adapters_cfg = get_adapters(repo_root)
    adapter_names = adapters_cfg.get("names", [])
    if "codex" not in adapter_names:
        gate_warn(
            "config adapters.names does not list codex; "
            "falling back to built-in codex (fail-closed)"
        )

    contract = ReviewContract(
        role="consultant",
        output_schema=VERDICT_SCHEMA,
        review_policy=hard_rules_text,
    )
    if contract.writes != ("consult",):
        raise GateError("consultant contract attempts to write outside consult block")

    adapter = CodexAdapter()

    # INV-2: require self-attestable level-2 capabilities.
    capabilities = adapter.capabilities()
    if not (capabilities.sandbox_enforced and capabilities.structured_output):
        raise GateError(
            "consultant capabilities not provable: sandbox_enforced or "
            "structured_output false"
        )

    # ------------------------------------------------------------------
    # Independence rating (WP-09) with bootstrap exception (P3-scope-freeze)
    # ------------------------------------------------------------------
    min_independence = review_policy.get("min_independence", "strong")
    consultant_identity = adapter.identity()

    implementer_id: AgentIdentity | None = None
    if review_decision == "N/A":
        executor_tool = read_field(validator, status_file, "executor.tool")
        implementer_id = AgentIdentity(tool=executor_tool or "unassigned")

    level, independence_reasons = evaluate(
        reviewer_id=None,
        consultant_id=consultant_identity,
        capabilities=capabilities,
        min_independence=min_independence,
        implementer_id=implementer_id,
    )

    # Bootstrap exception: one-sign path where the orchestrator (Claude) has no
    # adapter identity. Per P3-scope-freeze we do not downgrade this to ``none``;
    # when WP-09 signals are insufficient we record weak-attested and continue.
    is_bootstrap_normal = review_decision == "ACCEPT" and implementer_id is None
    if is_bootstrap_normal and level == "none" and capabilities.sandbox_enforced:
        level = "weak"
        independence_reasons.append(
            "bootstrap exception: reviewer identity unavailable (orchestrator); "
            "rated weak-attested, attested not engine-proven"
        )

    # 恒计算门限判据(单点可读),不再按分支跳过。
    threshold_met = meets_threshold(level, min_independence)
    if not threshold_met:
        # 唯一允许的放行例外:bootstrap 正常路径 + 已升 weak-attested +
        # capabilities.sandbox_enforced(INV-2 已证)。此例外显式留痕,
        # 绝不放行真 none(level=="none" 时不满足此条件)、绝不冒充 engine-proven strong。
        bootstrap_override = (
            is_bootstrap_normal
            and level == "weak"
            and capabilities.sandbox_enforced
        )
        if bootstrap_override:
            gate_warn(
                f"bootstrap independence override: level={level} below "
                f"min_independence={min_independence}; permitted under "
                "P3-scope-freeze reviewer-attested exception (attested, not "
                "engine-proven)"
            )
            independence_reasons.append(
                f"bootstrap override: {level} below {min_independence}, "
                "permitted (reviewer identity unavailable; attested not engine-proven)"
            )
        else:
            raise GateError(
                f"independence level {level} does not meet minimum "
                f"{min_independence}; reasons: {'; '.join(independence_reasons)}"
            )

    # ------------------------------------------------------------------
    # Invoke consultant and persist verdict + answer artifact
    # ------------------------------------------------------------------
    gate_log(f"invoking codex adapter for {wp_id} ...")
    try:
        verdict = adapter.review(
            diff=diff_text,
            brief=brief_text or None,
            contract=contract,
            effort=gate_effort,
        )
    except Exception as exc:
        raise GateError(f"codex review failed: {exc}") from None

    reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer_file = persist_answer(iteration_dir, wp_id, verdict)
    write_consult_block(
        status_file=status_file,
        verdict=verdict,
        independence_level=level,
        independence_reasons=independence_reasons,
        reviewed_at=reviewed_at,
    )

    run_validator(validator, status_file)

    print(f"GATE_DECISION={verdict.decision}")
    print(
        f"GATE: consult block written to {status_file}; full answer at {answer_file}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
