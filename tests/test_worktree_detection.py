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


def test_caller_env_combined_cannot_disguise_worktree_path(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A22 regression guard, combined form: GIT_DIR + GIT_WORK_TREE +
    # GIT_COMMON_DIR all pointing at the MAIN repo at once must still not
    # flip a linked-worktree path to False. (Set after worktree creation so
    # the fixture's own git calls are unaffected.)
    wt = tmp_path / "wp19-env-all"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-env-all", str(wt))
    monkeypatch.setenv("GIT_DIR", str(repo / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(repo))
    monkeypatch.setenv("GIT_COMMON_DIR", str(repo / ".git"))
    assert path_is_in_worktree(wt / "README.md") is True


def test_sanitized_env_still_preserves_path(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Distinguish "env sanitized" from "env emptied": env={} would drop PATH
    # (or fall back to the exec default, which on macOS still finds
    # /usr/bin/git — so merely asserting False proves nothing). The contrast
    # here locks the real invariant: with a PATH that has NO git, the probe
    # cannot find git and must fail closed (True); with the inherited PATH
    # it finds git and the main-repo path is correctly NOT refused (False).
    # Only the second verdict proves the sanitized env kept PATH usable.
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    assert shutil.which("git") is None  # premise: git genuinely unfindable
    assert path_is_in_worktree(repo / "README.md") is True  # fail-closed
    monkeypatch.undo()  # restore the real PATH
    assert shutil.which("git") is not None
    assert path_is_in_worktree(repo / "README.md") is False


def test_blank_common_dir_fails_closed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A28-1 (WP-19 rev4): git exits 0 with exactly two lines, but the
    # --git-common-dir line is blank after strip(). Before rev4 this
    # degenerated to common_dir = directory / Path("") == directory, which
    # resolved equal to git_dir and answered False (fail-OPEN). Degenerate
    # output must fail closed.
    directory = str(repo)
    fake = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout=f"{directory}\n \n", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    assert path_is_in_worktree(repo / "README.md") is True


def test_blank_git_dir_fails_closed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A28-1 (WP-19 rev4): symmetric degeneration on the --absolute-git-dir
    # line. A blank first line is not an absolute path, but the blank check
    # must reject it as degenerate output regardless of line position.
    directory = str(repo)
    fake = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout=f" \n{directory}\n", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    assert path_is_in_worktree(repo / "README.md") is True


def test_symlink_loop_fails_closed_without_raising(repo: Path) -> None:
    # A28-2 (WP-19 rev4): resolving a symlink loop raises RuntimeError,
    # which is NOT an OSError subclass — an `except OSError` guard cannot
    # catch it, violating the "never raises" contract. The predicate must
    # fail closed (True) and must not raise.
    loop = repo / "loop"
    loop.symlink_to("loop")  # real self-referential symlink loop
    assert path_is_in_worktree(loop) is True


def test_main_repo_symlink_to_worktree_status_is_refused(
    repo: Path, tmp_path: Path
) -> None:
    # A27 (WP-19 rev4): the predicate must judge the file actually read and
    # written, not the path NAME. A symlink in the main repo pointing at a
    # worktree-local status file is followed by is_file()/validator/finalize
    # write-back, so the verdict must be the worktree's: True (refused).
    # Before rev4 the probe used the UNRESOLVED path, answered False, and
    # let the write-back land on the worktree copy.
    wt = tmp_path / "wp19-link"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-link", str(wt))
    status_in_wt = wt / "docs" / "plans" / "iter" / "WP-L.status.json"
    status_in_wt.parent.mkdir(parents=True)
    status_in_wt.write_text("{}\n", encoding="utf-8")
    link = repo / "WP-L.status.json"
    link.symlink_to(status_in_wt)
    assert path_is_in_worktree(link) is True


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


def test_long_path_fails_closed_without_raising(repo: Path) -> None:
    # A29-1 (WP-19 rev5): ``directory = resolved if resolved.is_dir() else
    # resolved.parent`` sat outside every guard, and ``is_dir()`` stats the
    # path — a ~300-character filename raises ``OSError: [Errno 63] File name
    # too long``. The predicate's docstring promises "never raises", and the
    # fail-open command-substitution call site in finalize_merge.sh turns a
    # raised predicate into a skipped refusal. Overlong input must fail
    # closed (True) without raising.
    long_name = "a" * 300 + ".json"
    assert path_is_in_worktree(repo / long_name) is True


def test_null_byte_path_fails_closed_without_raising(repo: Path) -> None:
    # A29-2 (WP-19 rev5): ``path.resolve()`` raises ``ValueError: embedded
    # null byte`` for a path containing NUL, and ValueError is not an OSError
    # subclass — the rev4 guards could not catch it. The three guards share
    # one except form ``(OSError, RuntimeError, ValueError)`` (§5.3), so the
    # predicate fails closed (True) instead of raising.
    nul_path = Path(str(repo) + "/a\x00b.json")
    assert path_is_in_worktree(nul_path) is True
