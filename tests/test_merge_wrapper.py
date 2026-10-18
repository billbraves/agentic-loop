"""Tests for merge.sh (local no-ff merge wrapper)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"


def _resolve_wrapper(name: str) -> Path:
    bundled = PKG_SRC / "agentic_loop" / "wrappers" / name
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parents[3] / "scripts" / "agentic" / name


MERGE_SH = _resolve_wrapper("merge.sh")


def _run_git(repo: Path, *args: str, check: bool = True):
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True
    )


def _head(repo: Path) -> str:
    return _run_git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def env():
    e = dict(os.environ)
    e["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + e["PYTHONPATH"] if e.get("PYTHONPATH") else ""
    )
    return e


def _make_repo_and_status(tmp_path: Path, state: str = "APPROVED_FOR_MERGE"):
    """Temp repo: main + feat/x (one commit). Returns (repo, status_path, feat_commit)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "t@e.com")
    _run_git(repo, "config", "user.name", "T")
    (repo / "README.md").write_text("init\n")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "init")
    _run_git(repo, "branch", "-M", "main")
    base_commit = _head(repo)

    _run_git(repo, "checkout", "-q", "-b", "feat/x")
    (repo / "a.txt").write_text("a\n")
    _run_git(repo, "add", "a.txt")
    _run_git(repo, "commit", "-q", "-m", "feat")
    feat_commit = _head(repo)
    _run_git(repo, "checkout", "-q", "main")

    status = {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": "WP-A",
        "iteration_id": "it",
        "phase": "P1",
        "state": state,
        "role": "Developer",
        "executor": {"tool": "kimi-cli"},
        "orchestrator": {"tool": "claude-code"},
        "reviewer": {"tool": "claude-code"},
        "git": {
            "base_branch": "main",
            "base_commit": base_commit,
            "branch": "feat/x",
            "worktree": ".worktrees/x",
            "commit": feat_commit,
        },
        "scope": {"allowed_paths": ["a.txt"], "forbidden_paths": []},
        "risk": {"production_writes": "FORBIDDEN", "network": "FORBIDDEN",
                 "notifications": "FORBIDDEN", "data_access": "READ_ONLY"},
        "evidence": {"tests": [{"exit_code": 0}]},
        "review": {"decision": "ACCEPT"},
        "consult": {"decision": "ACCEPT"},
        "timestamps": {"dispatched_at": ""},
    }
    status_path = repo / "WP-A.status.json"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    # WP-01: the status-source predicate resolves the authoritative branch from
    # the PLAN status beside the judged file, so the fixture must supply one.
    # Declares the branch this repo actually holds ("main", renamed above).
    (repo / "PLAN-A.status.json").write_text(json.dumps({"schema_version": "agentic-plan-status/v1", "plan_id": "PLAN-A", "iteration_id": "it-1", "state": "ACTIVE", "title": "fixture plan", "git": {"base_branch": "main", "target_branch": "main"}, "work_packages": ["WP-A"], "timestamps": {"created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}}), encoding="utf-8")
    return repo, status_path, feat_commit


def _run_merge(repo: Path, status_path: Path, env: dict):
    return subprocess.run(
        ["bash", str(MERGE_SH), str(status_path)],
        cwd=repo, capture_output=True, text=True, env=env,
    )


def test_merge_success_creates_merge_commit(tmp_path, env):
    repo, status_path, feat_commit = _make_repo_and_status(tmp_path)
    res = _run_merge(repo, status_path, env)
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert "MERGE_OK" in res.stdout
    # main now contains feat/x's a.txt via a no-ff merge commit
    assert (repo / "a.txt").is_file()
    merge_commit = _head(repo)
    parents = _run_git(repo, "rev-list", "--parents", "-n", "1", merge_commit).stdout.split()
    assert len(parents) == 3  # merge commit has two parents
    assert feat_commit in parents


def test_merge_autonomy_stop(tmp_path, env):
    repo, status_path, _ = _make_repo_and_status(tmp_path)
    (repo / ".agentic").mkdir()
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ask"\n', encoding="utf-8"
    )
    res = _run_merge(repo, status_path, env)
    assert res.returncode == 3, (res.stdout, res.stderr)
    assert "MERGE_STOP" in res.stderr
    # nothing merged
    assert not (repo / "a.txt").exists()


def test_merge_wrong_state_fails(tmp_path, env):
    repo, status_path, _ = _make_repo_and_status(tmp_path, state="IMPLEMENTING")
    res = _run_merge(repo, status_path, env)
    assert res.returncode == 2
    assert "MERGE_FAIL" in res.stderr
    assert "APPROVED_FOR_MERGE" in res.stderr
