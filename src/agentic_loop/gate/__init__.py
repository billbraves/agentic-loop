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

# ``gate`` is now a package (``gate/``); ``adapters/``, ``independence.py``,
# ``resolve_paths.py`` and ``validate_wp_status.py`` are its package siblings in
# ``agentic_loop/``. Keep that directory on the bare-python3 path so the
# historical sys.path contract of ``python3 -m agentic_loop.gate`` is preserved.
_PACKAGE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PACKAGE_DIR))

from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.base import ReviewerAttestation
from agentic_loop.adapters.base import Verdict
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.independence import evaluate
from agentic_loop.independence import meets_threshold
from agentic_loop.resolve_paths import get_adapters
from agentic_loop.resolve_paths import get_review_policy
from agentic_loop.resolve_paths import iterations_dir
from agentic_loop.resolve_paths import main_repo
from agentic_loop.resolve_paths import resolve_role_binding


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


# Sentinel returned by ``git_merge_base`` when ``git merge-base --all`` finds
# more than one best common ancestor (criss-cross). A valid commit is hex-only,
# so this value can never collide with a real fork point; the caller must treat
# it as an ambiguity and fail closed instead of guessing.
MERGE_BASE_AMBIGUOUS = "<ambiguous>"


def git_merge_base(repo: Path, base: str, tip: str) -> str:
    """Return the engine-computed fork point of ``base`` and ``tip``.

    Uses ``git merge-base --all`` so a criss-cross topology (multiple best
    common ancestors) is surfaced instead of silently picking one. Mirrors the
    ``git_output`` style (``git -C <repo> ...``) but, unlike ``git_output``,
    returns ``""`` on failure (e.g. ``base`` cannot be resolved) and
    ``MERGE_BASE_AMBIGUOUS`` on ambiguity, instead of raising. This lets the
    diff-start fallback decide whether to use the fork point, fail closed on
    ambiguity, or fall through to ``base_commit``.
    """
    proc = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--all", base, tip],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return ""
    if len(lines) > 1:
        gate_log(
            f"merge-base ambiguous: {len(lines)} common ancestors between "
            f"{base} and {tip}; refusing to guess"
        )
        return MERGE_BASE_AMBIGUOUS
    return lines[0].strip()


def scope_prefix(pattern: str) -> str:
    """Reduce a scope pattern to the literal directory prefix it denotes.

    Scope entries are prefixes, not globs, but authors write ``skills/**`` and
    ``dir/*`` because every other path-matching surface in this tool accepts
    them (``[[gate]] rule.match`` strips exactly these two suffixes). A literal
    ``startswith`` never matches such an entry: no real path contains ``**``.
    A ``forbidden_paths`` entry of ``skills/**`` therefore forbade **nothing**
    while looking active in the status JSON — the worst possible failure mode
    for a fail-closed guard.

    Trailing ``/**`` and ``/*`` are stripped so those spellings mean what their
    author intended. Any *other* wildcard (``a/*/b``, ``*.env``, ``a*b``) is
    NOT reducible to a prefix; it is rejected upstream by
    ``validate_wp_status`` rather than silently mis-handled here.
    """
    normalized = pattern.strip().removeprefix("./")
    for suffix in ("/**", "/*"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized.rstrip("/")


def scope_matches(path: str, prefix: str) -> bool:
    """Prefix match verbatim-aligned with ``quality-gate.sh`` ``matches()``.

    A file path is in scope for ``prefix`` when it equals the prefix or starts
    with ``prefix + "/"``, after reducing the pattern via ``scope_prefix``.
    This is the exact predicate the quality gate uses for its allowed/forbidden
    enforcement, so the merge gate can never diverge from it.
    """
    normalized = scope_prefix(prefix)
    # An entry that reduces to empty (``/``, ``./``, ``**``, whitespace) would
    # match every path. For forbidden that blocks the whole WP; for allowed it
    # silently disables scope enforcement. Refuse to interpret it — the
    # validator rejects such entries, so reaching here means an unvalidated
    # caller, and matching nothing is the fail-closed side for allowed_paths.
    if not normalized:
        return False
    return path == normalized or path.startswith(normalized + "/")


def _path_in_scope(
    path: str, allowed_paths: list[str], forbidden_paths: list[str]
) -> bool:
    """Forbidden wins over allowed; empty ``allowed_paths`` = forbidden only."""
    if any(scope_matches(path, prefix) for prefix in forbidden_paths):
        return False
    if not allowed_paths:
        return True
    return any(scope_matches(path, prefix) for prefix in allowed_paths)


def _diff_path_from_header(block: str) -> str | None:
    """Return the post-image path from a ``diff --git a/... b/...`` header.

    Returns ``None`` when the block is not a diff header or the post-image path
    cannot be parsed; callers keep such blocks verbatim so we never drop content
    we cannot classify (fail-safe against false negatives)."""
    first = block.splitlines()[0] if block else ""
    if not first.startswith("diff --git "):
        return None
    rest = first[len("diff --git "):]
    idx = rest.find(" b/")
    if idx == -1:
        return None
    return rest[idx + 3:].strip()


def filter_diff_by_scope(
    diff_text: str,
    allowed_paths: list[str],
    forbidden_paths: list[str],
) -> tuple[str, int, int]:
    """Filter a multi-file unified diff to files within WP scope.

    Splits on ``diff --git`` file boundaries and keeps a file when it matches at
    least one allowed prefix and no forbidden prefix (forbidden wins). Empty
    ``allowed_paths`` imposes no allowed restriction, mirroring quality-gate.sh.
    Returns ``(filtered_diff, kept_count, excluded_count)``; kept blocks are
    re-joined byte-for-byte so an all-in-scope diff is unchanged."""
    if not diff_text:
        return diff_text, 0, 0

    blocks = re.split(r"(?m)^(?=diff --git )", diff_text)
    kept_blocks: list[str] = []
    kept_count = 0
    excluded_count = 0

    for block in blocks:
        if not block:
            continue
        path = _diff_path_from_header(block)
        if path is None:
            # Not a file block or unparseable: keep verbatim (fail-safe).
            kept_blocks.append(block)
            kept_count += 1
            continue
        if _path_in_scope(path, allowed_paths, forbidden_paths):
            kept_blocks.append(block)
            kept_count += 1
        else:
            excluded_count += 1

    return "".join(kept_blocks), kept_count, excluded_count


def read_scope_paths(validator: Path, status_file: Path, dotted: str) -> list[str]:
    """Read a ``scope.*_paths`` list field via the validator ``--field`` path."""
    raw = read_field(validator, status_file, dotted)
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise GateError(f"{dotted} must be a list, got {type(parsed).__name__}")
    return [str(item) for item in parsed]


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


def read_attestation(status_file: Path) -> ReviewerAttestation | None:
    """Read the structured reviewer attestation from the auditable status record.

    WP-07 REWORK: the bootstrap attestation must come from the persisted
    ``review.attestation`` object in the status file, never from a code
    constant. Missing block, non-object block, or missing/empty required string
    fields resolve to ``None`` so ``evaluate()`` fail-closes to ``none``.

    The boolean fields are passed through verbatim (including any non-bool
    value) so ``ReviewerAttestation.is_valid()`` remains the single source of
    truth for strict-bool validation: JSON ``true`` becomes Python ``True`` and
    is the only accepted value; strings like ``"false"`` stay invalid.
    """
    data = load_status_json(status_file)
    review = data.get("review")
    if not isinstance(review, dict):
        return None
    att = review.get("attestation")
    if not isinstance(att, dict):
        return None

    reviewer_role = att.get("reviewer_role")
    reviewer_tool = att.get("reviewer_tool")
    attested_by = att.get("attested_by")
    if not (
        isinstance(reviewer_role, str)
        and reviewer_role.strip()
        and isinstance(reviewer_tool, str)
        and reviewer_tool.strip()
        and isinstance(attested_by, str)
        and attested_by.strip()
    ):
        return None

    attested_at = att.get("attested_at")
    if not isinstance(attested_at, str):
        attested_at = None

    return ReviewerAttestation(
        reviewer_role=reviewer_role,
        reviewer_tool=reviewer_tool,
        fresh_session=att.get("fresh_session"),
        adversarial_prompt=att.get("adversarial_prompt"),
        attested_by=attested_by,
        attested_at=attested_at,
    )


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


def compute_wp_diff(
    repo_root: Path,
    validator: Path,
    status_file: Path,
    iterations_dir_path: Path,
    *,
    base_commit: str,
    head_commit: str,
    branch: str,
    base_branch: str,
    iteration_id: str,
    wp_id: str,
) -> tuple[str, str, str]:
    """Compute the scope-filtered base→tip diff for a work package.

    Shared by the Codex merge gate and the qoder security gate: branch-tip
    resolution, ancestor integrity, the brief-introducing diff-start fallback,
    the engine-computed merge-base fallback, and scope filtering. Returns
    ``(diff_text, diff_start, tip_commit)``.
    """
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
        # Layer 2: engine-computed fork point. ``base_commit`` is a human-recorded
        # field that can go stale; ``git merge-base --all <base_branch> <tip>`` is
        # the git-truth fork point, so prefer it over the recorded base when the
        # brief-introducing heuristic did not pin a start.
        merge_base_commit = git_merge_base(repo_root, base_branch, tip_commit)
        if merge_base_commit == MERGE_BASE_AMBIGUOUS:
            raise GateError(
                "merge-base ambiguous: multiple common ancestors between "
                f"{base_branch} and {tip_commit}; refusing to guess "
                "(fail-closed, brief stop condition)"
            )
        if merge_base_commit:
            if not (
                git_is_ancestor(repo_root, base_commit, merge_base_commit)
                and git_is_ancestor(repo_root, merge_base_commit, tip_commit)
            ):
                raise GateError(
                    f"merge-base diff start {merge_base_commit} is outside "
                    f"{base_commit}..{tip_commit}; refusing to review an "
                    "invalid diff range (fail-closed)"
                )
            diff_start = merge_base_commit
            gate_log(
                f"diff start = merge-base {merge_base_commit} "
                f"(base_branch '{base_branch}', tip {tip_commit}; "
                f"brief-introducing heuristic missed: {fallback_reason})"
            )
        else:
            diff_start = base_commit
            gate_log(
                f"diff start = base_commit {base_commit} "
                f"(brief-introducing heuristic missed: {fallback_reason}; "
                f"merge-base unavailable for base_branch '{base_branch}')"
            )

    diff_text = git_output(repo_root, "diff", f"{diff_start}..{tip_commit}")

    # Scope-filter the diff so only this WP's files are sent downstream. Forbidden
    # wins over allowed; empty allowed = forbidden only (quality-gate.sh parity).
    allowed_paths = read_scope_paths(validator, status_file, "scope.allowed_paths")
    forbidden_paths = read_scope_paths(
        validator, status_file, "scope.forbidden_paths"
    )
    diff_text, kept_count, excluded_count = filter_diff_by_scope(
        diff_text, allowed_paths, forbidden_paths
    )
    gate_log(
        f"scope filter: retained {kept_count} file(s), "
        f"excluded {excluded_count} file(s)"
    )
    if not diff_text:
        gate_log("GATE: scope-filtered diff is empty")

    return diff_text, diff_start, tip_commit


def _enforce_autonomy(repo_root: Path) -> None:
    """Opt-in autonomy gate for ``merge_gate`` (fail-closed to STOP, exit 3).

    Runs BEFORE any Codex quota is spent: if the project's ``[autonomy]`` policy
    does not auto-approve ``merge_gate`` and no human-approved override is set,
    the gate refuses with a distinct ``GATE_STOP`` line and exit 3 (the autonomy
    STOP code), never burning credits on a step that should have been gated.
    """
    from agentic_loop.autonomy import STOP, configured, decide
    from agentic_loop.resolve_paths import get_autonomy

    if not configured(repo_root):
        return
    if decide("merge_gate", get_autonomy(repo_root)) == STOP and os.environ.get(
        "AGENTIC_AUTONOMY_APPROVE", "0"
    ) != "1":
        print(
            "GATE_STOP: autonomy requires human approval (merge_gate); "
            "set AGENTIC_AUTONOMY_APPROVE=1 after human approval",
            file=sys.stderr,
        )
        raise SystemExit(3)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: gate.py <work-package-status.json>", file=sys.stderr)
        return 64

    status_arg = argv[0]

    repo_root = main_repo()
    iterations_dir_path = iterations_dir()
    # Sibling module inside the agentic_loop package (moved in WP-18).
    validator = _PACKAGE_DIR / "validate_wp_status.py"

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

    # Autonomy gate: check BEFORE spending Codex quota (fail-closed to STOP).
    _enforce_autonomy(repo_root)

    wp_id = read_field(validator, status_file, "work_package_id")
    iteration_id = read_field(validator, status_file, "iteration_id")
    phase = read_field(validator, status_file, "phase")
    base_commit = read_field(validator, status_file, "git.base_commit")
    head_commit = read_field(validator, status_file, "git.commit")
    branch = read_field(validator, status_file, "git.branch")
    base_branch = read_field(validator, status_file, "git.base_branch") or "main"

    if not base_commit or not head_commit:
        raise GateError(
            "git.base_commit and git.commit are required for the diff"
        )

    if not branch:
        raise GateError(
            "git.branch is required to resolve the diff endpoint (branch tip)"
        )

    diff_text, diff_start, tip_commit = compute_wp_diff(
        repo_root,
        validator,
        status_file,
        iterations_dir_path,
        base_commit=base_commit,
        head_commit=head_commit,
        branch=branch,
        base_branch=base_branch,
        iteration_id=iteration_id,
        wp_id=wp_id,
    )

    iteration_dir = iterations_dir_path / iteration_id
    brief_path = iteration_dir / f"{wp_id}-brief.md"
    if brief_path.is_file():
        brief_text = brief_path.read_text(encoding="utf-8")
    else:
        gate_warn(f"brief not found at {brief_path}; proceeding with diff-only review")
        brief_text = ""

    gate_effort = resolve_gate_effort(iteration_dir, phase)
    gate_log(f"phase={phase} → model_reasoning_effort={gate_effort}")

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

    # Resolve the consultant's provider binding (e.g. DeepSeek) so codex is
    # actually injected with it — not its global default model.
    _, consultant_binding = resolve_role_binding("consultant", repo=repo_root)
    adapter = CodexAdapter(binding=consultant_binding)

    # INV-2: require self-attestable level-2 capabilities.
    capabilities = adapter.capabilities()
    if not (capabilities.sandbox_enforced and capabilities.structured_output):
        raise GateError(
            "consultant capabilities not provable: sandbox_enforced or "
            "structured_output false"
        )

    # ------------------------------------------------------------------
    # Independence rating (WP-09/WP-07) with structured bootstrap attestation
    # ------------------------------------------------------------------
    min_independence = review_policy.get("min_independence", "strong")
    consultant_identity = adapter.identity()

    implementer_id: AgentIdentity | None = None
    if review_decision == "N/A":
        executor_tool = read_field(validator, status_file, "executor.tool")
        implementer_id = AgentIdentity(tool=executor_tool or "unassigned")

    # True bootstrap path: review=ACCEPT and no implementer fallback. The
    # reviewer is the orchestrator (no adapter identity), so its identity is
    # declared as a structured attestation. WP-07 REWORK: that attestation is
    # now READ from the auditable status record (``review.attestation``), never
    # constructed in code. Missing/invalid -> None, so ``evaluate()``
    # fail-closes to ``none`` instead of silently self-signing a valid
    # declaration. The attestation never upgrades the rating to strong.
    is_bootstrap_normal = review_decision == "ACCEPT" and implementer_id is None
    attestation: ReviewerAttestation | None = None
    if is_bootstrap_normal:
        attestation = read_attestation(status_file)

    level, independence_reasons = evaluate(
        reviewer_id=None,
        consultant_id=consultant_identity,
        capabilities=capabilities,
        min_independence=min_independence,
        implementer_id=implementer_id,
        attestation=attestation,
    )

    # WP-07: the structured attestation above replaces the former text-only
    # none→weak override. With a valid attestation, ``evaluate()`` already
    # returns weak-attested for the bootstrap path; with missing/invalid
    # attestation it fail-closes to none and the gate rejects below.

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

