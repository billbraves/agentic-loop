"""WP-27 / B17: preflight reads the LIVE main-repo status copy, not the worktree.

B17 (defect): ``preflight.sh:9`` used a bare ``status_file=$1``. A relative
status path then resolved against ``cwd``, which the operating contract (§4.1)
forces to be the *secondary worktree*. The gate therefore judged the
git-tracked historical snapshot inside the worktree instead of the live
main-repo status — and that affected every later consumer of ``$status_file``:
``state``, ``git.branch``/``git.worktree``, and the path handed to
``dispatch_lint.sh`` (which in turn owns ``scope.allowed_paths`` and ``risk.*``).

The fix anchors a relative path to the MAIN repo root (the same ``case`` form
as ``dispatch_lint.sh:26-29``), honours an absolute path unchanged, and refuses
a status path that resolves inside a linked worktree via the single-authority
predicate ``agentic_loop.gate.path_is_in_worktree`` (WP-19).

Each negative assertion below carries the WP-27 oracle's three items:

1. **positive reachability control** — the same fixture produces the passing
   verdict when the authoritative input is supplied;
2. **cause-specific witness** — a file:line reference to the single ``print``
   in the authoritative source (or a differential pair when two reasons could
   print the same wording), so the failure is attributable to THIS cause;
3. **forbidden mutation** — reverting the ``:9`` anchoring to a bare
   ``status_file=$1`` turns the divergence test red; restoring it returns green
   (exercised end-to-end in ``test_bare_status_assignment_reverts_to_worktree``).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"
WRAPPERS_DIR = PKG_SRC / "agentic_loop" / "wrappers"
PREFLIGHT_SH = WRAPPERS_DIR / "preflight.sh"

ITER = "wp27-preflight-source"
PLAN_DIR = Path("docs/plans") / ITER

BRIEF = """# WP brief fixture

## Allowed and forbidden paths

- allowed: docs/

## Acceptance tests

- run the tests

## Completion definition

- done
"""

# The authoritative ``print`` sites this test suite is anchored to. Asserting on
# the full emitted line (not just a substring) keeps the witness cause-specific.
# preflight.sh emits its verdicts to stderr; the final PASS line goes to stdout.
STATE_NOT_EXECUTABLE = "PREFLIGHT_FAIL: state "

# Passing risk baseline: every §4.1 risk flag false. dispatch_lint.sh refuses
# dispatch when any flag is True (dispatch_lint.sh:108-126); these differentials
# keep the non-tested risk dimension at this baseline so the two refusal causes
# cannot mask one another (B19).
PASSING_RISK = {
    "production_writes_authorized": False,
    "network_authorized": False,
    "real_notifications_authorized": False,
    "irreversible_actions_authorized": False,
}

# Cause-specific refusal witnesses: the exact substrings printed by
# dispatch_lint.sh, which preflight.sh wraps as
# ``PREFLIGHT_FAIL: dispatch-lint DISPATCH_LINT_FAIL: <reason>``. The two are
# distinct from each other and from a ``state … is not executable`` refusal.
SCOPE_REFUSAL_WITNESS = "scope.allowed_paths is empty"  # dispatch_lint.sh:136
RISK_REFUSAL_WITNESS = "risk.network_authorized authorized"  # dispatch_lint.sh:120


@pytest.fixture
def session_env():
    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = "wp27-preflight-source-test"
    env["AGENTIC_PYTHON"] = sys.executable
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return env


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _head(repo: Path) -> str:
    return _run_git(repo, "rev-parse", "HEAD").stdout.strip()


def _default_branch(repo: Path) -> str:
    return _run_git(repo, "branch", "--show-current").stdout.strip()


def _status(
    repo: Path,
    wp: str,
    *,
    branch: str,
    worktree: str,
    state: str = "APPROVED",
    allowed_paths: list[str] | None = None,
    risk: dict | None = None,
) -> dict:
    if allowed_paths is None:
        allowed_paths = ["docs/"]
    if risk is None:
        risk = {
            "production_writes_authorized": False,
            "network_authorized": False,
            "real_notifications_authorized": False,
            "irreversible_actions_authorized": False,
        }
    return {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": wp,
        "iteration_id": ITER,
        "phase": "P1",
        "state": state,
        "role": "Developer",
        "executor": {"tool": "kimi-cli", "session": ""},
        "orchestrator": {"tool": "claude-code", "session": ""},
        "reviewer": {"tool": "claude-code", "session": ""},
        "git": {
            "base_branch": _default_branch(repo),
            "base_commit": _head(repo),
            "branch": branch,
            "worktree": worktree,
            "commit": "",
        },
        "scope": {"allowed_paths": allowed_paths, "forbidden_paths": [".env"]},
        "risk": risk,
        "evidence": {"changed_files": [], "tests": [], "artifacts": []},
        "review": {},
        "consult": {},
        "timestamps": {"created_at": "2026-09-16T00:00:00Z"},
    }


def _make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "init")
    return repo


def _commit_all(repo: Path, message: str) -> None:
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", message)


def _add_worktree(repo: Path, wt: Path, branch: str) -> None:
    _run_git(repo, "worktree", "add", "-q", "-b", branch, str(wt))


def _write_status_and_brief(repo: Path, wp: str, status: dict) -> Path:
    brief = repo / PLAN_DIR / f"{wp}-brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(BRIEF, encoding="utf-8")
    # WP-01: the status-source predicate resolves the authoritative branch from
    # the PLAN status in this same plan directory, so every fixture must carry
    # one. It declares the PRIMARY repo's current branch: that is the checkout
    # holding the authoritative copy in these fixtures, which is exactly the
    # layout the tests exercise. Without it the predicate would fail closed
    # (unresolved) and the main-repo control paths could never pass.
    _write_plan_status(repo)
    status_path = repo / PLAN_DIR / f"{wp}.status.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status_path


def _write_plan_status(repo: Path) -> Path:
    """Declare the authoritative branch as the primary repo's current branch."""
    branch = _default_branch(repo)
    plan_path = repo / PLAN_DIR / "PLAN-01.status.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "agentic-plan-status/v1",
                "plan_id": "PLAN-01",
                "git": {"base_branch": branch, "target_branch": "main"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return plan_path


def _run_preflight(
    wt: Path, status_arg: str, env: dict, script: Path = PREFLIGHT_SH
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), status_arg],
        cwd=wt,
        capture_output=True,
        text=True,
        env=env,
    )


def _diverged_fixture(
    tmp_path: Path,
    *,
    wp: str,
    worktree_state: str,
    worktree_allowed: list[str] | None,
    worktree_risk: dict | None,
) -> dict:
    """Main repo + secondary worktree with a DIVERGENT status copy in each.

    The main-repo copy is always the valid, executable ``APPROVED`` status
    (non-empty scope, all risk flags false). The worktree copy is the divergent
    snapshot a buggy preflight used to read. Returns every path the assertions
    need plus the relative status path (what the developer actually passes).
    """
    repo = _make_repo(tmp_path)
    branch = f"feature/{wp.lower()}"
    wt = tmp_path / wp.lower()

    main_status = _status(
        repo, wp, branch=branch, worktree=str(wt), state="APPROVED"
    )
    main_status_path = _write_status_and_brief(repo, wp, main_status)
    _commit_all(repo, f"freeze {wp}")

    _add_worktree(repo, wt, branch)

    # Divergent copy lives only on the worktree branch (what old preflight read).
    wt_status = _status(
        repo,
        wp,
        branch=branch,
        worktree=str(wt),
        state=worktree_state,
        allowed_paths=worktree_allowed,
        risk=worktree_risk,
    )
    wt_status_path = wt / PLAN_DIR / f"{wp}.status.json"
    wt_status_path.write_text(json.dumps(wt_status, indent=2), encoding="utf-8")
    _commit_all(wt, f"{wp} divergent worktree copy")

    return {
        "repo": repo,
        "wt": wt,
        "main_status_path": main_status_path,
        "wt_status_path": wt_status_path,
        "rel": str(PLAN_DIR / f"{wp}.status.json"),
    }


def _rewrite_main_status(fx: dict, *, allowed_paths=None, risk=None) -> None:
    """Flip a field on the LIVE main-repo copy in place (it stays tracked)."""
    status = json.loads(fx["main_status_path"].read_text(encoding="utf-8"))
    if allowed_paths is not None:
        status["scope"]["allowed_paths"] = allowed_paths
    if risk is not None:
        status["risk"] = risk
    fx["main_status_path"].write_text(json.dumps(status, indent=2), encoding="utf-8")


def _main_tight_fixture(
    tmp_path: Path,
    *,
    wp: str,
    main_allowed: list[str],
    main_risk: dict,
) -> dict:
    """Main-repo copy carries the field(s) under test; worktree copy permissive.

    The MAIN copy is the tight one (potentially refused by dispatch_lint.sh);
    the worktree copy is always the passing shape (APPROVED, ``docs/`` allowed,
    every risk flag false). A correct preflight reads the main copy and therefore
    fails on the tight field; a buggy preflight reading the worktree copy would
    pass. Returns the same shape as ``_diverged_fixture``.
    """
    repo = _make_repo(tmp_path, name=f"repo-{wp.lower()}")
    branch = f"feature/{wp.lower()}"
    wt = tmp_path / wp.lower()

    main_status = _status(
        repo,
        wp,
        branch=branch,
        worktree=str(wt),
        state="APPROVED",
        allowed_paths=main_allowed,
        risk=main_risk,
    )
    main_status_path = _write_status_and_brief(repo, wp, main_status)
    _commit_all(repo, f"freeze {wp}")

    _add_worktree(repo, wt, branch)

    wt_status = _status(
        repo,
        wp,
        branch=branch,
        worktree=str(wt),
        state="APPROVED",
        allowed_paths=["docs/"],
        risk=PASSING_RISK,
    )
    wt_status_path = wt / PLAN_DIR / f"{wp}.status.json"
    wt_status_path.write_text(json.dumps(wt_status, indent=2), encoding="utf-8")
    _commit_all(wt, f"{wp} permissive worktree copy")

    return {
        "repo": repo,
        "wt": wt,
        "main_status_path": main_status_path,
        "wt_status_path": wt_status_path,
        "rel": str(PLAN_DIR / f"{wp}.status.json"),
    }


# ---------------------------------------------------------------------------
# Core B17 differential pairs: a RELATIVE status path must follow the MAIN copy
# ---------------------------------------------------------------------------


def test_state_divergence_follows_main_repo_copy(tmp_path, session_env) -> None:
    """main=APPROVED (executable) vs worktree=BLOCKED (not executable).

    A relative status path from inside the worktree must judge the MAIN copy and
    pass; the worktree copy's BLOCKED state must be invisible.

    Oracle:
    - positive control: same fixture, same call — PREFLIGHT_PASS on stdout.
    - witness: the worktree copy is BLOCKED, which preflight.sh:96-102 rejects
      with ``PREFLIGHT_FAIL: state BLOCKED is not executable``; asserting PASS
      proves the BLOCKED worktree copy was never read. The PASS line's
      ``status=`` must name the MAIN copy, not the worktree copy.
    - forbidden mutation: ``test_bare_status_assignment_reverts_to_worktree``
      reverts ``:9`` to a bare assignment and shows this exact fixture going red.
    """
    fx = _diverged_fixture(
        tmp_path,
        wp="WP-STATE",
        worktree_state="BLOCKED",
        worktree_allowed=["docs/"],
        worktree_risk=None,
    )

    res = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "PREFLIGHT_PASS" in res.stdout
    # Cause-specific: the verdict's status field is the anchored MAIN copy.
    assert f"status={fx['main_status_path']}" in res.stdout
    assert str(fx["wt_status_path"]) not in res.stdout


def test_state_divergence_opposite_direction_fails_on_main(tmp_path, session_env) -> None:
    """main=DRAFT (not executable) vs worktree=APPROVED (executable).

    The reverse differential pair: the gate must FAIL because the MAIN copy is
    DRAFT, even though the worktree copy would have passed.

    Oracle:
    - positive control: main=APPROVED / worktree=BLOCKED passes (the test above).
    - witness: ``PREFLIGHT_FAIL: state DRAFT is not executable`` (preflight.sh:99);
      the flip is exactly the worktree copy's APPROVED -> DRAFT, so red/green
      inverts when the authoritative input flips.
    - forbidden mutation: reverting ``:9`` makes this test go GREEN by reading
      the worktree's APPROVED copy — the same mutation that reds the main test.
    """
    fx = _diverged_fixture(
        tmp_path,
        wp="WP-STATE-REV",
        worktree_state="APPROVED",
        worktree_allowed=["docs/"],
        worktree_risk=None,
    )
    # Overwrite the MAIN copy with DRAFT (validator allows DRAFT; preflight does not).
    main_draft = _status(
        fx["repo"],
        "WP-STATE-REV",
        branch="feature/wp-state-rev",
        worktree=str(fx["wt"]),
        state="DRAFT",
    )
    fx["main_status_path"].write_text(json.dumps(main_draft, indent=2), encoding="utf-8")
    _commit_all(fx["repo"], "main copy -> DRAFT")

    res = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert f"{STATE_NOT_EXECUTABLE}DRAFT is not executable" in res.stderr


def test_scope_and_risk_divergence_follow_main_copy(tmp_path, session_env) -> None:
    """scope.allowed_paths / risk.* tightened ONLY in the worktree copy.

    This is the "mirror image" half of the B17 differential: the worktree copy
    carries a BAD value (``scope.allowed_paths=[]`` and
    ``risk.network_authorized=True`` — either alone would make
    dispatch_lint.sh:135 / :119 refuse), while the main copy is permissive.
    Requiring PASS proves the worktree copy's bad values are never read. It
    does NOT prove that a main-copy tight value binds — that half is covered by
    ``test_scope_tightened_only_in_main_copy_fails`` and
    ``test_risk_tightened_only_in_main_copy_fails`` (this mirror image holds
    even when scope/risk are never consumed at all).

    Oracle:
    - positive control: PREFLIGHT_PASS with ``status=<main copy>``.
    - witness: the worktree copy carries ``scope.allowed_paths=[]`` and
      ``risk.network_authorized=True`` — either would make dispatch_lint.sh:135 /
      :119 fail; asserting PASS proves they were not read. Asserting
      ``status=<main copy>`` is the cause-specific witness.
    - forbidden mutation: reverting ``:9`` removes the ``status=`` anchoring and
      this assertion goes red (the PASS line no longer names the main copy).
    """
    divergent_risk = {
        "production_writes_authorized": False,
        "network_authorized": True,
        "real_notifications_authorized": False,
        "irreversible_actions_authorized": False,
    }
    fx = _diverged_fixture(
        tmp_path,
        wp="WP-SCOPE-RISK",
        worktree_state="APPROVED",
        worktree_allowed=[],
        worktree_risk=divergent_risk,
    )

    res = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "PREFLIGHT_PASS" in res.stdout
    assert f"status={fx['main_status_path']}" in res.stdout
    assert str(fx["wt_status_path"]) not in res.stdout


# ---------------------------------------------------------------------------
# scope / risk differentials: tightening ONLY the main copy must bind (FAIL)
# ---------------------------------------------------------------------------


def test_scope_tightened_only_in_main_copy_fails(tmp_path, session_env) -> None:
    """main scope.allowed_paths=[] (refused) vs worktree copy permissive.

    The correct direction of the scope differential: tighten ``allowed_paths``
    ONLY in the main copy and leave the worktree copy permissive. A buggy
    preflight that read the worktree copy would pass; requiring FAIL proves the
    main copy's tight value binds.

    Oracle:
    - positive control: flip ONLY the main copy's ``allowed_paths`` back to
      ``["docs/"]`` on the same fixture and require PREFLIGHT_PASS.
    - witness: ``scope.allowed_paths is empty`` — the single print point at
      dispatch_lint.sh:136, distinct from the risk witness (dispatch_lint.sh:120)
      and from a ``state … is not executable`` refusal.
    - removal mutation: test_dispatch_lint_removal_turns_scope_and_risk_green
      deletes the dispatch_lint call and this scenario flips to PASS.
    """
    fx = _main_tight_fixture(
        tmp_path, wp="WP-SCOPE-TIGHT", main_allowed=[], main_risk=PASSING_RISK
    )

    res = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert SCOPE_REFUSAL_WITNESS in res.stderr

    # Positive control: flip ONLY the main allowed_paths back to passing.
    _rewrite_main_status(fx, allowed_paths=["docs/"])
    res_ok = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res_ok.returncode == 0, (res_ok.returncode, res_ok.stdout, res_ok.stderr)
    assert "PREFLIGHT_PASS" in res_ok.stdout
    assert f"status={fx['main_status_path']}" in res_ok.stdout


def test_risk_tightened_only_in_main_copy_fails(tmp_path, session_env) -> None:
    """main risk.network_authorized=True (refused) vs worktree copy permissive.

    The correct direction of the risk differential: tighten a ``risk.*`` value
    ONLY in the main copy and leave the worktree copy permissive (and leave the
    main scope passing), so a buggy preflight reading the worktree copy would
    pass; requiring FAIL proves the main copy's tight value binds.

    Oracle:
    - positive control: flip ONLY the main copy's ``risk.network_authorized``
      back to ``False`` on the same fixture and require PREFLIGHT_PASS.
    - witness: ``risk.network_authorized authorized`` — the single print point
      at dispatch_lint.sh:120, distinct from the scope witness
      (dispatch_lint.sh:136) and from a ``state … is not executable`` refusal.
    - removal mutation: test_dispatch_lint_removal_turns_scope_and_risk_green
      deletes the dispatch_lint call and this scenario flips to PASS.
    """
    fx = _main_tight_fixture(
        tmp_path,
        wp="WP-RISK-TIGHT",
        main_allowed=["docs/"],
        main_risk={**PASSING_RISK, "network_authorized": True},
    )

    res = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert RISK_REFUSAL_WITNESS in res.stderr

    # Positive control: flip ONLY the main risk flag back to passing.
    _rewrite_main_status(fx, risk=PASSING_RISK)
    res_ok = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res_ok.returncode == 0, (res_ok.returncode, res_ok.stdout, res_ok.stderr)
    assert "PREFLIGHT_PASS" in res_ok.stdout
    assert f"status={fx['main_status_path']}" in res_ok.stdout


# ---------------------------------------------------------------------------
# Worktree-local status copy must be REFUSED (fail-closed)
# ---------------------------------------------------------------------------


def test_absolute_worktree_status_path_is_refused(tmp_path, session_env) -> None:
    """An ABSOLUTE worktree-local status path is refused before any field is read.

    Oracle:
    - positive control: same fixture, RELATIVE path -> PASS (the main copy is
      read). This is the flip: only the input path changes.
    - witness: the full ``PREFLIGHT_FAIL: status file resolves inside a worktree
      ... (single source of truth)`` line from preflight.sh:48 — the only place
      this wording is printed, so no differential pair is needed.
    - forbidden mutation: deleting the ``path_is_in_worktree`` refusal block
      would turn this red (the worktree copy would be validated/read instead).
    """
    fx = _diverged_fixture(
        tmp_path,
        wp="WP-REFUSE",
        worktree_state="APPROVED",
        worktree_allowed=[],
        worktree_risk=None,
    )

    # Positive control (same fixture, authoritative input = relative path -> main).
    res_ok = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res_ok.returncode == 0, (res_ok.returncode, res_ok.stdout, res_ok.stderr)
    assert f"status={fx['main_status_path']}" in res_ok.stdout

    # Absolute worktree copy -> refused.
    res = _run_preflight(fx["wt"], str(fx["wt_status_path"]), session_env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert res.stderr.strip() == (
        "PREFLIGHT_FAIL: status file resolves inside a worktree "
        f"({fx['wt_status_path']}); pass the main-repo copy (single source of truth)"
    )


# ---------------------------------------------------------------------------
# Absolute MAIN-repo status path must be honoured unchanged
# ---------------------------------------------------------------------------


def test_absolute_main_repo_status_path_is_honoured_unchanged(
    tmp_path, session_env
) -> None:
    repo = _make_repo(tmp_path)
    branch = "feature/wp-abs"
    wt = tmp_path / "wp-abs"
    status = _status(repo, "WP-ABS", branch=branch, worktree=str(wt))
    main_status_path = _write_status_and_brief(repo, "WP-ABS", status)
    _commit_all(repo, "freeze WP-ABS")
    _add_worktree(repo, wt, branch)

    res = _run_preflight(wt, str(main_status_path), session_env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "PREFLIGHT_PASS" in res.stdout
    assert f"status={main_status_path}" in res.stdout


# ---------------------------------------------------------------------------
# Forbidden mutation: reverting ``:9`` to a bare assignment goes red
# ---------------------------------------------------------------------------


def test_bare_status_assignment_reverts_to_worktree(tmp_path, session_env) -> None:
    """Oracle item 3, exercised end-to-end without touching the real script.

    Copy the whole wrappers dir to a scratch dir, revert the anchoring ``case``
    (preflight.sh:32-35) back to the bare ``status_file=$status_arg``, and show
    the state-divergence fixture goes RED under the mutated copy while the real
    script stays GREEN. The scratch copy is removed, leaving the worktree clean.
    """
    fx = _diverged_fixture(
        tmp_path,
        wp="WP-MUTATE",
        worktree_state="BLOCKED",
        worktree_allowed=["docs/"],
        worktree_risk=None,
    )

    # Real script: green.
    res_real = _run_preflight(fx["wt"], fx["rel"], session_env)
    assert res_real.returncode == 0, (res_real.returncode, res_real.stdout, res_real.stderr)
    assert f"status={fx['main_status_path']}" in res_real.stdout

    # Mutated copy in a scratch dir (sibling wrappers resolve via dirname $0).
    # Reproduce the ORIGINAL B17 defect faithfully: bare assignment AND no
    # worktree refusal (the refusal is part of the same fix, so leaving it in
    # would stop the relative path before the anchoring divergence is reached).
    scratch = tmp_path / "mutated-wrappers"
    shutil.copytree(WRAPPERS_DIR, scratch)
    mutated_preflight = scratch / "preflight.sh"
    text = mutated_preflight.read_text(encoding="utf-8")

    # Replace the whole B17 block (B17 comment .. refusal closing ``fi``) with
    # the bare assignment, so the mutated script is exactly the pre-fix shape.
    region_start = text.index("# B17 (WP-27)")
    # The refusal block's closing ``fi`` is the line whose strip() == "fi"
    # following the refusal ``if``; a plain substring search would instead hit
    # the "fi" inside "single source of truth" on the echo line above it.
    lines = text.splitlines()
    refusal_if_line = next(
        i for i, line in enumerate(lines) if 'if [[ "$wt_verdict" != "MAIN" ]]' in line
    )
    close_fi_line = next(
        i for i in range(refusal_if_line + 1, len(lines)) if lines[i].strip() == "fi"
    )
    prefix_len = sum(len(line) + 1 for line in lines[:close_fi_line])
    region_end = prefix_len + len(lines[close_fi_line])
    region = text[region_start:region_end]
    mutated = text.replace(
        region,
        'status_file="$status_arg"  # forbidden mutation: bare assignment, no refusal (reverts B17 fix)',
    )
    mutated_preflight.write_text(mutated, encoding="utf-8")

    res_mut = _run_preflight(
        fx["wt"], fx["rel"], session_env, script=mutated_preflight
    )
    # The mutated copy reads the worktree's BLOCKED copy and fails the state gate.
    assert res_mut.returncode == 2, (res_mut.returncode, res_mut.stdout, res_mut.stderr)
    assert "state BLOCKED is not executable" in res_mut.stderr

    # Clean up the scratch copy; the authoritative script is untouched.
    shutil.rmtree(scratch)
    assert PREFLIGHT_SH.read_text(encoding="utf-8") != mutated


def test_dispatch_lint_removal_turns_scope_and_risk_green(tmp_path, session_env) -> None:
    """Oracle item 3 for both new differentials, end-to-end.

    Delete the whole ``dispatch_lint.sh`` invocation (preflight.sh:120) on a
    scratch copytree. The scope-tight and the risk-tight scenarios then each
    flip from FAIL to PASS — i.e. ``test_scope_tightened_only_in_main_copy_fails``
    and ``test_risk_tightened_only_in_main_copy_fails`` would each go red under
    this mutation, independently. The authoritative script is untouched: its
    sha256 is byte-identical before and after.
    """
    scope_fx = _main_tight_fixture(
        tmp_path, wp="WP-SCOPE-MUT", main_allowed=[], main_risk=PASSING_RISK
    )
    risk_fx = _main_tight_fixture(
        tmp_path,
        wp="WP-RISK-MUT",
        main_allowed=["docs/"],
        main_risk={**PASSING_RISK, "network_authorized": True},
    )

    # Real script: each tight copy is refused by its own distinct cause.
    res_scope_real = _run_preflight(scope_fx["wt"], scope_fx["rel"], session_env)
    assert res_scope_real.returncode == 2, (
        res_scope_real.returncode, res_scope_real.stdout, res_scope_real.stderr
    )
    assert SCOPE_REFUSAL_WITNESS in res_scope_real.stderr
    assert RISK_REFUSAL_WITNESS not in res_scope_real.stderr

    res_risk_real = _run_preflight(risk_fx["wt"], risk_fx["rel"], session_env)
    assert res_risk_real.returncode == 2, (
        res_risk_real.returncode, res_risk_real.stdout, res_risk_real.stderr
    )
    assert RISK_REFUSAL_WITNESS in res_risk_real.stderr
    assert SCOPE_REFUSAL_WITNESS not in res_risk_real.stderr

    live_before = PREFLIGHT_SH.read_bytes()

    scratch = tmp_path / "mutated-wrappers"
    shutil.copytree(WRAPPERS_DIR, scratch)
    mutated_preflight = scratch / "preflight.sh"
    text = mutated_preflight.read_text(encoding="utf-8")

    # Delete the whole dispatch_lint invocation block (preflight.sh:120-123),
    # leaving the "MUTATION" marker in its place.
    lines = text.splitlines()
    if_line = next(
        i for i, line in enumerate(lines)
        if 'if ! lint_reason=$("$here/dispatch_lint.sh"' in line
    )
    fi_line = next(
        i for i in range(if_line + 1, len(lines)) if lines[i].strip() == "fi"
    )
    region = "\n".join(lines[if_line : fi_line + 1])
    mutated = text.replace(region, "# MUTATION: dispatch_lint call deleted entirely")
    assert mutated != text
    mutated_preflight.write_text(mutated, encoding="utf-8")

    # Under the mutation each tight scenario flips to PASS (the tests go red).
    res_scope_mut = _run_preflight(
        scope_fx["wt"], scope_fx["rel"], session_env, script=mutated_preflight
    )
    assert res_scope_mut.returncode == 0, (
        res_scope_mut.returncode, res_scope_mut.stdout, res_scope_mut.stderr
    )
    assert "PREFLIGHT_PASS" in res_scope_mut.stdout

    res_risk_mut = _run_preflight(
        risk_fx["wt"], risk_fx["rel"], session_env, script=mutated_preflight
    )
    assert res_risk_mut.returncode == 0, (
        res_risk_mut.returncode, res_risk_mut.stdout, res_risk_mut.stderr
    )
    assert "PREFLIGHT_PASS" in res_risk_mut.stdout

    # Clean up the scratch copy; the authoritative script is byte-identical.
    shutil.rmtree(scratch)
    assert PREFLIGHT_SH.read_bytes() == live_before
