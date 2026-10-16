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


def _write_plan_status(repo: Path, base_branch: str) -> None:
    """WP-01: declare the authoritative branch beside the fixture status.

    The status-source predicate resolves the authoritative branch from the PLAN
    status in the judged file's own plan dir; without it the run fails closed as
    unresolved. The declaration is the repo's real default branch, held by the
    primary checkout these fixtures use.
    """
    plan_path = repo / PLAN_DIR / "PLAN-01.status.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "agentic-plan-status/v1",
                "plan_id": "PLAN-01",
                "git": {"base_branch": base_branch, "target_branch": "main"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


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
    _write_plan_status(repo, base)
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


# A syntactically valid gate module whose predicate raises when CALLED.
# Shadows ONLY agentic_loop.gate via PYTHONPATH (see the test below);
# agentic_loop.resolve_paths / agentic_loop.validate_wp_status keep loading
# from the real src tree through the namespace-extending __init__.
_BROKEN_GATE_INIT = '''\
"""WP-21 A29 hardening fixture: valid syntax, raises on call."""
from pathlib import Path


def path_is_in_worktree(path: Path) -> bool:
    raise RuntimeError("injected broken predicate (WP-21 A29 hardening)")
'''

# Extends the shadow package's search path with the real agentic_loop
# directory so sibling modules (resolve_paths, validate_wp_status) still
# import normally while gate resolves to the injected copy first.
_SHADOW_PACKAGE_INIT = '''\
import os

__path__.append(os.path.join(os.environ["AGENTIC_REAL_SRC"], "agentic_loop"))
'''


def test_finalize_fails_closed_when_predicate_raises(
    tmp_path: Path, session_env
) -> None:
    # WP-21 / A29 hardening characterization test. finalize_merge.sh reads the
    # worktree verdict via a PLAIN command-substitution assignment
    # (`in_worktree=$(...)`); under `set -euo pipefail` a crashed predicate
    # aborts the script before any refusal/finalize logic — fail-closed.
    # Inject a gate module that is syntactically valid but raises on call
    # (shadowing ONLY agentic_loop.gate via PYTHONPATH precedence), and pin:
    # non-zero exit AND no FINALIZE_OK anywhere in the output. This locks the
    # measured behavior (rc=1, zero later steps executed) so nobody can move
    # the assignment into an `if` condition or append `|| true` — either
    # would suspend `set -e` and turn the crash into a skipped refusal.
    #
    # A35 (WP-21 rev2): the status must be genuinely finalizable — built from
    # the same existing fixtures as the happy-path test above and committed
    # into the repo index — otherwise the run dies at a LATER step
    # (`FINALIZE_FAIL: status file not found`) even under a fail-open
    # mutation, and the two negative assertions hold vacuously. The positive
    # control at the end (same status, no injection -> FINALIZE_OK) proves
    # the case really reaches the finalize endpoint.
    repo, base, wp_tip, merge_commit = _make_repo_with_merged_wp(tmp_path)
    status_path = repo / PLAN_DIR / STATUS_NAME
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        json.dumps(_status_without_merged_commit(base, wp_tip), indent=2),
        encoding="utf-8",
    )
    _write_plan_status(repo, base)
    # finalize requires the status to be tracked in the main repo index;
    # write alone would make the run fail before the verdict read.
    _run_git(repo, "add", str(PLAN_DIR / STATUS_NAME), str(PLAN_DIR / "PLAN-01.status.json"))
    _run_git(repo, "commit", "-q", "-m", "add WP-FC status")

    inject = tmp_path / "inject"
    (inject / "agentic_loop" / "gate").mkdir(parents=True)
    (inject / "agentic_loop" / "__init__.py").write_text(
        _SHADOW_PACKAGE_INIT, encoding="utf-8"
    )
    (inject / "agentic_loop" / "gate" / "__init__.py").write_text(
        _BROKEN_GATE_INIT, encoding="utf-8"
    )

    env = dict(session_env)
    env["AGENTIC_REAL_SRC"] = str(PKG_SRC)
    env["PYTHONPATH"] = str(inject) + os.pathsep + env["PYTHONPATH"]

    # Premise: through the injected PYTHONPATH the predicate raises, while
    # the sibling modules finalize also needs still import from real src.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import agentic_loop.gate as g, agentic_loop.resolve_paths, "
            "agentic_loop.validate_wp_status; "
            "g.path_is_in_worktree(__import__('pathlib').Path('.'))",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert probe.returncode != 0
    assert "injected broken predicate" in probe.stderr

    res = subprocess.run(
        ["bash", str(FINALIZE_SH), str(PLAN_DIR / STATUS_NAME)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "FINALIZE_OK" not in res.stdout
    assert "FINALIZE_OK" not in res.stderr

    # Positive control (A35): the SAME status without the injection reaches
    # FINALIZE_OK, proving the negative run above died at the verdict read
    # (the point under test), not at some earlier setup step.
    control = subprocess.run(
        ["bash", str(FINALIZE_SH), str(PLAN_DIR / STATUS_NAME)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=session_env,
    )
    assert control.returncode == 0, (
        control.returncode,
        control.stdout,
        control.stderr,
    )
    assert control.stdout.strip() == f"FINALIZE_OK merged_commit={merge_commit}"
