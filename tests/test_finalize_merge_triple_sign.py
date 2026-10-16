"""WP-05: ``finalize_merge.sh`` three-signature (review + consult + qoder) gate.

Uses temporary git repositories + temporary status copies + the real
``scripts/agentic/finalize_merge.sh`` (symlinked in) so the fail-closed
behaviour is exercised end-to-end without touching the main repo or production
state. The qoder third signature applies only to ``agentic-wp-status/v3``; v2
stays double-sign only.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"


def _resolve_wrapper(name: str) -> Path:
    """Locate a wrapper shell in either layout.

    Prefers the bundled copy under this package (``src/agentic_loop/wrappers``),
    falling back to the monorepo dogfood copy under ``scripts/agentic/``
    (parents[3] = monorepo root). Runnable both inside the monorepo and in the
    standalone extracted repo.
    """
    bundled = PKG_SRC / "agentic_loop" / "wrappers" / name
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parents[3] / "scripts" / "agentic" / name


FINALIZE_SH = _resolve_wrapper("finalize_merge.sh")
LOCK_SH = _resolve_wrapper("lock.sh")

V2 = "agentic-wp-status/v2"
V3 = "agentic-wp-status/v3"

PLAN_DIR = Path("docs/plans/agentic-gate-unification-v1")
STATUS_NAME = "WP-A.status.json"


@pytest.fixture
def session_env():
    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = "wp05-test-session"
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return env


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True
    )


def _head(repo: Path) -> str:
    return _run_git(repo, "rev-parse", "HEAD").stdout.strip()


def _default_branch(repo: Path) -> str:
    """The temp repo's actual initial branch.

    ``git init`` honours ``init.defaultBranch``, so this is ``master`` on a
    machine configured that way and ``main`` elsewhere. Hardcoding ``main``
    made four of these tests fail for an environment reason unrelated to the
    behaviour under test. This is the same helper the sibling fixtures
    (``test_finalize_merge_first_call.py``, ``test_finalize_merge_sequential.py``)
    already use.
    """
    return _run_git(repo, "branch", "--show-current").stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    """A temp git repo with symlinks to the real agentic scripts under test."""
    repo = tmp_path / "repo"
    repo.mkdir()

    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")

    scripts_dir = repo / "scripts" / "agentic"
    scripts_dir.mkdir(parents=True)
    for name in ("lock.sh", "finalize_merge.sh"):
        (scripts_dir / name).symlink_to(_resolve_wrapper(name))

    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "init")
    return repo


def _pass_qoder() -> dict:
    return {"decision": "PASS", "findings": [], "level": "L3", "requested_level": "L3"}


def _findings_qoder(override: dict | None = None) -> dict:
    qoder: dict = {
        "decision": "FINDINGS",
        "findings": [
            {
                "category": "path_traversal",
                "severity": "high",
                "file": "scripts/agentic/finalize_merge.sh",
                "dataflow": None,
                "summary": "path traversal risk",
            }
        ],
        "level": "L3",
        "requested_level": "L3",
    }
    if override is not None:
        qoder["override"] = override
    return qoder


def _valid_override() -> dict:
    return {
        "approved": True,
        "approver": "human-adjudicated",
        "justification": "security gate false positive",
        "reviewed_at": "2026-08-15T00:00:00Z",
    }


def _make_status(
    *,
    schema_version: str = V3,
    state: str = "APPROVED_FOR_MERGE",
    review_decision: str = "ACCEPT",
    consult_decision: str = "ACCEPT",
    consult_override: dict | None = None,
    qoder: dict | None = None,
    git_commit: str | None = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    tests: list | None = None,
    merged_commit: str | None = None,
    base_branch: str = "main",  # callers that merge pass the repo's real default
    branch: str = "feat/wp-a",
) -> dict:
    if tests is None:
        tests = [{"command": "pytest", "exit_code": 0}]
    data: dict = {
        "schema_version": schema_version,
        "work_package_id": "WP-A",
        "iteration_id": "agentic-gate-unification-v1",
        "phase": "P3",
        "state": state,
        "role": "Developer",
        "executor": {
            "tool": "kimi-cli",
            "session_id": None,
            "exit_code": None,
            "log_path": None,
        },
        "orchestrator": {"tool": "claude-code", "session_id": None},
        "reviewer": {"tool": "claude-code", "session_id": None},
        "git": {
            "base_branch": base_branch,
            "base_commit": "0000000000000000000000000000000000000000",
            "branch": branch,
            "worktree": ".worktrees/triple-sign-wp-a",
            "commit": git_commit,
            "merged_commit": merged_commit,
        },
        "scope": {
            "allowed_paths": [
                "scripts/agentic/finalize_merge.sh",
                "AGENTS.md",
                "packages/agentic-loop/tests/",
            ],
            "forbidden_paths": [
                "profiles/",
                ".env",
                ".context/",
                ".worktrees/",
                "packages/agentic-loop/src/agentic_loop/validate_wp_status.py",
            ],
        },
        "risk": {
            "production_writes_authorized": False,
            "network_authorized": False,
            "real_notifications_authorized": False,
            "irreversible_actions_authorized": False,
        },
        "evidence": {
            "changed_files": [],
            "tests": tests,
            "artifacts": [],
            "remaining_risks": [],
        },
        "review": {
            "decision": review_decision,
            "reviewed_by": "claude-code",
            "reviewed_at": "2026-08-15T00:00:00Z",
            "notes": None,
        },
        "timestamps": {
            "created_at": "2026-08-15T00:00:00Z",
            "updated_at": "2026-08-15T00:00:00Z",
            "started_at": "2026-08-15T00:00:00Z",
            "completed_at": None,
        },
    }
    if schema_version in (V2, V3):
        consult: dict = {
            "decision": consult_decision,
            "reviewed_by": "codex-cli",
            "reviewed_at": "2026-08-15T00:00:00Z",
            "notes": None,
        }
        if consult_override is not None:
            consult["override"] = consult_override
        data["consult"] = consult
    if schema_version == V3 and qoder is not None:
        data["qoder_security"] = qoder
    return data


def _write_status(repo: Path, data: dict) -> Path:
    status_path = repo / PLAN_DIR / STATUS_NAME
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # WP-01: the status-source predicate resolves the authoritative branch from
    # the PLAN status in this same plan dir. Declare the repo's REAL default
    # branch (probed, never hardcoded) — the checkout holding it is the
    # authoritative source these fixtures exercise.
    (status_path.parent / "PLAN-01.status.json").write_text(
        json.dumps(
            {
                "schema_version": "agentic-plan-status/v1",
                "plan_id": "PLAN-01",
                "git": {
                    "base_branch": _default_branch(repo),
                    "target_branch": "main",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return status_path


def _finalize(repo: Path, status_path: Path, env: dict) -> subprocess.CompletedProcess:
    rel = status_path.relative_to(repo)
    return subprocess.run(
        ["bash", str(FINALIZE_SH), str(rel)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def _assert_ok(res: subprocess.CompletedProcess, expected_sha: str) -> None:
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert res.stdout.strip() == f"FINALIZE_OK merged_commit={expected_sha}"


def _assert_fail(res: subprocess.CompletedProcess, reason_substring: str) -> None:
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    combined = (res.stdout + res.stderr).lower()
    assert "finalize_fail:" in combined, (res.returncode, res.stdout, res.stderr)
    assert reason_substring.lower() in combined, (res.returncode, res.stdout, res.stderr)


def _merge_wp_branch(repo: Path, branch: str = "feat/wp-a") -> tuple[str, str, str]:
    """Create and merge a WP branch with ``--no-ff``.

    Returns ``(wp_tip, merge_commit, base)`` where ``base`` is the repo's real
    default branch, so callers pass a ``base_branch`` that matches the actual
    layout instead of a hardcoded ``main``.
    """
    base = _default_branch(repo)
    _run_git(repo, "checkout", "-q", "-b", branch)
    (repo / "wp.txt").write_text("wp\n", encoding="utf-8")
    _run_git(repo, "add", "wp.txt")
    _run_git(repo, "commit", "-q", "-m", "wp work")
    wp_tip = _head(repo)

    _run_git(repo, "checkout", "-q", base)
    _run_git(repo, "merge", "-q", "--no-ff", branch, "-m", "Merge WP-A")
    merge_commit = _head(repo)
    return wp_tip, merge_commit, base


# ① v3 three signatures complete (review ACCEPT + consult ACCEPT + qoder PASS).
def test_v3_triple_sign_pass_finalizes(tmp_path, session_env):
    repo = _make_repo(tmp_path)
    wp_tip, merge_commit, base = _merge_wp_branch(repo)

    status = _make_status(
        schema_version=V3,
        git_commit=wp_tip,
        branch="feat/wp-a",
        base_branch=base,
        qoder=_pass_qoder(),
    )
    status_path = _write_status(repo, status)

    res = _finalize(repo, status_path, session_env)
    _assert_ok(res, merge_commit)

    final = json.loads(status_path.read_text(encoding="utf-8"))
    assert final["state"] == "MERGED"
    assert final["git"]["merged_commit"] == merge_commit
    assert final["qoder_security"]["decision"] == "PASS"


# ② v3 qoder non-PASS with no override is rejected by finalize's own shell gate.
#    DRAFT state avoids the validator's merge-state qoder gate so this test pins
#    the finalize_merge.sh branch directly (validator still passes the fixture).
def test_v3_qoder_findings_no_override_rejected(tmp_path, session_env):
    repo = _make_repo(tmp_path)

    status = _make_status(
        schema_version=V3,
        state="DRAFT",
        review_decision="ACCEPT",
        consult_decision="ACCEPT",
        qoder=_findings_qoder(),
    )
    status_path = _write_status(repo, status)

    res = _finalize(repo, status_path, session_env)
    _assert_fail(res, "qoder_security.decision must be PASS")


# ③ v3 qoder FINDINGS + complete approved override finalizes and the original
#    decision is preserved honestly (never rewritten to PASS).
def test_v3_qoder_override_approved_finalizes_record_preserved(tmp_path, session_env):
    repo = _make_repo(tmp_path)
    wp_tip, merge_commit, base = _merge_wp_branch(repo)

    status = _make_status(
        schema_version=V3,
        git_commit=wp_tip,
        branch="feat/wp-a",
        base_branch=base,
        qoder=_findings_qoder(override=_valid_override()),
    )
    status_path = _write_status(repo, status)

    res = _finalize(repo, status_path, session_env)
    _assert_ok(res, merge_commit)

    final = json.loads(status_path.read_text(encoding="utf-8"))
    assert final["state"] == "MERGED"
    assert final["git"]["merged_commit"] == merge_commit
    # The FINDINGS decision and the finding record survive; only state changed.
    assert final["qoder_security"]["decision"] == "FINDINGS"
    assert final["qoder_security"]["findings"][0]["severity"] == "high"
    assert final["qoder_security"]["override"]["approved"] is True


# ④ v3 missing qoder_security block is rejected fail-closed by validation.
def test_v3_missing_qoder_block_rejected(tmp_path, session_env):
    repo = _make_repo(tmp_path)
    wp_tip, _, base = _merge_wp_branch(repo)

    status = _make_status(
        schema_version=V3,
        git_commit=wp_tip,
        branch="feat/wp-a",
        base_branch=base,
        qoder=None,
    )
    status_path = _write_status(repo, status)

    res = _finalize(repo, status_path, session_env)
    _assert_fail(res, "status validation failed")


# ⑤ v2 status (no qoder block) remains double-sign only and finalizes.
def test_v2_without_qoder_finalizes_double_sign(tmp_path, session_env):
    repo = _make_repo(tmp_path)
    wp_tip, merge_commit, base = _merge_wp_branch(repo)

    status = _make_status(
        schema_version=V2,
        git_commit=wp_tip,
        branch="feat/wp-a",
        base_branch=base,
        qoder=None,
    )
    status_path = _write_status(repo, status)

    res = _finalize(repo, status_path, session_env)
    _assert_ok(res, merge_commit)

    final = json.loads(status_path.read_text(encoding="utf-8"))
    assert final["state"] == "MERGED"
    assert final["git"]["merged_commit"] == merge_commit
    assert "qoder_security" not in final
