"""WP-19 / A12: first ``finalize_merge.sh`` call must not abort on the field it
writes itself.

``finalize_merge.sh`` reads ``git.merged_commit`` under ``set -euo pipefail``.
That field only exists AFTER finalize writes it, so on the first call the
un guarded read aborted with ``STATUS_INVALID: unknown field
git.merged_commit``. The guarded read must treat a missing field as empty
(fail-closed) and reach FINALIZE_OK; a second call must be idempotent.

Fixture mirrors test_finalize_merge_triple_sign.py but derives the default
branch name instead of assuming ``main``.
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

PLAN_DIR = Path("docs/plans/wp19-first-call")
STATUS_NAME = "WP-FC.status.json"


@pytest.fixture
def session_env():
    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = "wp19-first-call-test"
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
    """Temp repo with feat/wp-fc merged --no-ff into the default branch.

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

    _run_git(repo, "checkout", "-q", "-b", "feat/wp-fc")
    (repo / "wp.txt").write_text("wp\n", encoding="utf-8")
    _run_git(repo, "add", "wp.txt")
    _run_git(repo, "commit", "-q", "-m", "wp work")
    wp_tip = _head(repo)

    _run_git(repo, "checkout", "-q", base)
    _run_git(repo, "merge", "-q", "--no-ff", "feat/wp-fc", "-m", "Merge WP-FC")
    return repo, base, wp_tip, _head(repo)


def _status_without_merged_commit(base: str, wp_tip: str) -> dict:
    """A schema-valid v2 APPROVED_FOR_MERGE status with NO git.merged_commit key."""
    return {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": "WP-FC",
        "iteration_id": "wp19-first-call",
        "phase": "P1",
        "state": "APPROVED_FOR_MERGE",
        "role": "Developer",
        "executor": {"tool": "kimi-cli", "session": "test"},
        "orchestrator": {"tool": "claude-code", "session": "test"},
        "reviewer": {"tool": "claude-code", "session": "test"},
        "git": {
            "base_branch": base,
            "base_commit": "0" * 40,
            "branch": "feat/wp-fc",
            "worktree": "../wp-fc",
            "commit": wp_tip,
            # NOTE: deliberately no "merged_commit" key — finalize writes it.
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
            "tests": [{"command": "pytest tests -q", "exit_code": 0}],
            "artifacts": [],
            "remaining_risks": [],
        },
        "review": {"decision": "ACCEPT", "reviewed_by": "claude-code"},
        "consult": {"decision": "ACCEPT", "reviewed_by": "codex-cli"},
        "timestamps": {"created_at": "2026-09-14T00:00:00Z"},
    }


def test_first_call_without_merged_commit_finalizes_then_idempotent(
    tmp_path: Path, session_env
) -> None:
    repo, base, wp_tip, merge_commit = _make_repo_with_merged_wp(tmp_path)
    status_path = repo / PLAN_DIR / STATUS_NAME
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        json.dumps(_status_without_merged_commit(base, wp_tip), indent=2),
        encoding="utf-8",
    )
    assert "merged_commit" not in json.loads(status_path.read_text())["git"]

    def run_finalize() -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(FINALIZE_SH), str(PLAN_DIR / STATUS_NAME)],
            cwd=repo,
            capture_output=True,
            text=True,
            env=session_env,
        )

    # First call: the missing git.merged_commit field must NOT abort the run.
    first = run_finalize()
    assert first.returncode == 0, (first.returncode, first.stdout, first.stderr)
    assert first.stdout.strip() == f"FINALIZE_OK merged_commit={merge_commit}"

    final = json.loads(status_path.read_text(encoding="utf-8"))
    assert final["state"] == "MERGED"
    assert final["git"]["merged_commit"] == merge_commit

    # Second call: idempotent re-finalization of an already-MERGED status.
    second = run_finalize()
    assert second.returncode == 0, (second.returncode, second.stdout, second.stderr)
    assert second.stdout.strip() == (
        f"FINALIZE_OK merged_commit={merge_commit} (already finalized)"
    )
