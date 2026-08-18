"""Tests for `agentic plan` (one plan = one merged commit)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import plan_cmd  # noqa: E402


# ---------------------------------------------------------------------------
# Pure schema validation
# ---------------------------------------------------------------------------

def _valid_plan(**overrides):
    plan = {
        "schema_version": "agentic-plan-status/v1",
        "plan_id": "PLAN-1",
        "iteration_id": "it-1",
        "state": "READY_TO_MERGE",
        "title": "demo",
        "git": {"base_branch": "plan/it-1", "target_branch": "main",
                "merged_commit": ""},
        "work_packages": ["WP-1"],
        "timestamps": {"created_at": "", "updated_at": ""},
    }
    plan.update(overrides)
    return plan


def test_validate_accepts_valid_plan():
    assert plan_cmd.validate(_valid_plan()) == []


def test_validate_rejects_missing_fields():
    errors = plan_cmd.validate({"schema_version": "agentic-plan-status/v1"})
    assert any("missing top-level fields" in e for e in errors)


def test_validate_rejects_bad_schema_version():
    errors = plan_cmd.validate(_valid_plan(schema_version="agentic-plan-status/v9"))
    assert any("schema_version must be" in e for e in errors)


def test_validate_rejects_base_equals_target():
    plan = _valid_plan()
    plan["git"]["base_branch"] = "main"
    plan["git"]["target_branch"] = "main"
    errors = plan_cmd.validate(plan)
    assert any("must differ" in e for e in errors)


def test_validate_rejects_merged_without_merged_commit():
    plan = _valid_plan(state="MERGED", git={"base_branch": "plan/it-1",
                                            "target_branch": "main",
                                            "merged_commit": ""})
    errors = plan_cmd.validate(plan)
    assert any("merged_commit is required" in e for e in errors)


def test_validate_rejects_empty_work_packages_in_ready_to_merge():
    plan = _valid_plan(work_packages=[])
    errors = plan_cmd.validate(plan)
    assert any("work_packages must not be empty" in e for e in errors)


# ---------------------------------------------------------------------------
# Git helpers (mirror the production helpers; run against tmp repos only)
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str, check: bool = True):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=check, capture_output=True, text=True
    )


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


# ---------------------------------------------------------------------------
# Repo builder: the integration branch carries each WP's status file committed
# exactly as freeze (add) -> finalize (state=MERGED). Optional `sync` inserts a
# "review sync" commit that only touches the status file (what the lint gate
# must reject).
# ---------------------------------------------------------------------------

def _make_converged_repo(tmp_path: Path, merged: bool = True, sync: bool = False,
                         wp_plan_id: str = "PLAN-1") -> tuple:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@e.com")
    _git(repo, "config", "user.name", "T")
    (repo / "seed.txt").write_text("s\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", "-M", "main")

    # integration branch cut from main
    _git(repo, "checkout", "-q", "-b", "plan/it-1")

    # freeze: commit WP-1 status (APPROVED) on the integration branch
    wp_status = repo / "docs" / "plans" / "it-1" / "WP-1.status.json"
    wp_status.parent.mkdir(parents=True)
    wp_status.write_text(json.dumps(
        {"state": "APPROVED", "git": {}, "plan_id": wp_plan_id}
    ))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "freeze WP-1")

    # one WP branch merged (no-ff) into the integration branch
    _git(repo, "checkout", "-q", "-b", "feat/wp1")
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "wp1")
    _git(repo, "checkout", "-q", "plan/it-1")
    _git(repo, "merge", "-q", "--no-ff", "feat/wp1", "-m", "merge wp1")
    wp_merge_commit = _head(repo)

    if sync:
        # an intermediate "review sync" commit touching ONLY the status file
        wp_status.write_text(json.dumps(
            {"state": "APPROVED", "review": {"decision": "ACCEPT"},
             "git": {}, "plan_id": wp_plan_id}
        ))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "review sync ACCEPT")

    # finalize: commit WP-1 status (MERGED or not) on the integration branch
    if merged:
        final = {"state": "MERGED", "git": {"merged_commit": wp_merge_commit},
                 "plan_id": wp_plan_id}
    else:
        final = {"state": "APPROVED_FOR_MERGE", "git": {}, "plan_id": wp_plan_id}
    wp_status.write_text(json.dumps(final))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "finalize WP-1")

    integration_tip = _head(repo)
    _git(repo, "checkout", "-q", "main")

    # plan status lives (untracked) on main until finalize stamps it MERGED
    plan_dir = repo / "docs" / "plans" / "it-1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "PLAN-1.status.json").write_text(json.dumps(_valid_plan()))

    return repo, "docs/plans/it-1/PLAN-1.status.json", integration_tip


@pytest.fixture
def converged(tmp_path, monkeypatch):
    repo, plan_path, integration_tip = _make_converged_repo(tmp_path, merged=True)
    monkeypatch.chdir(repo)
    return repo, plan_path, integration_tip


# ---------------------------------------------------------------------------
# Convergence helper (git-based)
# ---------------------------------------------------------------------------

def test_require_converged_fails_closed_on_non_merged(tmp_path, monkeypatch):
    repo, _, _ = _make_converged_repo(tmp_path, merged=False)
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit) as ei:
        plan_cmd._require_converged(_valid_plan(), repo)
    assert ei.value.code == plan_cmd.RC_FAIL


def test_require_converged_catches_plan_id_mismatch(tmp_path, monkeypatch):
    repo, _, _ = _make_converged_repo(tmp_path, merged=True, wp_plan_id="PLAN-OTHER")
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit) as ei:
        plan_cmd._require_converged(_valid_plan(), repo)
    assert ei.value.code == plan_cmd.RC_FAIL


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def test_check_reports_ready_to_merge(converged, capsys):
    repo, plan_path, _ = converged
    # all WPs MERGED, but the plan is not yet merged into main -> not fully converged
    assert plan_cmd.cmd_check(plan_path) == plan_cmd.RC_STOP
    out = capsys.readouterr().out
    assert "PLAN_CHECK plan_id=PLAN-1" in out
    assert "wp WP-1 MERGED" in out
    assert "merge NOT detected" in out
    assert "not converged" in out


def test_check_reports_converged_after_merge(converged, capsys):
    repo, plan_path, _ = converged
    assert plan_cmd.cmd_merge(plan_path) == plan_cmd.RC_OK
    assert plan_cmd.cmd_check(plan_path) == plan_cmd.RC_OK
    out = capsys.readouterr().out
    assert "converged" in out


def test_check_reports_not_converged_when_wp_pending(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_converged_repo(tmp_path, merged=False)
    monkeypatch.chdir(repo)
    assert plan_cmd.cmd_check(plan_path) == plan_cmd.RC_STOP
    out = capsys.readouterr().out
    assert "not merged" in out
    assert "not converged" in out


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

def test_merge_creates_single_merge_commit(converged):
    repo, plan_path, integration_tip = converged
    assert plan_cmd.cmd_merge(plan_path) == plan_cmd.RC_OK
    # main now contains a.txt via exactly one plan-level merge commit
    assert (repo / "a.txt").is_file()
    merge_commit = _head(repo)
    parents = _git(repo, "rev-list", "--parents", "-n", "1", merge_commit).stdout.split()
    assert len(parents) == 3  # two parents => a merge commit
    assert integration_tip in parents  # integration branch tip is the second parent


def test_merge_fails_closed_when_wp_not_merged(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_converged_repo(tmp_path, merged=False)
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit) as ei:
        plan_cmd.cmd_merge(plan_path)
    assert ei.value.code == plan_cmd.RC_FAIL
    assert "not MERGED" in capsys.readouterr().err
    assert not (repo / "a.txt").exists()


def test_merge_requires_ready_to_merge_state(converged, capsys):
    repo, plan_path, _ = converged
    plan_file = repo / "docs" / "plans" / "it-1" / "PLAN-1.status.json"
    data = json.loads(plan_file.read_text())
    data["state"] = "ACTIVE"
    plan_file.write_text(json.dumps(data))
    assert plan_cmd.cmd_merge(plan_path) == plan_cmd.RC_FAIL
    assert "READY_TO_MERGE" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# lint (freeze/merge/finalize commit discipline)
# ---------------------------------------------------------------------------

def test_lint_clean(converged, capsys):
    repo, plan_path, _ = converged
    assert plan_cmd.cmd_lint(plan_path) == plan_cmd.RC_OK
    out = capsys.readouterr().out
    assert "wp WP-1 clean (freeze + finalize)" in out
    assert "PLAN_LINT: clean" in out


def test_lint_detects_sync_commit(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_converged_repo(tmp_path, merged=True, sync=True)
    monkeypatch.chdir(repo)
    assert plan_cmd.cmd_lint(plan_path) == plan_cmd.RC_STOP
    out = capsys.readouterr().out
    assert "status-sync commit(s)" in out
    assert "review sync ACCEPT" in out
    assert "PLAN_LINT: dirty" in out


def test_merge_fails_closed_on_sync_commit(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_converged_repo(tmp_path, merged=True, sync=True)
    monkeypatch.chdir(repo)
    assert plan_cmd.cmd_merge(plan_path) == plan_cmd.RC_FAIL
    assert "status-sync commit" in capsys.readouterr().err
    # nothing merged into main
    assert not (repo / "a.txt").exists()


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------

def test_finalize_stamps_merged(converged):
    repo, plan_path, _ = converged
    assert plan_cmd.cmd_merge(plan_path) == plan_cmd.RC_OK
    assert plan_cmd.cmd_finalize(plan_path) == plan_cmd.RC_OK
    plan_file = repo / "docs" / "plans" / "it-1" / "PLAN-1.status.json"
    data = json.loads(plan_file.read_text())
    assert data["state"] == "MERGED"
    assert data["git"]["merged_commit"]
    assert data["timestamps"]["updated_at"]


def test_finalize_fails_without_merge(converged, capsys):
    repo, plan_path, _ = converged
    # all WPs MERGED but the integration branch was never merged into main
    assert plan_cmd.cmd_finalize(plan_path) == plan_cmd.RC_FAIL
    assert "merge not detected" in capsys.readouterr().err


def test_finalize_idempotent(converged, capsys):
    repo, plan_path, _ = converged
    assert plan_cmd.cmd_merge(plan_path) == plan_cmd.RC_OK
    assert plan_cmd.cmd_finalize(plan_path) == plan_cmd.RC_OK
    assert plan_cmd.cmd_finalize(plan_path) == plan_cmd.RC_OK
    assert "already finalized" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def test_plan_subcommand_in_cli_usage(tmp_path, monkeypatch):
    from agentic_loop import cli

    monkeypatch.chdir(tmp_path)
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main([])
    assert rc == 0
    assert "plan" in buf.getvalue()
