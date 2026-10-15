#!/usr/bin/env python3
"""agentic plan — plan-level convergence: one plan = one merged commit.

A *plan* groups N work packages (WPs) under a single integration branch — one
plan (iteration) = one branch. Sequential WPs work on that one branch; only
"parallel lanes" that genuinely need concurrent execution get separate branches
(AGENTS.md §5). The plan-level commands here converge the whole plan into ONE
merge commit on the target branch (`git.target_branch`, normally `main`), instead
of N commits/pushes leaking onto the protected branch.

Sub-actions:

  plan check    <plan.status.json>  read-only: report WP + merge convergence
  plan lint     <plan.status.json>  read-only: enforce status commit discipline
                                    (freeze + finalize only, no review/consult/
                                    override "sync" commits) per WP
  plan lanes    <plan.status.json>  read-only: compute READY / BLOCKED / DONE
                                    from the dependency graph + lane serialization
  plan merge    <plan.status.json>  single `git merge --no-ff <integration>`
                                    onto the target branch (the only git-mutating
                                    step; autonomy-gated as local_merge_no_ff;
                                    fails closed on any status-sync commit)
  plan finalize <plan.status.json>  stamp state=MERGED + merged_commit
                                    (status-only, never touches git — mirrors
                                    finalize_merge.sh)

`push` is deliberately NOT a plan action: it stays a hard ``always_stop`` action
the user approves exactly once, after the single plan merge. This is what turns
"split a plan into WPs -> N independent commits/pushes" into "one plan -> one
merged commit -> one push".

Plan state machine:

  DRAFT -> ACTIVE -> READY_TO_MERGE -> MERGED
  DRAFT -> ABANDONED
  ACTIVE -> BLOCKED -> ACTIVE

Commit discipline (enforced by `plan lint` and `plan merge`): on the integration
branch, each WP's status file is committed exactly twice — once at freeze (the
add), once at finalize (state=MERGED with all signatures folded in). The
implementation commits land on the branch in between (they do not touch the
status file). Review / consult / override / qoder decisions are accumulated as
working-tree changes and committed only inside the finalize commit, so they
never appear as separate "sync" commits.

Fail-closed: `merge` and `finalize` re-verify the evidence (every declared WP is
MERGED in the integration branch; the integration branch tip is actually merged
into the target), never trusting the plan state alone.

Stdlib only; no network, no third-party dependency.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from agentic_loop import autonomy as _autonomy
from agentic_loop import resolve_paths as _rp

SCHEMA_VERSION = "agentic-plan-status/v1"

STATES = {
    "DRAFT",
    "ACTIVE",
    "READY_TO_MERGE",
    "MERGED",
    "ABANDONED",
    "BLOCKED",
}

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "plan_id",
    "iteration_id",
    "state",
    "git",
    "work_packages",
    "timestamps",
}

OPTIONAL_TOP_LEVEL = {"title", "lint_exemption"}

# Default lane a WP lands in when its object entry has no `lane` (and every WP
# in the legacy string form). A lane is defined as *serial*: at any instant,
# only one READY WP per lane may start (§5 + WP-03 brief).
DEFAULT_LANE = "default"

# Exit codes (mirror the WP gates: 0 ok, 2 fail, 3 autonomy stop / not converged,
# 64 usage).
RC_OK = 0
RC_FAIL = 2
RC_STOP = 3
RC_USAGE = 64


# ---------------------------------------------------------------------------
# JSON load + schema validation (pure)
# ---------------------------------------------------------------------------

def load_plan(path: Path) -> tuple:
    """Read the plan file exactly once and parse those same raw bytes.

    Returns ``(raw, data)``.  The raw bytes are the bytes actually parsed;
    every later trust decision must compare against them, never a re-read
    of the path (INV-3c).
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise ValueError("plan status file does not exist: {}".format(path)) from None
    except OSError as exc:
        raise ValueError("plan status file cannot be read: {} ({})".format(path, exc)) from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("plan status file is not valid UTF-8: {}".format(exc)) from None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON at line {}: {}".format(exc.lineno, exc.msg)) from None
    if not isinstance(value, dict):
        raise ValueError("plan status root must be a JSON object")
    return raw, value


def validate(data: dict) -> list:
    errors: list = []
    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        errors.append(
            "schema_version must be {} (got {!r})".format(SCHEMA_VERSION, schema_version)
        )
    missing = sorted(REQUIRED_TOP_LEVEL - data.keys())
    if missing:
        errors.append("missing top-level fields: {}".format(", ".join(missing)))
    extra = sorted(data.keys() - REQUIRED_TOP_LEVEL - OPTIONAL_TOP_LEVEL)
    if extra:
        errors.append("unknown top-level fields: {}".format(", ".join(extra)))

    state = data.get("state")
    if state not in STATES:
        errors.append("invalid state: {!r}".format(state))

    for field in ("plan_id", "iteration_id"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append("{} must be a non-empty string".format(field))
            continue
        # INV-3e: both fields are concatenated into the canonical plan path,
        # so each must be a SINGLE safe relative component.  Enforced here (not
        # only at the concatenation site) so every caller of validate() — and
        # therefore `plan check/lint/lanes/merge/finalize` — rejects a field of
        # `"../../etc"` before any path is derived.
        if not _is_single_path_component(value):
            errors.append(
                "{} must be a single relative path component (no '/', no "
                "'\\', not '.' or '..', no leading dot, no NUL)".format(field)
            )

    git = data.get("git")
    if not isinstance(git, dict):
        errors.append("git must be an object")
        git = {}
    base_branch = git.get("base_branch")
    target_branch = git.get("target_branch")
    if not isinstance(base_branch, str) or not base_branch.strip():
        errors.append("git.base_branch must be a non-empty string")
    if not isinstance(target_branch, str) or not target_branch.strip():
        errors.append("git.target_branch must be a non-empty string")
    if (
        isinstance(base_branch, str)
        and isinstance(target_branch, str)
        and base_branch
        and base_branch == target_branch
    ):
        errors.append("git.base_branch must differ from git.target_branch")

    work_packages = data.get("work_packages")
    if not isinstance(work_packages, list):
        errors.append("work_packages must be a list")
    else:
        seen_ids = set()
        for item in work_packages:
            if isinstance(item, str):
                if not item.strip():
                    errors.append(
                        "work_packages entries must be non-empty strings or objects"
                    )
                    continue
                wp_id = item
            elif isinstance(item, dict):
                wp_id = item.get("id")
                if not isinstance(wp_id, str) or not wp_id.strip():
                    errors.append(
                        "work_packages object entries need a non-empty 'id'"
                    )
                    continue
                lane = item.get("lane")
                if lane is not None and (not isinstance(lane, str) or not lane.strip()):
                    errors.append("work_packages[{!r}].lane must be a non-empty string".format(wp_id))
                depends_on = item.get("depends_on")
                if depends_on is not None and not isinstance(depends_on, list):
                    errors.append("work_packages[{!r}].depends_on must be a list".format(wp_id))
            else:
                errors.append("work_packages entries must be strings or objects")
                continue
            if wp_id in seen_ids:
                errors.append("duplicate work_packages id: {!r}".format(wp_id))
            seen_ids.add(wp_id)

    timestamps = data.get("timestamps")
    if not isinstance(timestamps, dict):
        errors.append("timestamps must be an object")

    if state == "MERGED" and not git.get("merged_commit"):
        errors.append("git.merged_commit is required in state MERGED")
    if state in {"READY_TO_MERGE", "MERGED"} and not work_packages:
        errors.append("work_packages must not be empty in state {}".format(state))

    # Topology: dependencies must exist, must not cycle, must not deadlock across
    # lanes. Performed here so `plan check` and `plan lanes` both reject before
    # any git/IO work.
    if isinstance(work_packages, list):
        norm = _normalize_work_packages(work_packages)
        wp_ids = [wp["id"] for wp in norm]
        present = {wp["id"] for wp in norm if isinstance(wp["id"], str)}
        graph = _dependency_graph(work_packages)

        for wp_id in wp_ids:
            for dep in graph.get(wp_id, []):
                if dep not in present:
                    errors.append(
                        "work_packages[{!r}] depends_on missing WP {!r}".format(
                            wp_id, dep
                        )
                    )

        cycle = _find_cycle(graph)
        if cycle is not None:
            errors.append("dependency cycle detected: {}".format(" -> ".join(cycle)))

    return errors


def _validate_or_raise(data: dict, label: str) -> None:
    errors = validate(data)
    if errors:
        for error in errors:
            print("PLAN_INVALID: {}: {}".format(label, error), file=sys.stderr)
        raise SystemExit(RC_FAIL)


# ---------------------------------------------------------------------------
# Work-package normalization + dependency topology (pure: no IO, no clock)
# ---------------------------------------------------------------------------

def _normalize_work_packages(work_packages: list) -> list:
    """Normalize the dual-form `work_packages` into a list of dicts, each with
    keys `id`, `lane`, `depends_on`. String entries become
    ``{"id": <str>, "lane": DEFAULT_LANE, "depends_on": []}``; object entries
    inherit a missing `lane` as DEFAULT_LANE and a missing `depends_on` as [].
    """
    out = []
    for item in work_packages:
        if isinstance(item, str):
            out.append(
                {"id": item, "lane": DEFAULT_LANE, "depends_on": []}
            )
        elif isinstance(item, dict):
            dep = item.get("depends_on")
            out.append(
                {
                    "id": item.get("id"),
                    "lane": item.get("lane") or DEFAULT_LANE,
                    "depends_on": list(dep) if isinstance(dep, list) else [],
                }
            )
        # Non-str, non-dict entries are invalid per the per-entry schema loop in
        # validate(); skip them here so callers (topology block, _wp_ids,
        # _dependency_graph, _lanes_ready) never crash on a type-error entry.
    return out


def _wp_ids(work_packages: list) -> list:
    """The WL IDs in declared order (used by the git-status discovery path)."""
    return [wp["id"] for wp in _normalize_work_packages(work_packages)]


def _dependency_graph(work_packages: list) -> dict:
    """Map of wp id -> [dependencies] (only entries whose id is a string)."""
    graph = {}
    for wp in _normalize_work_packages(work_packages):
        if isinstance(wp["id"], str):
            graph[wp["id"]] = [d for d in wp["depends_on"] if isinstance(d, str)]
    return graph


def _find_cycle(graph: dict):
    """Return a cycle as a list of node ids, or None when acyclic.

    Iteratively strip nodes that have no unresolved dependency within the
    remaining set (topological layering). Any node left over belongs to at least
    one cycle; reconstruct one concrete cycle by walking dependencies inside the
    residue."""
    remaining = {n for n in graph if isinstance(n, str)}
    changed = True
    while changed:
        changed = False
        for node in list(remaining):
            deps = [d for d in graph.get(node, []) if d in remaining]
            if not deps:
                remaining.discard(node)
                changed = True

    if not remaining:
        return None

    # Walk one cycle inside the residue. Every remaining node still has at least
    # one dependency in `remaining`, so following deps cannot dead-end.
    start = sorted(remaining)[0]
    path = [start]
    pos = {start: 0}
    while True:
        cur = path[-1]
        nxt = next((d for d in graph.get(cur, []) if d in remaining), None)
        if nxt is None:
            return None
        if nxt in pos:
            return path[pos[nxt]:] + [nxt]
        pos[nxt] = len(path)
        path.append(nxt)


def _lanes_ready(work_packages: list, states: dict):
    """Pure ready-set computation. `states` maps wp id -> WP state string
    ('MERGED' means done). Returns a dict with keys `ready`, `blocked`, `done`.

    - `ready`   : deps all done AND self not done -> can start now.
    - `blocked` : [(wp_id, [unfinished dep ids])] -> waiting on someone.
    - `done`    : [wp_id] already MERGED.

    Same-lane serialization is NOT decided here (a lane may contain several
    READY WPs); the caller picks one READY WP per lane, since lanes are serial
    by definition."""
    done_ids = {wp_id for wp_id, state in states.items() if state == "MERGED"}
    norm = _normalize_work_packages(work_packages)
    graph = {wp["id"]: [d for d in wp["depends_on"] if isinstance(d, str)]
             for wp in norm if isinstance(wp["id"], str)}

    ready = []
    blocked = []
    done = []
    for wp in norm:
        wp_id = wp["id"]
        if not isinstance(wp_id, str):
            continue
        state = states.get(wp_id)
        if state == "MERGED":
            done.append(wp_id)
            continue
        unfinished = [d for d in graph.get(wp_id, []) if d not in done_ids]
        if unfinished:
            blocked.append((wp_id, unfinished))
        else:
            ready.append(wp_id)
    return {"ready": ready, "blocked": blocked, "done": done}


# ---------------------------------------------------------------------------
# Git helpers (all operate on the MAIN repo, like the WP merge/finalize gates)
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git {} failed".format(" ".join(args)))
    return proc.stdout.strip()


def _git_may_fail(repo: Path, *args: str):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )


def _tip(repo: Path, ref: str) -> str:
    proc = _git_may_fail(repo, "rev-parse", "--verify", "refs/heads/{}".format(ref))
    if proc.returncode != 0:
        raise ValueError("cannot resolve branch '{}' tip".format(ref))
    return proc.stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = _git_may_fail(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    return proc.returncode == 0


def _resolve_plan_merge_commit(repo: Path, base_tip: str, target_tip: str) -> list:
    """Merge commits in target history whose second parent is the base tip."""
    out = _git(repo, "rev-list", "--merges", "--parents", target_tip)
    candidates = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == base_tip:
            candidates.append(parts[0])
    return candidates


def _blob_exists(repo: Path, treeish: str, path: str) -> bool:
    proc = _git_may_fail(repo, "cat-file", "-e", "{}:{}".format(treeish, path))
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# WP status discovery (git-based: the integration branch is the source of truth)
# ---------------------------------------------------------------------------

def _rel_iter_dir(repo: Path, iteration_id: str) -> str:
    """Relative path (from the repo root) of the iteration directory."""
    base = os.path.relpath(_rp.iterations_dir(), repo)
    base = "" if base == "." else base
    return iteration_id if not base else "{}/{}".format(base, iteration_id)


def _candidate_paths(rel_iter: str, wp_id: str) -> list:
    name = "{}.status.json".format(wp_id)
    if rel_iter in ("", "."):
        return [name, "work-packages/{}".format(name)]
    return [
        "{}/{}".format(rel_iter, name),
        "{}/work-packages/{}".format(rel_iter, name),
    ]


def _status_git_paths(data: dict, repo: Path) -> list:
    """Return [(wp_id, git_relative_path)] resolved against the integration
    branch tree (not the working tree, which is on the target branch at merge
    time)."""
    base = data["git"]["base_branch"]
    rel_iter = _rel_iter_dir(repo, data.get("iteration_id", ""))
    out = []
    for wp_id in _wp_ids(data.get("work_packages", [])):
        chosen = None
        for c in _candidate_paths(rel_iter, wp_id):
            if _blob_exists(repo, base, c):
                chosen = c
                break
        out.append((wp_id, chosen or _candidate_paths(rel_iter, wp_id)[0]))
    return out


def _wp_status_git(repo: Path, base: str, git_path: str) -> dict | None:
    proc = _git_may_fail(repo, "show", "{}:{}".format(base, git_path))
    if proc.returncode != 0:
        return None
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


# ---------------------------------------------------------------------------
# Autonomy gate (reuse the existing actions: merge -> local_merge_no_ff,
# finalize -> finalize_merge; identical semantics to the WP gates)
# ---------------------------------------------------------------------------

def _autonomy_stop(action: str) -> bool:
    """True when the project's [autonomy] policy STOPS this action and the
    one-step human approval env flag is not set. Not configured => not gated."""
    try:
        repo = _rp.main_repo()
    except SystemExit:
        return False
    if not _autonomy.configured(repo):
        return False
    verdict = _autonomy.decide(action, _rp.get_autonomy(repo))
    if verdict == "STOP" and os.environ.get("AGENTIC_AUTONOMY_APPROVE") != "1":
        return True
    return False


# ---------------------------------------------------------------------------
# Shared: resolve the plan file path against the main repo (single source of
# truth), mirroring finalize_merge.sh's main-repo-only resolution.
# ---------------------------------------------------------------------------

def _resolve_plan_path(plan_arg: str) -> Path:
    arg = Path(plan_arg)
    if arg.is_absolute():
        return arg
    repo = _rp.main_repo()
    return repo / arg


def _discover_relative_candidates(rel: str) -> list:
    """R3-a stage 1 for the canonical RELATIVE shape: deterministic candidate
    discovery, in registered-worktree order (INV-3b rule 3).

    ``_resolve_plan_path()`` is deliberately NOT used: it anchors a relative
    spelling at ``main_repo()``, while the plan file is committed only on the
    integration branch (E13's first-introduction case), so that spelling
    resolves to a main-repo path that does not exist and is undeployable.  The
    spelling is instead joined onto EVERY registered worktree root and the
    candidates that actually exist are collected.  Nothing here grants trust:
    the returned paths are only read once, and uniqueness is decided later on
    the candidates that pass the full stage-2 check (rev11)."""
    try:
        roots = _registered_worktrees(_rp.main_repo())
    except (OSError, RuntimeError, ValueError, SystemExit):
        return []
    out = []
    for wt_root in roots:
        candidate = Path(wt_root) / rel
        try:
            if candidate.is_file():
                out.append(candidate)
        except (OSError, RuntimeError, ValueError):
            continue
    return out


def _discover_absolute_candidates(plan_arg: str) -> list:
    """R3-a stage 1 for the ABSOLUTE shape: exactly one candidate, the caller's
    own spelling (INV-3b rule 3, 'absolute: use that absolute path itself').
    No worktree is needed to locate it, so this works even when the caller is
    not inside the repository."""
    try:
        path = Path(plan_arg)
        if path.is_file():
            return [path]
    except (OSError, RuntimeError, ValueError):
        return []
    return []


def _stage1_load(plan_arg: str) -> tuple:
    """R3-a stages 0+1: locate the caller's spelling and read it ONCE.

    Returns ``(data, path, raw)``.  The single read is explicitly authorized by
    R3-a and grants no trust; ``raw`` is the bytes that were parsed, retained
    for INV-3c's rule-4 comparison.  Fail-closed with a reason-specific witness:

      * an unaccepted spelling is rejected lexically (stage 0), without
        touching the filesystem at all;
      * zero existing candidate (relative) / no such file (absolute) reports
        ``no candidate`` rather than falling back to any other root;
      * more than one existing candidate for the ABSOLUTE shape cannot happen
        (the spelling is a single literal); for the RELATIVE shape existence
        alone is NOT a rejection criterion (rev11) — every existing candidate
        is read once and the uniqueness decision is made by stage 2 on the
        candidates that pass the trust check.
    """
    shape, rel = _plan_arg_shape(plan_arg)
    if shape == "reject":
        print(
            "PLAN_FAIL: plan status path has an unaccepted spelling: {}".format(
                plan_arg
            ),
            file=sys.stderr,
        )
        raise SystemExit(RC_FAIL)

    def _report(reason: str):
        print("PLAN_FAIL: {}".format(reason), file=sys.stderr)
        raise SystemExit(RC_FAIL)

    if shape == "relative":
        candidates = _discover_relative_candidates(rel)
    else:
        candidates = _discover_absolute_candidates(plan_arg)
    if not candidates:
        if shape == "relative":
            _report(
                "no trusted candidate for the plan status path {} (no registered "
                "worktree carries it)".format(plan_arg)
            )
        _report("plan status file does not exist: {}".format(plan_arg))
    path = candidates[0]
    try:
        _raw, data = load_plan(path)
    except ValueError as exc:
        _report(str(exc))
    _validate_or_raise(data, path.name)
    return data, path, _raw


def _load_and_validate(plan_arg: str) -> tuple:
    """Read + validate the plan file at the caller's spelling (R3-a stage 1).

    Absolute spellings keep the historical single-path semantics; a canonical
    relative spelling goes through deterministic candidate discovery so the
    documented `agentic plan merge docs/plans/<iter>/<plan>.json` form works
    from any CWD and from a checkout where only the integration branch carries
    the file (rev10/rev11)."""
    return _stage1_load(plan_arg)


def _git_bytes_may_fail(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True)


def _git_common_dir(repo: Path) -> Path:
    """Resolved ``git-common-dir`` of ``repo`` (shared across linked worktrees)."""
    out = _git(repo, "rev-parse", "--git-common-dir")
    p = Path(out)
    if not p.is_absolute():
        p = repo / p
    return p.resolve()


def _registered_worktrees(repo: Path) -> dict:
    """Map each registered worktree root (resolved) -> current branch name
    (None when detached), from ``git worktree list --porcelain``."""
    proc = _git_may_fail(repo, "worktree", "list", "--porcelain")
    if proc.returncode != 0:
        return {}
    out: dict = {}
    current: Path | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            try:
                current = Path(line[len("worktree "):]).resolve()
            except (OSError, RuntimeError, ValueError):
                current = None
            if current is not None:
                out.setdefault(current, None)
        elif line.startswith("branch refs/heads/") and current is not None:
            out[current] = line[len("branch refs/heads/"):]
    return out


def _is_single_path_component(value: object) -> bool:
    """True only when ``value`` is a single, safe relative path component.

    ``iteration_id`` and ``plan_id`` are concatenated into the canonical plan
    path, so a value that itself carries path syntax makes "derived from the
    worktree root" vacuous: ``iteration_id="../../etc"`` would derive
    ``docs/plans/../../etc/PLAN-1.status.json`` and ``"."`` would collapse the
    iteration directory away (INV-3e, rev9).  The constraints are: a non-empty
    string, no path separators (``/`` or ``\\``), not ``.`` / ``..``, no leading
    dot, and no NUL.  This is deliberately stricter than "no separator" — an
    id must be a plain directory/file name an attacker cannot bend."""
    if not isinstance(value, str) or not value.strip():
        return False
    if value in (".", ".."):
        return False
    if value.startswith("."):
        return False
    if "/" in value or "\\" in value or "\x00" in value:
        return False
    return True


def _canonical_plan_rel(data: dict):
    """Lexically safe repo-relative canonical path of the plan status file:
    ``<iterations_dir>/<iteration_id>/<plan_id>.status.json``. None when the
    configured iterations_dir escapes the repo root, or when either path field
    is not a single safe component (INV-3e).

    Defensive only: ``validate()`` already fails closed on such fields, so call
    sites that ran ``_validate_or_raise`` first can never see the ``None``."""
    try:
        if not _is_single_path_component(data.get("iteration_id")):
            return None
        if not _is_single_path_component(data.get("plan_id")):
            return None
        repo = _rp.main_repo()
        rel = os.path.relpath(_rp.iterations_dir(), repo)
    except (OSError, RuntimeError, ValueError, SystemExit):
        return None
    rel_path = Path(rel)
    if rel_path.is_absolute() or rel_path.parts[:1] == ("..",):
        return None
    return (rel_path / data["iteration_id"] / "{}.status.json".format(data["plan_id"])).as_posix()


def _lint_exemption_is_legal(exemption: object) -> bool:
    """Return True only for the repository's strict four-field approval shape."""
    if not isinstance(exemption, dict):
        return False
    if exemption.get("approved") is not True:
        return False
    approver = exemption.get("approver")
    if not isinstance(approver, str) or not approver.strip():
        return False
    justification = exemption.get("justification")
    if not isinstance(justification, str) or not justification.strip():
        return False
    reviewed_at = exemption.get("reviewed_at")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        return False
    return True


def _lexical_absolute(path: Path) -> Path:
    """Absolute + lexical-normalized form of ``path`` (``os.path.normpath``).

    NOT used by the source-trust check: ``normpath`` collapses ``hop/..``
    lexically, which hides a symlinked component from every later check (the r4
    bypass).  It survives only as the historical spelling used by the
    `canonical-symlink` test shape, which asserts that lexical equality alone
    would NOT reject a symlinked leaf."""
    return Path(os.path.normpath(os.path.abspath(path)))


def _no_symlinked_component(wt_root: Path, rel: str) -> bool:
    """True only when every relative component of ``rel`` under ``wt_root``
    exists and is a real (non-symlink) filesystem entry.

    ``rel`` is the DERIVED canonical repo-relative path of the plan status file
    (``docs/plans/<iteration_id>/<plan_id>.status.json``).  Each accumulated
    path is inspected with ``Path.is_symlink()``, which is an ``lstat`` and
    never follows links, so a symlinked parent component (e.g. a relocated
    ``docs`` tree) is detected instead of silently followed (INV-3b rule 3,
    R3-b).  Fail-closed: any ``OSError``/``RuntimeError``/``ValueError``
    (including a missing or dangling component) returns False.  The file's
    bytes are never read here (INV-3c)."""
    try:
        current = Path(wt_root)
        for part in Path(rel).parts:
            current = current / part
            if current.is_symlink():
                return False
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _plan_arg_shape(plan_arg: str):
    """R3-c pre-sanitization: classify the caller's RAW spelling, lexically.

    Runs strictly before any ``normpath`` / ``abspath`` / ``resolve``: those
    would collapse ``hop/..`` (hiding a symlinked component) or fold a ``.`` /
    doubled separator into a different spelling that then compares equal.  The
    output is one of:

      * ``("reject", None)``           — carries ``..`` / ``.`` / ``//`` / a
        trailing separator, or is neither accepted shape;
      * ``("absolute", None)``         — an absolute spelling to use verbatim;
      * ``("relative", rel)``          — a canonical relative spelling, mapped
        later onto whichevery registered worktree root actually carries it.

    A canonical relative spelling must consist of non-empty, non-``.``/``..``
    components; every component except the last must additionally not start
    with a dot (no hidden segment traversal), and the last must be
    ``<plan_id>.status.json``.  The terminal ``.status.json`` and the iteration
    directory are therefore the only opaque parts, and both are verified
    byte-for-byte against the file's own fields in stage 2."""
    if not isinstance(plan_arg, str) or not plan_arg:
        return ("reject", None)
    if "\x00" in plan_arg:
        return ("reject", None)
    if plan_arg.endswith("/") or plan_arg.endswith("/."):
        return ("reject", None)
    if "//" in plan_arg:
        return ("reject", None)
    if os.path.isabs(plan_arg):
        # Absolute: the sole accepted spelling.  Stage 2 requires byte-exact
        # equality with the derived path, so any oddity (a ``.``/``..``/``//``
        # component) is rejected there; only a trailing separator is caught
        # here, because it changes the spelling without changing the path.
        return ("absolute", None)
    if plan_arg.endswith("/") or plan_arg.endswith("."):
        return ("reject", None)
    parts = plan_arg.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return ("reject", None)
    if any(part.startswith(".") for part in parts[:-1]):
        return ("reject", None)
    if not parts[-1].endswith(".status.json") or parts[-1] == ".status.json":
        return ("reject", None)
    return ("relative", plan_arg)


def _stage2_candidate(
    plan_arg: str,
    shape: str,
    rel: str,
    wt_root: Path,
    main_common: Path,
) -> tuple:
    """INV-3b stage 2: independently re-check one candidate's bytes.

    The candidate is read AT MOST ONCE — exactly one read here, against the
    caller's spelling (explicitly authorized by R3-a stage 1, which forbids only
    a *second* read) — and every acceptance decision below uses that raw bytes
    object plus the DERIVED path.  Returns ``raw`` on success and ``None`` on
    any failure, including a failure to parse the candidate at all (a candidate
    whose bytes cannot be parsed cannot have declared the base branch we need,
    so it is simply not trusted).

    Invariants checked, each of which alone must be able to fail closed:

    1. the worktree is registered and shares the main repo's resolved
       ``git-common-dir``;
    2. its current branch is byte-exactly what the file itself declares as
       ``git.base_branch`` (this is what excludes a parallel-lane worktree that
       merely inherits the same relative path, E18(c1));
    3. the file's ``iteration_id`` / ``plan_id`` match the canonical relative
       spelling component by component (no field forgery can move trust to a
       different worktree, E18(d)); the fields must also be safe single
       components (INV-3e);
    4. containment: the derived path stays lexically below the worktree root;
    5. every component of the derived path, leaf and parents, is a real
       (non-symlink) entry — R3-b;
    6. raw bytes == ``git show <base_branch>:<derived-rel>``.
    """
    base_branch = ""
    try:
        if _git_common_dir(wt_root) != main_common:
            return None
        raw = (Path(plan_arg) if shape == "absolute" else wt_root / rel).read_bytes()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            return None
        iteration_id = data.get("iteration_id")
        plan_id = data.get("plan_id")
        git = data.get("git")
        if not isinstance(git, dict):
            return None
        base_branch = git.get("base_branch")
    except (OSError, RuntimeError, ValueError, UnicodeDecodeError, SystemExit):
        return None
    if not isinstance(base_branch, str) or not base_branch.strip():
        return None
    # (3) The file's own fields must BE the spelling we were asked for — an
    # attacker cannot stash a file whose fields point elsewhere under a
    # legitimate relative spelling.  `rel` is the effective repo-relative path
    # (``<iterations_dir>/<iteration_id>/<plan_id>.status.json``), and the
    # iterations_dir prefix is the engine's own constant, so the fields must
    # equal its last two components byte for byte.
    if not _is_single_path_component(iteration_id) or not _is_single_path_component(plan_id):
        return None
    rel_parts = Path(rel).parts
    if len(rel_parts) < 2 or rel_parts[-2:] != (iteration_id, "{}.status.json".format(plan_id)):
        return None
    # (2) Branch binding: the worktree's CURRENT branch must be the one the
    # file declares.  A lane worktree cut from the integration branch inherits
    # this file but is checked out at a different branch, so it is dropped here
    # rather than by the accident of the file existing (rev11).
    try:
        if _registered_worktrees(_rp.main_repo()).get(Path(wt_root).resolve()) != base_branch:
            return None
    except (OSError, RuntimeError, ValueError, SystemExit):
        return None
    derived = Path(wt_root) / rel
    # (4) Containment: the derivation itself must not escape the root.
    if Path(rel).is_absolute() or Path(rel).parts[:1] == ("..",):
        return None
    # (5) R3-b: derived path, per-component lstat from the worktree root down.
    if not _no_symlinked_component(wt_root, rel):
        return None
    if not derived.is_file() or derived.is_symlink():
        return None
    # (6) INV-3c / rule 4: the DERIVED path names the blob to compare, and the
    # object compared is the raw bytes read above — never a re-read.
    blob = _git_bytes_may_fail(_rp.main_repo(), "show", "{}:{}".format(base_branch, rel))
    if blob.returncode != 0 or blob.stdout != raw:
        return None
    return raw


def _trusted_candidate_raw(
    plan_arg: str, path: Path, data: dict, raw: bytes
):
    """INV-3b rule 3 (rev8 direction: canonicalize once) — returns
    ``(ok, witness)``.

    Trust is NOT established by validating whatever spelling the caller typed.
    The engine derives the canonical path itself and accepts exactly two
    spellings, byte for byte:

      * canonical absolute: ``<worktree_root>/<iterations_dir>/<iter>/<plan>.status.json``;
      * canonical relative: ``<iterations_dir>/<iter>/<plan>.status.json``.

    Anything else (case variants, Unicode normalization variants, Windows
    separators as literals, symlink aliases, paths outside the repository, a
    copy in the target worktree) can only fail, and no enumeration of known
    aliases exists to be out-grown.

    The caller's path is used in exactly two places and nowhere else: the
    single read of `_load_and_validate` / `_stage2_candidate` (explicitly
    authorized by R3-a), and the byte-exact comparison below.  Rule 4's blob
    comparison uses the DERIVED path with this function's `raw` (INV-3c).
    """
    shape, rel = _plan_arg_shape(plan_arg)
    if shape == "reject":
        return (False, "unaccepted spelling")

    try:
        main_repo = _rp.main_repo()
        main_common = _git_common_dir(main_repo)
        worktrees = _registered_worktrees(main_repo)
    except (OSError, RuntimeError, ValueError, SystemExit):
        return (False, "cannot resolve the registered worktree set")

    if shape == "absolute":
        # Exactly one candidate: the caller handed us an absolute spelling.
        # Which worktree it belongs to is decided by the bytes it holds.
        # The path is NOT re-resolved here: `path` is the very candidate that
        # `_stage1_load` already read (R3-a forbids a second open/read/resolve
        # of the caller spelling), and the lexical form is enough to locate the
        # registered worktree root that contains it.
        for wt_root in worktrees:
            wt_root = Path(wt_root).resolve()
            try:
                lexical = Path(os.path.normpath(os.path.abspath(path)))
                if not lexical.is_relative_to(wt_root):
                    continue
            except (OSError, RuntimeError, ValueError):
                continue
            try:
                candidate_rel = lexical.relative_to(wt_root).as_posix()
            except (OSError, RuntimeError, ValueError):
                continue
            # R3-c: the raw spelling must be the un-folded canonical absolute
            # form, so a `..`/`.` component can never hide a symlinked parent.
            if os.path.normpath(plan_arg) != plan_arg:
                return (False, "unaccepted spelling")
            candidate_raw = _stage2_candidate(plan_arg, shape, candidate_rel, wt_root, main_common)
            if candidate_raw is None:
                continue
            # Accepted == the caller's spelling names exactly the derived form.
            if str((wt_root / candidate_rel)) != plan_arg:
                return (False, "unaccepted spelling")
            return (True, "")
        return (False, "no trusted candidate")

    # Canonical relative shape: candidate discovery across every registered
    # worktree.  `_resolve_plan_path()` is deliberately NOT used: it anchors
    # relative paths at `main_repo()`, while the plan file is committed only on
    # the integration branch (E13's first-introduction case), so that spelling
    # resolves to a non-existent main-repo path and is undeployable.  The file
    # used is the canonical relative contract spelling, which maps to the
    # worktree the candidate discovery selects — never to the CWD.
    trusted = []
    for wt_root in worktrees:
        try:
            wt_root = Path(wt_root).resolve()
            candidate_raw = _stage2_candidate(plan_arg, shape, rel, wt_root, main_common)
        except (OSError, RuntimeError, ValueError, SystemExit):
            continue
        if candidate_raw is not None:
            trusted.append((wt_root, candidate_raw))

    if not trusted:
        return (False, "no trusted candidate")
    if len(trusted) > 1:
        return (False, "trusted candidate not unique")
    # The accepted bytes ARE the trusted candidate's bytes.  R3-c requires the
    # caller's RAW spelling to equal the canonical relative form byte for byte
    # — that spelling never depends on a worktree root or on the CWD.
    wt_root, candidate_raw = trusted[0]
    if plan_arg != rel:
        return (False, "unaccepted spelling")
    return (True, "")


def _lint_exemption_source_is_trusted(plan_arg: str, data: dict, raw: bytes):
    """Bind a merge-only lint exemption to the integration branch's committed
    blob; returns ``(trusted, witness)`` (the witness is empty when trusted).

    The audit authority is the committed blob on ``git.base_branch`` — not any
    checkout's index (known trap 4).  Everything is decided on the raw bytes
    that ``_load_and_validate`` already parsed; nothing is re-read here except
    a relative form's other candidates, each at most once (INV-3b/3c).

    rev8 direction (unchanged since): the trusted path is DERIVED by the
    engine.  Checking the caller's spelling harder cannot close this hole —
    three successive implementations (outside alias, parent-directory symlink,
    ``..``-cancelled symlink hop) were all the same root cause exposed through a
    different spelling, because ``_lexical_absolute()`` folds ``hop/..``
    lexically and the symlinked component never reaches any checked path.  The
    witness vocabulary is closed and generated from that judgement itself:
    ``no trusted candidate`` / ``trusted candidate not unique`` /
    ``unaccepted spelling``; a caller can never supply a witness string.
    """
    ok, witness = _trusted_candidate_raw(plan_arg, Path(plan_arg), data, raw)
    return (ok, witness)


def _require_converged(data: dict, repo: Path) -> None:
    """Fail-closed: every declared WP must be MERGED (and agree on plan_id)."""
    base = data["git"]["base_branch"]
    problems = []
    for wp_id, git_path in _status_git_paths(data, repo):
        wp = _wp_status_git(repo, base, git_path)
        if wp is None:
            problems.append("{}: status file not found on {} at {}".format(
                wp_id, base, git_path))
            continue
        state = wp.get("state")
        merged_commit = (wp.get("git") or {}).get("merged_commit")
        if not (state == "MERGED" and merged_commit):
            problems.append("{}: state={} (not MERGED)".format(wp_id, state))
            continue
        wp_plan_id = wp.get("plan_id")
        if wp_plan_id and wp_plan_id != data["plan_id"]:
            problems.append(
                "{}: plan_id={!r} does not match plan {!r}".format(
                    wp_id, wp_plan_id, data["plan_id"]
                )
            )
    if problems:
        for problem in problems:
            print("PLAN_FAIL: {}".format(problem), file=sys.stderr)
        raise SystemExit(RC_FAIL)


# ---------------------------------------------------------------------------
# Commit-discipline lint (freeze + finalize only; no review/consult/override
# "sync" commits) per WP.
# ---------------------------------------------------------------------------

def _wp_commit_discipline(repo: Path, target: str, base: str, git_path: str) -> dict:
    rng = "{}..{}".format(target, base)
    touching = _git(repo, "log", "--format=%H", rng, "--", git_path).split()
    freeze = _git(
        repo, "log", "--format=%H", "--diff-filter=A", rng, "--", git_path
    ).split()
    freeze_set = set(freeze)
    finalize = []
    sync = []
    for h in touching:
        if h in freeze_set:
            continue
        blob = _git_may_fail(repo, "show", "{}:{}".format(h, git_path))
        state = None
        if blob.returncode == 0:
            try:
                state = json.loads(blob.stdout).get("state")
            except json.JSONDecodeError:
                state = None
        if state == "MERGED":
            finalize.append(h)
        else:
            sync.append(h)
    return {"touching": touching, "freeze": freeze, "finalize": finalize, "sync": sync}


def _lint_report(data: dict, repo: Path) -> tuple:
    """Return (dirty, [lines]) for the whole plan. Read-only."""
    base = data["git"]["base_branch"]
    target = data["git"]["target_branch"]
    dirty = False
    lines = []
    for wp_id, git_path in _status_git_paths(data, repo):
        d = _wp_commit_discipline(repo, target, base, git_path)
        problems = []
        if len(d["freeze"]) != 1:
            problems.append("freeze commit x{} (expected 1)".format(len(d["freeze"])))
        if len(d["finalize"]) != 1:
            problems.append("finalize commit x{} (expected 1)".format(len(d["finalize"])))
        if d["sync"]:
            subs = []
            for h in d["sync"]:
                subj = _git(repo, "log", "-1", "--format=%s", h)
                subs.append("{} {}".format(h[:8], subj))
            problems.append(
                "{} status-sync commit(s): {}".format(len(d["sync"]), "; ".join(subs))
            )
        if problems:
            dirty = True
            lines.append("PLAN_LINT: wp {} DIRTY: {}".format(wp_id, "; ".join(problems)))
        else:
            lines.append("PLAN_LINT: wp {} clean (freeze + finalize)".format(wp_id))
    return dirty, lines


# ---------------------------------------------------------------------------
# Sub-actions
# ---------------------------------------------------------------------------

def cmd_check(plan_arg: str) -> int:
    data, path, _raw = _load_and_validate(plan_arg)
    repo = _rp.main_repo()
    base = data["git"]["base_branch"]
    target = data["git"]["target_branch"]

    print(
        "PLAN_CHECK plan_id={} state={} base_branch={} target_branch={}".format(
            data["plan_id"], data["state"], base, target
        )
    )

    wp_ids = data.get("work_packages", [])
    if not wp_ids:
        print("PLAN_CHECK: no work packages declared")
        return RC_STOP

    pending = 0
    for wp_id, git_path in _status_git_paths(data, repo):
        wp = _wp_status_git(repo, base, git_path)
        if wp is None:
            print("PLAN_CHECK: wp {} MISSING".format(wp_id))
            pending += 1
        elif wp.get("state") == "MERGED" and (wp.get("git") or {}).get("merged_commit"):
            print("PLAN_CHECK: wp {} MERGED".format(wp_id))
        else:
            print("PLAN_CHECK: wp {} state={} (not merged)".format(
                wp_id, wp.get("state")))
            pending += 1

    merge_done = False
    try:
        base_tip = _tip(repo, base)
        target_tip = _tip(repo, target)
        merge_done = _is_ancestor(repo, base_tip, target_tip)
    except ValueError as exc:
        print("PLAN_CHECK: {}".format(exc), file=sys.stderr)

    if merge_done:
        print("PLAN_CHECK: merge detected ({} is an ancestor of {})".format(
            base, target))
    else:
        print("PLAN_CHECK: merge NOT detected ({} not merged into {})".format(
            base, target))

    if pending == 0 and merge_done:
        print("PLAN_CHECK: converged")
        return RC_OK
    print(
        "PLAN_CHECK: not converged ({} WP(s) pending{}, merge {}done)".format(
            pending,
            " or " if pending and not merge_done else "",
            "" if merge_done else "not ",
        )
    )
    return RC_STOP


def cmd_lint(plan_arg: str) -> int:
    data, path, _raw = _load_and_validate(plan_arg)
    repo = _rp.main_repo()
    dirty, lines = _lint_report(data, repo)
    for line in lines:
        print(line)
    if dirty:
        print("PLAN_LINT: dirty")
        return RC_STOP
    print("PLAN_LINT: clean")
    return RC_OK


def cmd_lanes(plan_arg: str) -> int:
    """Read the plan + each WP's actual state from the integration branch and
    print the ready / blocked / done sets. Same-lane serialization is applied:
    at most one READY WP is reported per lane.

    Read-only (git `show` only). The ready computation is a pure function
    (`_lanes_ready`) evaluated over WP states read from git — the state is the
    only dynamic input; there is no clock / no network."""
    data, path, _raw = _load_and_validate(plan_arg)
    repo = _rp.main_repo()
    base = data["git"]["base_branch"]

    # Collect each WP's state from the integration branch tree.
    states = {}
    for wp_id, git_path in _status_git_paths(data, repo):
        wp = _wp_status_git(repo, base, git_path)
        state = wp.get("state") if isinstance(wp, dict) else None
        states[wp_id] = state

    norm = _normalize_work_packages(data.get("work_packages", []))
    result = _lanes_ready(data.get("work_packages", []), states)

    # Same-lane serialization: among READY WPs in a lane, only the first (in
    # declared order) may start now; the rest are reported as blocked-on-lane.
    ready_ids = set(result["ready"])
    claimed_lanes = set()
    ready_out = []
    lane_held = []  # (lane, [wp ids deferred because the lane is busy])
    for wp in norm:
        wp_id = wp["id"]
        if wp_id not in ready_ids:
            continue
        lane = wp["lane"]
        if lane in claimed_lanes:
            lane_held.append((wp_id, lane))
            continue
        claimed_lanes.add(lane)
        ready_out.append(wp_id)

    print("PLAN_LANES plan_id={} state={} base_branch={}".format(
        data["plan_id"], data["state"], base))

    print("READY:")
    if not ready_out:
        print("  (none)")
    for wp_id in ready_out:
        lane = next(wp["lane"] for wp in norm if wp["id"] == wp_id)
        print("  {} [lane={}]".format(wp_id, lane))

    print("BLOCKED:")
    blocked_lines = []
    for wp_id, deps in result["blocked"]:
        blocked_lines.append("  {} waiting on {}".format(wp_id, ", ".join(deps)))
    for wp_id, lane in lane_held:
        blocked_lines.append(
            "  {} waiting on lane {} (same-lane serialization)".format(wp_id, lane)
        )
    if not blocked_lines:
        print("  (none)")
    for line in blocked_lines:
        print(line)

    print("DONE:")
    if not result["done"]:
        print("  (none)")
    for wp_id in result["done"]:
        print("  {}".format(wp_id))

    return RC_OK


def cmd_merge(plan_arg: str) -> int:
    data, path, raw = _load_and_validate(plan_arg)
    repo = _rp.main_repo()

    base_branch = data["git"]["base_branch"]
    target_branch = data["git"]["target_branch"]
    state = data["state"]

    if state != "READY_TO_MERGE":
        print(
            "PLAN_FAIL: state must be READY_TO_MERGE (got {}); set it after every "
            "WP is MERGED".format(state),
            file=sys.stderr,
        )
        return RC_FAIL

    if _autonomy_stop("local_merge_no_ff"):
        print(
            "PLAN_STOP: autonomy requires human approval (local_merge_no_ff); "
            "set AGENTIC_AUTONOMY_APPROVE=1 after human approval",
            file=sys.stderr,
        )
        return RC_STOP

    # Fail-closed on evidence: every declared WP must actually be MERGED.
    _require_converged(data, repo)

    # Fail-closed on commit discipline.  A legal exemption waives only this one
    # finding, and only when the bytes actually parsed are bound to the
    # integration branch's committed canonical blob (see
    # _lint_exemption_source_is_trusted).
    dirty, lines = _lint_report(data, repo)
    if dirty:
        exemption = data.get("lint_exemption")
        if not _lint_exemption_is_legal(exemption):
            for line in lines:
                print(line, file=sys.stderr)
            print(
                "PLAN_FAIL: status-sync commits present; squash to freeze + finalize "
                "first (see `agentic plan lint`)",
                file=sys.stderr,
            )
            return RC_FAIL
        trusted, witness = _lint_exemption_source_is_trusted(plan_arg, data, raw)
        if not trusted:
            for line in lines:
                print(line, file=sys.stderr)
            print(
                "PLAN_FAIL: lint exemption source is untrusted ({}); the exemption "
                "must name the plan status file committed on the integration "
                "branch, either as its canonical absolute path or as the "
                "contract's canonical relative path".format(witness),
                file=sys.stderr,
            )
            return RC_FAIL
        print(
            "PLAN_LINT_EXEMPTION approver={} justification={}".format(
                exemption["approver"], exemption["justification"]
            )
        )

    # Everything below consults or mutates a checkout.  It MUST run in the
    # caller's current worktree (INV-3d) — never the physical-primary
    # checkout, which may be on another branch with unrelated user changes
    # (E14).  Refs-only queries above already ran against the shared main
    # repo; the current worktree must share that repo's resolved common dir.
    try:
        checkout = _rp.current_worktree()
        if _git_common_dir(checkout) != _git_common_dir(repo):
            print(
                "PLAN_FAIL: current worktree is not linked to the main repo "
                "(shared git-common-dir mismatch)",
                file=sys.stderr,
            )
            return RC_FAIL
    except (OSError, RuntimeError, ValueError, SystemExit):
        print("PLAN_FAIL: cannot resolve the current worktree", file=sys.stderr)
        return RC_FAIL

    current = _git(checkout, "branch", "--show-current")
    if current != target_branch:
        print(
            "PLAN_FAIL: must run on target branch {} (current: {})".format(
                target_branch, current
            ),
            file=sys.stderr,
        )
        return RC_FAIL

    base_tip = _tip(repo, base_branch)
    if _is_ancestor(repo, base_tip, _tip(repo, target_branch)):
        print(
            "PLAN_FAIL: {} already merged into {}; run `agentic plan finalize`".format(
                base_branch, target_branch
            ),
            file=sys.stderr,
        )
        return RC_FAIL

    proc = _git_may_fail(checkout, "merge", "--no-ff", "--no-edit", base_branch)
    if proc.returncode != 0:
        conflicted = _git_may_fail(checkout, "diff", "--name-only", "--diff-filter=U")
        if conflicted.returncode == 0 and conflicted.stdout.strip():
            print("PLAN_FAIL: merge conflicts in:", file=sys.stderr)
            for line in conflicted.stdout.splitlines():
                if line.strip():
                    print("    - {}".format(line.strip()), file=sys.stderr)
            print(
                "  resolve then: git -C {} merge --continue   (or abort: git merge --abort)".format(checkout),
                file=sys.stderr,
            )
        else:
            print("PLAN_FAIL: git merge --no-ff {} failed: {}".format(
                base_branch, proc.stderr.strip()), file=sys.stderr)
        return RC_FAIL

    merged_commit = _git(checkout, "rev-parse", "HEAD")
    print(
        "PLAN_MERGE_OK merged_commit={} base_branch={} into={}".format(
            merged_commit, base_branch, target_branch
        )
    )
    print("PLAN_MERGE_NEXT: run 'agentic plan finalize {}'".format(plan_arg))
    return RC_OK


def cmd_finalize(plan_arg: str) -> int:
    data, path, _raw = _load_and_validate(plan_arg)
    repo = _rp.main_repo()

    base_branch = data["git"]["base_branch"]
    target_branch = data["git"]["target_branch"]
    state = data["state"]

    if state not in {"READY_TO_MERGE", "MERGED"}:
        print(
            "PLAN_FAIL: state must be READY_TO_MERGE or MERGED (got {})".format(state),
            file=sys.stderr,
        )
        return RC_FAIL

    if _autonomy_stop("finalize_merge"):
        print(
            "PLAN_STOP: autonomy requires human approval (finalize_merge); "
            "set AGENTIC_AUTONOMY_APPROVE=1 after human approval",
            file=sys.stderr,
        )
        return RC_STOP

    # Fail-closed on evidence: all WPs MERGED + the integration branch must
    # actually be merged into the target (never stamp a merge that didn't happen).
    _require_converged(data, repo)

    try:
        base_tip = _tip(repo, base_branch)
        target_tip = _tip(repo, target_branch)
    except ValueError as exc:
        print("PLAN_FAIL: {}".format(exc), file=sys.stderr)
        return RC_FAIL

    if not _is_ancestor(repo, base_tip, target_tip):
        print(
            "PLAN_FAIL: merge not detected ({} tip {} is not an ancestor of {} {})".format(
                base_branch, base_tip, target_branch, target_tip
            ),
            file=sys.stderr,
        )
        return RC_FAIL

    candidates = _resolve_plan_merge_commit(repo, base_tip, target_tip)

    # Idempotency: an already-finalized plan must resolve to the same commit.
    recorded = (data.get("git") or {}).get("merged_commit")
    if state == "MERGED" and recorded:
        if len(candidates) != 1:
            print(
                "PLAN_FAIL: cannot uniquely resolve plan merge commit (found {})".format(
                    len(candidates)
                ),
                file=sys.stderr,
            )
            return RC_FAIL
        if recorded != candidates[0]:
            print(
                "PLAN_FAIL: recorded merged_commit {} != resolved {}".format(
                    recorded, candidates[0]
                ),
                file=sys.stderr,
            )
            return RC_FAIL
        print("PLAN_FINALIZE_OK merged_commit={} (already finalized)".format(recorded))
        return RC_OK

    if len(candidates) != 1:
        print(
            "PLAN_FAIL: cannot uniquely resolve plan merge commit for {} tip {} "
            "(found {})".format(base_branch, base_tip, len(candidates)),
            file=sys.stderr,
        )
        return RC_FAIL

    merged_commit = candidates[0]

    # Atomic write + self-validation.
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_data = json.loads(json.dumps(data))  # deep copy
    new_data["state"] = "MERGED"
    new_data["git"] = dict(new_data.get("git", {}))
    new_data["git"]["merged_commit"] = merged_commit
    new_data["timestamps"] = dict(new_data.get("timestamps", {}))
    new_data["timestamps"]["updated_at"] = updated_at

    _validate_or_raise(new_data, path.name)
    tmp = path.with_name(path.name + ".tmp-{}".format(os.getpid()))
    try:
        tmp.write_text(json.dumps(new_data, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()

    print("PLAN_FINALIZE_OK merged_commit={} plan_id={}".format(
        merged_commit, data["plan_id"]))
    return RC_OK


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentic plan")
    sub = parser.add_subparsers(dest="action")

    p_check = sub.add_parser("check", help="report WP + merge convergence (read-only)")
    p_check.add_argument("plan_status", help="plan.status.json path")

    p_lint = sub.add_parser("lint", help="enforce freeze + finalize status discipline")
    p_lint.add_argument("plan_status", help="plan.status.json path")

    p_lanes = sub.add_parser("lanes", help="compute READY/BLOCKED/DONE from deps + lanes")
    p_lanes.add_argument("plan_status", help="plan.status.json path")

    p_merge = sub.add_parser("merge", help="single no-ff merge of the plan into target")
    p_merge.add_argument("plan_status", help="plan.status.json path")

    p_finalize = sub.add_parser("finalize", help="stamp state=MERGED + merged_commit")
    p_finalize.add_argument("plan_status", help="plan.status.json path")

    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.action == "check":
        return cmd_check(args.plan_status)
    if args.action == "lint":
        return cmd_lint(args.plan_status)
    if args.action == "lanes":
        return cmd_lanes(args.plan_status)
    if args.action == "merge":
        return cmd_merge(args.plan_status)
    if args.action == "finalize":
        return cmd_finalize(args.plan_status)

    parser.print_help(sys.stderr)
    return RC_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
