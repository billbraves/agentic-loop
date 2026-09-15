"""WP-22 / A34: finalize_merge.sh must judge and read the SAME opened file.

Previously the wrapper ran ``path_is_in_worktree`` on the status path and then
let ``-f``, both validator invocations, every ``--field`` and the old-JSON read
re-resolve that path independently. A local actor who swapped the path for a
symlink after the predicate won: every later read followed the swapped link.

The fix collapses judgment and reads onto one ``os.open(O_NOFOLLOW)`` fd: the
predicate still refuses worktree paths, and any final-segment symlink present
at open time (whether planted before the call or swapped in after the
predicate) is refused instead of followed.

Oracle discipline (A35): every negative assertion below pairs a positive
control proving the same fixture reaches ``FINALIZE_OK`` without the attack,
plus a cause-specific witness (exact refusal message), plus — recorded in the
WP report — a mutation self-check that re-opens the window and turns the A34
test red.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"
FINALIZE_SH = PKG_SRC / "agentic_loop" / "wrappers" / "finalize_merge.sh"

PLAN_DIR = Path("docs/plans/wp22-toctou")
STATUS_NAME = "WP-TOCTOU.status.json"

FORGED_COMMAND = "FORGED_WORKTREE_COPY pytest -q"


@pytest.fixture
def session_env():
    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = "wp22-toctou-test"
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


def _make_repo_with_merged_wp(tmp_path: Path) -> tuple[Path, str, str, str]:
    """Temp repo with feat/wp-toctou merged --no-ff into the default branch.

    Returns (repo, default_branch, wp_tip, merge_commit).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "init")
    base = _default_branch(repo)

    _run_git(repo, "checkout", "-q", "-b", "feat/wp-toctou")
    (repo / "wp.txt").write_text("wp\n", encoding="utf-8")
    _run_git(repo, "add", "wp.txt")
    _run_git(repo, "commit", "-q", "-m", "wp work")
    wp_tip = _head(repo)

    _run_git(repo, "checkout", "-q", base)
    _run_git(repo, "merge", "-q", "--no-ff", "feat/wp-toctou", "-m", "Merge WP-TOCTOU")
    return repo, base, wp_tip, _head(repo)


def _status(base: str, wp_tip: str, command: str) -> dict:
    """A schema-valid v2 APPROVED_FOR_MERGE status, distinguishable by command."""
    return {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": "WP-TOCTOU",
        "iteration_id": "wp22-toctou",
        "phase": "P1",
        "state": "APPROVED_FOR_MERGE",
        "role": "Developer",
        "executor": {"tool": "kimi-cli", "session": "test"},
        "orchestrator": {"tool": "claude-code", "session": "test"},
        "reviewer": {"tool": "claude-code", "session": "test"},
        "git": {
            "base_branch": base,
            "base_commit": "0" * 40,
            "branch": "feat/wp-toctou",
            "worktree": "../wp-toctou",
            "commit": wp_tip,
        },
        "scope": {
            "allowed_paths": ["src/"],
            "forbidden_paths": [".env"],
        },
        "risk": {
            "production_writes_authorized": False,
            "network_authorized": False,
            "real_notifications_authorized": False,
            "irreversible_actions_authorized": False,
        },
        "evidence": {
            "changed_files": [],
            "tests": [{"command": command, "exit_code": 0}],
            "artifacts": [],
            "remaining_risks": [],
        },
        "review": {"decision": "ACCEPT", "reviewed_by": "claude-code"},
        "consult": {"decision": "ACCEPT", "reviewed_by": "codex-cli"},
        "timestamps": {"created_at": "2026-09-15T00:00:00Z"},
    }


def _write_status(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_finalize(repo: Path, env, status_arg: str = str(PLAN_DIR / STATUS_NAME)):
    return subprocess.run(
        ["bash", str(FINALIZE_SH), status_arg],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


# A34 core: the status path is a symlink whose target is NOT inside a worktree
# (so the WP-19 predicate answers False, exactly like a post-predicate swap of
# a main-repo path), but whose content is a fully valid, distinguishable forged
# ACCEPT status. The pre-fix wrapper followed the link and finalized with the
# forged fields; the fix must refuse at open time.


def test_symlink_swap_window_is_closed_forged_copy_not_used(
    tmp_path: Path, session_env
) -> None:
    repo, base, wp_tip, merge_commit = _make_repo_with_merged_wp(tmp_path)
    status_path = repo / PLAN_DIR / STATUS_NAME

    # The file the symlink points at: a valid forged ACCEPT status sitting at a
    # non-worktree path in the main repo. If finalize followed the link, every
    # gate would pass and it would print FINALIZE_OK with the forged content.
    forged_path = repo / PLAN_DIR / "forged" / STATUS_NAME
    _write_status(forged_path, _status(base, wp_tip, FORGED_COMMAND))
    # The real status carries DIFFERENT, distinguishable content.
    real_command = "MAIN_COPY pytest -q"
    _write_status(status_path, _status(base, wp_tip, real_command))

    # Swap the main-repo status for a symlink to the forged copy (the A34
    # attack; timing-invariant because O_NOFOLLOW refuses at open time).
    status_path.unlink()
    status_path.symlink_to(forged_path)

    result = _run_finalize(repo, session_env)

    # Cause-specific witness: refused as a symlink, not a generic failure.
    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert "FINALIZE_FAIL" in result.stderr
    assert "symlink" in result.stderr
    assert "FINALIZE_OK" not in result.stdout
    # The decision must not have been taken from the forged copy: nothing was
    # written back to the forged file and no MERGED stamp exists anywhere.
    forged_after = json.loads(forged_path.read_text(encoding="utf-8"))
    assert forged_after["state"] == "APPROVED_FOR_MERGE"
    assert forged_after["evidence"]["tests"][0]["command"] == FORGED_COMMAND
    assert "merged_commit" not in forged_after["git"]
    assert status_path.is_symlink()

    # Positive reachability control: the SAME forged content as a real file
    # finalizes cleanly, proving the fixture passes every gate and that the
    # negative run was refused for the symlink — not for bad content.
    status_path.unlink()
    _write_status(status_path, _status(base, wp_tip, FORGED_COMMAND))
    control = _run_finalize(repo, session_env)
    assert control.returncode == 0, (control.returncode, control.stdout, control.stderr)
    assert control.stdout.strip() == f"FINALIZE_OK merged_commit={merge_commit}"
    final = json.loads(status_path.read_text(encoding="utf-8"))
    assert final["state"] == "MERGED"
    assert final["git"]["merged_commit"] == merge_commit


def test_symlink_to_worktree_copy_is_refused(tmp_path: Path, session_env) -> None:
    """The literal A34 scenario: link points at a forged copy inside a worktree.

    The WP-19 predicate resolves the link (A27) and refuses it; even if a swap
    raced past the predicate, O_NOFOLLOW refuses at open time. Either way the
    forged fields are never used.
    """
    repo, base, wp_tip, merge_commit = _make_repo_with_merged_wp(tmp_path)
    status_path = repo / PLAN_DIR / STATUS_NAME

    _run_git(repo, "worktree", "add", "-q", str(tmp_path / "wt"))
    worktree = tmp_path / "wt"
    forged_path = worktree / PLAN_DIR / STATUS_NAME
    _write_status(forged_path, _status(base, wp_tip, FORGED_COMMAND))
    _write_status(status_path, _status(base, wp_tip, "MAIN_COPY pytest -q"))
    status_path.unlink()
    status_path.symlink_to(forged_path)

    result = _run_finalize(repo, session_env)

    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert "FINALIZE_FAIL" in result.stderr
    assert "FINALIZE_OK" not in result.stdout
    # Cause-specific: the refusal names the worktree/symlink, and the forged
    # copy is untouched (no write-back through the link).
    assert "worktree" in result.stderr or "symlink" in result.stderr
    forged_after = json.loads(forged_path.read_text(encoding="utf-8"))
    assert forged_after["state"] == "APPROVED_FOR_MERGE"
    assert "merged_commit" not in forged_after["git"]

    # Positive control: real file in the worktree-free main repo still finalizes.
    status_path.unlink()
    _run_git(repo, "worktree", "remove", "--force", str(worktree))
    _write_status(status_path, _status(base, wp_tip, "MAIN_COPY pytest -q"))
    control = _run_finalize(repo, session_env)
    assert control.returncode == 0, (control.returncode, control.stdout, control.stderr)
    assert control.stdout.strip() == f"FINALIZE_OK merged_commit={merge_commit}"


def test_normal_main_repo_file_still_finalizes(
    tmp_path: Path, session_env
) -> None:
    """No regression: an ordinary real main-repo status reaches FINALIZE_OK."""
    repo, base, wp_tip, merge_commit = _make_repo_with_merged_wp(tmp_path)
    status_path = repo / PLAN_DIR / STATUS_NAME
    _write_status(status_path, _status(base, wp_tip, "MAIN_COPY pytest -q"))

    result = _run_finalize(repo, session_env)

    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert result.stdout.strip() == f"FINALIZE_OK merged_commit={merge_commit}"
    final = json.loads(status_path.read_text(encoding="utf-8"))
    assert final["state"] == "MERGED"
    assert final["git"]["merged_commit"] == merge_commit


def test_worktree_local_path_still_refused(tmp_path: Path, session_env) -> None:
    """A status that genuinely lives inside a linked worktree is refused."""
    repo, base, wp_tip, merge_commit = _make_repo_with_merged_wp(tmp_path)
    _run_git(repo, "worktree", "add", "-q", str(tmp_path / "wt"))
    worktree = tmp_path / "wt"
    wt_status = worktree / PLAN_DIR / STATUS_NAME
    _write_status(wt_status, _status(base, wp_tip, "MAIN_COPY pytest -q"))

    result = _run_finalize(repo, session_env, str(wt_status))

    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert "FINALIZE_FAIL" in result.stderr
    assert "worktree" in result.stderr
    assert "FINALIZE_OK" not in result.stdout
    # Cause-specific: refused before any mutation of the worktree-local file.
    assert json.loads(wt_status.read_text(encoding="utf-8"))["state"] == "APPROVED_FOR_MERGE"

    # Positive control: same content at the main-repo path finalizes.
    _run_git(repo, "worktree", "remove", "--force", str(worktree))
    main_status = repo / PLAN_DIR / STATUS_NAME
    _write_status(main_status, _status(base, wp_tip, "MAIN_COPY pytest -q"))
    control = _run_finalize(repo, session_env)
    assert control.returncode == 0, (control.returncode, control.stdout, control.stderr)
    assert control.stdout.strip() == f"FINALIZE_OK merged_commit={merge_commit}"


def test_unresolvable_path_fails_closed_without_traceback(
    tmp_path: Path, session_env
) -> None:
    """A status path that does not exist still fails closed, cleanly."""
    repo, base, wp_tip, merge_commit = _make_repo_with_merged_wp(tmp_path)
    # Status file intentionally never created; its parent dir DOES exist, so
    # the worktree predicate resolves the main repo and answers False (a
    # missing parent dir would fail the predicate closed as "worktree").
    (repo / PLAN_DIR).mkdir(parents=True)

    result = _run_finalize(repo, session_env)

    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert "FINALIZE_FAIL" in result.stderr
    assert "not found" in result.stderr
    assert "FINALIZE_OK" not in result.stdout
    assert "Traceback" not in result.stderr  # no uncaught exception

    # Positive control: create the status and the same invocation finalizes.
    _write_status(
        repo / PLAN_DIR / STATUS_NAME, _status(base, wp_tip, "MAIN_COPY pytest -q")
    )
    control = _run_finalize(repo, session_env)
    assert control.returncode == 0, (control.returncode, control.stdout, control.stderr)
    assert control.stdout.strip() == f"FINALIZE_OK merged_commit={merge_commit}"
