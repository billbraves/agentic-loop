"""WP-19 / A4 + A7: preflight branch/worktree binding and main-repo tracked check.

A4 (field timing): a frozen (APPROVED) status legitimately carries EMPTY
``git.branch``/``git.worktree`` — the branch does not exist yet at freeze time.
preflight must treat empty as "not yet bound": back-fill from the live branch
with a ``PREFLIGHT_WARN`` and proceed. A NON-empty field that does not match
must still fail (the binding check must not be relaxed).

A7 (commit topology): the "status file must be tracked" check must query the
MAIN repo index — status is main-area live state (§4.1). When a WP is based on
a sibling, unmerged WP branch, its freeze commit is not an ancestor of the
worktree's branch, so the old worktree-local ``git ls-files`` misfired.

Uses real temporary git repos + real linked worktrees and the real
``preflight.sh`` (fail-closed behaviour exercised end-to-end).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _write_fixture_plan_status(status_path, repo, wp_id="WP-01",
                               iteration_id="fixture-iteration"):
    """WP-01: give the fixture's plan dir a PLAN status.

    The status-source predicate resolves the authoritative branch from the PLAN
    status sitting beside the judged file, so a plan dir with no plan in it is
    refused. ``base_branch`` must name the branch this repo ACTUALLY holds --
    a hardcoded "main" would not match a fixture parked on a feature branch.
    """
    import json as _json
    import subprocess as _sp
    held = _sp.run(["git", "branch", "--show-current"], cwd=repo,
                   capture_output=True, text=True).stdout.strip() or "main"
    (Path(status_path).parent / "PLAN-FIXTURE.status.json").write_text(
        _json.dumps({
            "schema_version": "agentic-plan-status/v1",
            "plan_id": "PLAN-FIXTURE",
            "iteration_id": iteration_id,
            "state": "ACTIVE",
            "title": "fixture plan",
            "git": {"base_branch": held, "target_branch": "main"},
            "work_packages": [wp_id],
            "timestamps": {"created_at": "2026-01-01T00:00:00Z",
                           "updated_at": "2026-01-01T00:00:00Z"},
        }, indent=2), encoding="utf-8")

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"
PREFLIGHT_SH = PKG_SRC / "agentic_loop" / "wrappers" / "preflight.sh"

ITER = "wp19-preflight"
PLAN_DIR = Path("docs/plans") / ITER

BRIEF = """# WP brief fixture

## Allowed and forbidden paths

- allowed: docs/

## Acceptance tests

- run the tests

## Completion definition

- done
"""


@pytest.fixture
def session_env():
    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = "wp19-preflight-test"
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
) -> dict:
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
        "scope": {"allowed_paths": ["docs/"], "forbidden_paths": [".env"]},
        "risk": {
            "production_writes_authorized": False,
            "network_authorized": False,
            "real_notifications_authorized": False,
            "irreversible_actions_authorized": False,
        },
        "evidence": {"changed_files": [], "tests": [], "artifacts": []},
        "review": {},
        "consult": {},
        "timestamps": {"created_at": "2026-09-14T00:00:00Z"},
    }


def _write_status_and_brief(repo: Path, wp: str, status: dict) -> Path:
    brief = repo / PLAN_DIR / f"{wp}-brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(BRIEF, encoding="utf-8")
    status_path = repo / PLAN_DIR / f"{wp}.status.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    _write_fixture_plan_status(status_path, repo)
    return status_path


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
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


def _add_worktree(repo: Path, wt: Path, branch: str, start: str | None = None) -> None:
    args = ["worktree", "add", "-q", "-b", branch, str(wt)]
    if start:
        args.append(start)
    _run_git(repo, *args)


def _run_preflight(wt: Path, status_arg: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(PREFLIGHT_SH), status_arg],
        cwd=wt,
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# A4: empty git.branch / git.worktree → back-fill with a warning, not a failure
# ---------------------------------------------------------------------------


def test_empty_branch_and_worktree_are_backfilled_with_warning(
    tmp_path: Path, session_env
) -> None:
    repo = _make_repo(tmp_path)
    status = _status(repo, "WP-BB1", branch="", worktree="")
    _write_status_and_brief(repo, "WP-BB1", status)
    _commit_all(repo, "freeze WP-BB1")
    wt = tmp_path / "wp-bb1"
    _add_worktree(repo, wt, "feature/wp-bb1")

    res = _run_preflight(wt, str(PLAN_DIR / "WP-BB1.status.json"), session_env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "PREFLIGHT_WARN: git.branch empty; bound to feature/wp-bb1" in res.stderr
    assert "PREFLIGHT_WARN: git.worktree empty; bound to" in res.stderr
    assert "PREFLIGHT_PASS" in res.stdout


def test_nonempty_matching_branch_and_worktree_pass_without_warning(
    tmp_path: Path, session_env
) -> None:
    repo = _make_repo(tmp_path)
    wt = tmp_path / "wp-bb2"
    status = _status(repo, "WP-BB2", branch="feature/wp-bb2", worktree=str(wt))
    _write_status_and_brief(repo, "WP-BB2", status)
    _commit_all(repo, "freeze WP-BB2")
    _add_worktree(repo, wt, "feature/wp-bb2")

    res = _run_preflight(wt, str(PLAN_DIR / "WP-BB2.status.json"), session_env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "PREFLIGHT_WARN" not in res.stderr
    assert "PREFLIGHT_PASS" in res.stdout


def test_nonempty_mismatched_branch_still_fails(tmp_path: Path, session_env) -> None:
    """Regression guard: the A4 relaxation applies ONLY to the empty string."""
    repo = _make_repo(tmp_path)
    status = _status(repo, "WP-BB3", branch="feature/somebody-else", worktree="")
    _write_status_and_brief(repo, "WP-BB3", status)
    _commit_all(repo, "freeze WP-BB3")
    wt = tmp_path / "wp-bb3"
    _add_worktree(repo, wt, "feature/wp-bb3")

    res = _run_preflight(wt, str(PLAN_DIR / "WP-BB3.status.json"), session_env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert (
        "current branch feature/wp-bb3 != status branch feature/somebody-else"
        in res.stderr
    )


def test_nonempty_mismatched_worktree_still_fails(tmp_path: Path, session_env) -> None:
    repo = _make_repo(tmp_path)
    status = _status(
        repo, "WP-BB4", branch="feature/wp-bb4", worktree=str(repo)  # the MAIN repo
    )
    _write_status_and_brief(repo, "WP-BB4", status)
    _commit_all(repo, "freeze WP-BB4")
    wt = tmp_path / "wp-bb4"
    _add_worktree(repo, wt, "feature/wp-bb4")

    res = _run_preflight(wt, str(PLAN_DIR / "WP-BB4.status.json"), session_env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert "current worktree does not match status worktree" in res.stderr


# ---------------------------------------------------------------------------
# A7: the tracked check queries the MAIN repo index
# ---------------------------------------------------------------------------


def test_status_committed_only_on_sibling_branch_passes_from_other_worktree(
    tmp_path: Path, session_env
) -> None:
    """Freeze commit is NOT an ancestor of this WP's branch (sibling fork).

    The worktree's own index cannot see the status file; the main repo index
    can. preflight must pass when given the main-repo copy.
    """
    repo = _make_repo(tmp_path)
    fork_point = _head(repo)  # before the freeze commit

    wt = tmp_path / "wp-a7"
    status = _status(repo, "WP-A7", branch="feature/wp-a7", worktree=str(wt))
    status_path = _write_status_and_brief(repo, "WP-A7", status)
    _commit_all(repo, "freeze WP-A7")

    # WP branch based on the PRE-FREEZE commit: freeze commit is a sibling,
    # so the status file is neither on disk nor tracked in this worktree.
    _add_worktree(repo, wt, "feature/wp-a7", start=fork_point)
    assert not (wt / PLAN_DIR / "WP-A7.status.json").exists()

    res = _run_preflight(wt, str(status_path), session_env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "PREFLIGHT_PASS" in res.stdout


def test_status_never_committed_still_fails(tmp_path: Path, session_env) -> None:
    """Fail-closed floor: an untracked status file is still rejected."""
    repo = _make_repo(tmp_path)
    wt = tmp_path / "wp-nc"
    status = _status(repo, "WP-NC", branch="feature/wp-nc", worktree=str(wt))
    status_path = _write_status_and_brief(repo, "WP-NC", status)
    # NOTE: deliberately NOT committed — the status file only exists on disk.

    _add_worktree(repo, wt, "feature/wp-nc")

    res = _run_preflight(wt, str(status_path), session_env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert "status file must be tracked before implementation" in res.stderr
