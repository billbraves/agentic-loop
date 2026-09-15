"""WP-19 / A13: the worktree refusal predicate is a git fact, not a path literal.

``agentic_loop.gate.path_is_in_worktree`` is the single authoritative
definition; ``gate/__init__.py`` and ``wrappers/finalize_merge.sh`` both
reference it (global rule §5.3). This suite pins:

- a main-repo path is NOT a worktree;
- a linked-worktree path IS a worktree — including the sibling ``../wpN-x``
  layout this repo actually uses (no ``.worktrees/`` segment anywhere);
- the verdict does not depend on the directory NAME (a literal
  ``/.worktrees/`` directory inside the main repo is NOT a worktree);
- unresolvable paths fail closed (treated as a worktree) without raising;
- ``finalize_merge.sh`` end-to-end rejects a worktree-local absolute status
  path (the second call site).

WP-19 rev2 / A22: the predicate's git probe must not inherit the caller's
repository-selection environment (``GIT_DIR`` et al. declare which repository
a path belongs to, overriding filesystem topology). The predicate reads the
filesystem, so those variables are stripped — while the rest of the
environment (``PATH`` in particular) is kept intact.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_loop.gate import path_is_in_worktree

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"
FINALIZE_SH = PKG_SRC / "agentic_loop" / "wrappers" / "finalize_merge.sh"


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "init")
    return repo


def test_main_repo_path_is_not_worktree(repo: Path) -> None:
    assert path_is_in_worktree(repo / "README.md") is False


def test_sibling_worktree_path_is_worktree(repo: Path, tmp_path: Path) -> None:
    # The layout this repo actually uses: `git worktree add ../wpN-x` — a
    # sibling directory whose name never contains ".worktrees/".
    wt = tmp_path / "wp19-x"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-x", str(wt))
    assert "/.worktrees/" not in str(wt)
    assert path_is_in_worktree(wt / "README.md") is True


def test_verdict_does_not_depend_on_directory_name(repo: Path) -> None:
    # A literal ".worktrees" directory INSIDE the main repo is plain main-repo
    # content, not a linked worktree. The old `"/.worktrees/" in path` literal
    # would refuse it; the git-fact predicate must not.
    nested = repo / ".worktrees" / "fake"
    nested.mkdir(parents=True)
    (nested / "WP-X.status.json").write_text("{}\n", encoding="utf-8")
    assert path_is_in_worktree(nested / "WP-X.status.json") is False


def test_unresolvable_path_fails_closed_without_raising(tmp_path: Path) -> None:
    # Outside any git repository: fail closed (refuse) and never raise.
    missing = tmp_path / "no-such-dir" / "WP-X.status.json"
    assert path_is_in_worktree(missing) is True


@pytest.mark.parametrize("var", ["GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"])
def test_caller_env_cannot_disguise_worktree_path(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, var: str
) -> None:
    # A22 regression guard: a caller who exports a repository-selection
    # variable pointing at the MAIN repo must not flip a linked-worktree
    # path to False. GIT_DIR=<main>/.git alone bypassed the guard before
    # rev2; GIT_WORK_TREE/GIT_COMMON_DIR must stay non-bypassing too.
    branch = "feat/wp19-env-" + var.lower().replace("_", "-")
    wt = tmp_path / ("wp19-env-" + var.lower().replace("_", "-"))
    _run_git(repo, "worktree", "add", "-q", "-b", branch, str(wt))
    value = str(repo) if var == "GIT_WORK_TREE" else str(repo / ".git")
    monkeypatch.setenv(var, value)
    assert path_is_in_worktree(wt / "README.md") is True


def test_caller_env_cannot_disguise_main_repo_path(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The sanitization must not over-correct either: with GIT_DIR pointing
    # at a linked worktree's git dir, a main-repo path still resolves by
    # filesystem topology and is NOT refused (still False).
    wt = tmp_path / "wp19-env-rev"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-env-rev", str(wt))
    wt_git_dir = _run_git(wt, "rev-parse", "--absolute-git-dir").stdout.strip()
    monkeypatch.setenv("GIT_DIR", wt_git_dir)
    assert path_is_in_worktree(repo / "README.md") is False


def test_sanitized_env_still_preserves_path(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # env={} would drop PATH; on hosts where git lives outside the exec
    # default path (e.g. Homebrew) the lookup then fails and fail-closed
    # would incorrectly refuse a clean main-repo path. The sanitized env
    # must keep PATH so git is still found and the verdict stays correct.
    assert shutil.which("git") is not None
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)
    assert path_is_in_worktree(repo / "README.md") is False


def test_finalize_merge_rejects_worktree_local_status(repo: Path, tmp_path: Path) -> None:
    wt = tmp_path / "wp19-y"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-y", str(wt))
    status_in_wt = wt / "docs" / "plans" / "iter" / "WP-Y.status.json"
    status_in_wt.parent.mkdir(parents=True)
    status_in_wt.write_text("{}\n", encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["AGENTIC_PYTHON"] = sys.executable
    res = subprocess.run(
        ["bash", str(FINALIZE_SH), str(status_in_wt)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert "resolves inside a worktree" in res.stderr, (res.stdout, res.stderr)
