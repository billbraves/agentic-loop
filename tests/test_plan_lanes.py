"""Tests for `agentic plan lanes` and the dual-form `work_packages` schema."""
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
# Pure schema validation: dual-form `work_packages`
# ---------------------------------------------------------------------------

def _plan(work_packages, **overrides):
    plan = {
        "schema_version": "agentic-plan-status/v1",
        "plan_id": "PLAN-1",
        "iteration_id": "it-1",
        "state": "ACTIVE",
        "git": {"base_branch": "plan/it-1", "target_branch": "main",
                "merged_commit": ""},
        "work_packages": work_packages,
        "timestamps": {"created_at": "", "updated_at": ""},
    }
    plan.update(overrides)
    return plan


# --- legacy string form keeps passing (regression / dual-form proof) ---------

def test_validate_accepts_legacy_string_form():
    assert plan_cmd.validate(_plan(["WP-1", "WP-2"])) == []


# --- new object form ---------------------------------------------------------

def test_validate_accepts_object_form_with_full_fields():
    wps = [
        {"id": "WP-1", "lane": "lane-gate", "depends_on": []},
        {"id": "WP-2", "lane": "lane-gate", "depends_on": ["WP-1"]},
    ]
    assert plan_cmd.validate(_plan(wps)) == []


def test_validate_object_form_lane_and_deps_optional():
    wps = [{"id": "WP-1"}]
    assert plan_cmd.validate(_plan(wps)) == []


def test_validate_mixed_forms():
    wps = ["WP-1", {"id": "WP-2", "lane": "lane-x", "depends_on": ["WP-1"]}]
    assert plan_cmd.validate(_plan(wps)) == []


def test_validate_rejects_object_without_id():
    errors = plan_cmd.validate(_plan([{"lane": "lane-x"}]))
    assert any("need a non-empty 'id'" in e for e in errors)


def test_validate_rejects_empty_string_entry():
    errors = plan_cmd.validate(_plan([""]))
    assert any("non-empty strings or objects" in e for e in errors)


def test_validate_rejects_type_error_entry():
    # Regression guard: a non-str / non-dict entry must be cleanly rejected
    # (PLAN_INVALID / RC_FAIL), not crash the topology block with an
    # AttributeError (an int/None has no `.get`).
    errors = plan_cmd.validate(_plan([123]))
    assert any("work_packages entries must be strings or objects" in e for e in errors)


def test_validate_rejects_duplicate_ids():
    errors = plan_cmd.validate(_plan(["WP-1", "WP-1"]))
    assert any("duplicate work_packages id" in e for e in errors)


# --- topology: missing dependency -------------------------------------------

def test_validate_rejects_depends_on_missing_wp():
    wps = [{"id": "WP-1", "depends_on": ["WP-NOPE"]}]
    errors = plan_cmd.validate(_plan(wps))
    assert any("depends_on missing WP 'WP-NOPE'" in e for e in errors)


# --- topology: cycle ---------------------------------------------------------

def test_validate_rejects_dependency_cycle():
    wps = [
        {"id": "WP-1", "depends_on": ["WP-2"]},
        {"id": "WP-2", "depends_on": ["WP-1"]},
    ]
    errors = plan_cmd.validate(_plan(wps))
    assert any("dependency cycle detected" in e for e in errors)


def test_validate_rejects_self_cycle():
    wps = [{"id": "WP-1", "depends_on": ["WP-1"]}]
    errors = plan_cmd.validate(_plan(wps))
    assert any("dependency cycle detected" in e for e in errors)


# ---------------------------------------------------------------------------
# Pure ready-set computation (`_lanes_ready`)
# ---------------------------------------------------------------------------

def test_lanes_ready_no_deps_all_ready():
    wps = ["WP-1", "WP-2"]
    result = plan_cmd._lanes_ready(wps, {})
    assert set(result["ready"]) == {"WP-1", "WP-2"}
    assert result["blocked"] == []
    assert result["done"] == []


def test_lanes_ready_respects_dependencies():
    wps = [
        {"id": "WP-1", "depends_on": []},
        {"id": "WP-2", "depends_on": ["WP-1"]},
    ]
    # WP-1 not merged yet -> WP-2 blocked
    result = plan_cmd._lanes_ready(wps, {"WP-1": "APPROVED", "WP-2": "APPROVED"})
    assert result["ready"] == ["WP-1"]
    assert ("WP-2", ["WP-1"]) in result["blocked"]


def test_lanes_ready_dep_merged_unblocks():
    wps = [
        {"id": "WP-1", "depends_on": []},
        {"id": "WP-2", "depends_on": ["WP-1"]},
    ]
    result = plan_cmd._lanes_ready(wps, {"WP-1": "MERGED", "WP-2": "APPROVED"})
    assert result["ready"] == ["WP-2"]
    assert result["done"] == ["WP-1"]

def test_lanes_ready_done_classified():
    wps = ["WP-1", "WP-2"]
    result = plan_cmd._lanes_ready(wps, {"WP-1": "MERGED", "WP-2": "APPROVED"})
    assert result["done"] == ["WP-1"]
    assert result["ready"] == ["WP-2"]


def test_lanes_ready_is_pure_no_io():
    # Passing a non-existent state dict and iterable should not touch IO. The
    # function never reads files, clock, or env.
    wps = ["WP-1", "WP-2", "WP-3"]
    assert plan_cmd._lanes_ready(wps, {})["ready"] == ["WP-1", "WP-2", "WP-3"]


# ---------------------------------------------------------------------------
# Normalization defaults
# ---------------------------------------------------------------------------

def test_normalize_string_entry_defaults():
    norm = plan_cmd._normalize_work_packages(["WP-1"])
    assert norm == [{"id": "WP-1", "lane": "default", "depends_on": []}]


def test_normalize_object_entry_defaults():
    norm = plan_cmd._normalize_work_packages([{"id": "WP-1"}])
    assert norm[0]["lane"] == "default"
    assert norm[0]["depends_on"] == []


def test_normalize_object_entry_keeps_lane_and_deps():
    norm = plan_cmd._normalize_work_packages(
        [{"id": "WP-1", "lane": "lane-a", "depends_on": ["WP-0"]}]
    )
    assert norm[0]["lane"] == "lane-a"
    assert norm[0]["depends_on"] == ["WP-0"]


# ---------------------------------------------------------------------------
# `_status_git_paths` adapts to object form (consumption point #2)
# ---------------------------------------------------------------------------

def test_status_git_paths_handles_object_form(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@e.com")
    _git(repo, "config", "user.name", "T")
    (repo / "seed.txt").write_text("s\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", "-M", "main")
    _git(repo, "checkout", "-q", "-b", "plan/it-1")
    # put a status blob for WP-1 on the integration branch
    wp_status = repo / "docs" / "plans" / "it-1" / "WP-1.status.json"
    wp_status.parent.mkdir(parents=True, exist_ok=True)
    wp_status.write_text(json.dumps({"state": "APPROVED"}))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "freeze WP-1")

    monkeypatch.chdir(repo)
    data = _plan([{"id": "WP-1", "lane": "lane-a", "depends_on": []}])
    paths = plan_cmd._status_git_paths(data, repo)
    # must resolve WP-1 as a string id, not a dict
    assert paths == [("WP-1", "docs/plans/it-1/WP-1.status.json")]


# ---------------------------------------------------------------------------
# `cmd_lanes` end-to-end (consumption point #3 via the new subcommand)
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str, check: bool = True):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=check, capture_output=True, text=True
    )


def _make_lanes_repo(tmp_path: Path) -> tuple:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@e.com")
    _git(repo, "config", "user.name", "T")
    (repo / "seed.txt").write_text("s\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", "-M", "main")
    _git(repo, "checkout", "-q", "-b", "plan/it-1")

    # WP-1 APPROVED, WP-2 APPROVED, WP-3 MERGED (so WP-3 is DONE)
    states = {
        "WP-1": {"state": "APPROVED", "git": {}, "plan_id": "PLAN-1"},
        "WP-2": {"state": "APPROVED", "git": {}, "plan_id": "PLAN-1"},
        "WP-3": {"state": "MERGED", "git": {"merged_commit": "x" * 40},
                 "plan_id": "PLAN-1"},
    }
    for wp_id, st in states.items():
        p = repo / "docs" / "plans" / "it-1" / "{}.status.json".format(wp_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "freeze WPs")

    plan_dir = repo / "docs" / "plans" / "it-1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return repo, plan_dir


@pytest.fixture
def lanes_repo(tmp_path, monkeypatch):
    repo, plan_dir = _make_lanes_repo(tmp_path)
    monkeypatch.chdir(repo)
    return repo, plan_dir


def test_cmd_lanes_reports_ready_blocked_done(lanes_repo, capsys):
    repo, plan_dir = lanes_repo
    wps = [
        {"id": "WP-1", "lane": "lane-a", "depends_on": []},
        {"id": "WP-2", "lane": "lane-a", "depends_on": ["WP-1"]},
        {"id": "WP-3", "lane": "lane-b", "depends_on": []},
    ]
    plan_path = plan_dir / "PLAN-1.status.json"
    plan_path.write_text(json.dumps(_plan(wps)))

    assert plan_cmd.cmd_lanes(str(plan_path)) == plan_cmd.RC_OK
    out = capsys.readouterr().out
    assert "WP-1 [lane=lane-a]" in out       # READY (no deps)
    assert "WP-2 waiting on WP-1" in out     # BLOCKED (dep not merged)
    assert "WP-3" in out and "DONE" in out and "WP-3" in out  # WP-3 done


def test_cmd_lanes_same_lane_serialization(lanes_repo, capsys):
    repo, plan_dir = lanes_repo
    # Both WP-1 and WP-2 are in the same lane, both have no deps and are READY.
    # Only ONE may be reported READY; the other must be deferred to same-lane.
    wps = [
        {"id": "WP-1", "lane": "lane-a", "depends_on": []},
        {"id": "WP-2", "lane": "lane-a", "depends_on": []},
    ]
    plan_path = plan_dir / "PLAN-1.status.json"
    plan_path.write_text(json.dumps(_plan(wps)))

    assert plan_cmd.cmd_lanes(str(plan_path)) == plan_cmd.RC_OK
    out = capsys.readouterr().out
    assert "WP-1 [lane=lane-a]" in out
    assert "same-lane serialization" in out
    assert "WP-2 waiting on lane lane-a" in out


def test_cmd_lanes_rejects_cycle(lanes_repo, capsys):
    repo, plan_dir = lanes_repo
    wps = [
        {"id": "WP-1", "depends_on": ["WP-2"]},
        {"id": "WP-2", "depends_on": ["WP-1"]},
    ]
    plan_path = plan_dir / "PLAN-1.status.json"
    plan_path.write_text(json.dumps(_plan(wps)))

    with pytest.raises(SystemExit) as ei:
        plan_cmd.cmd_lanes(str(plan_path))
    assert ei.value.code == plan_cmd.RC_FAIL
    assert "dependency cycle detected" in capsys.readouterr().err


def test_cmd_lanes_rejects_missing_dependency(lanes_repo, capsys):
    repo, plan_dir = lanes_repo
    wps = [{"id": "WP-1", "depends_on": ["WP-MISSING"]}]
    plan_path = plan_dir / "PLAN-1.status.json"
    plan_path.write_text(json.dumps(_plan(wps)))

    with pytest.raises(SystemExit) as ei:
        plan_cmd.cmd_lanes(str(plan_path))
    assert ei.value.code == plan_cmd.RC_FAIL
    assert "depends_on missing WP" in capsys.readouterr().err


def test_cmd_lanes_rejects_type_error_entry(lanes_repo, capsys):
    repo, plan_dir = lanes_repo
    plan_path = plan_dir / "PLAN-1.status.json"
    plan_path.write_text(json.dumps(_plan([123])))

    with pytest.raises(SystemExit) as ei:
        plan_cmd.cmd_lanes(str(plan_path))
    assert ei.value.code == plan_cmd.RC_FAIL
    assert "work_packages entries must be strings or objects" in capsys.readouterr().err


def test_cli_help_mentions_lanes():
    parser = plan_cmd.build_parser()
    help_text = parser.format_help()
    assert "lanes" in help_text


def test_cmd_check_handles_object_form(lanes_repo, capsys):
    repo, plan_dir = lanes_repo
    wps = [
        {"id": "WP-1", "lane": "lane-a", "depends_on": []},
        {"id": "WP-2", "lane": "lane-a", "depends_on": ["WP-1"]},
        {"id": "WP-3", "lane": "lane-b", "depends_on": []},
    ]
    plan_path = plan_dir / "PLAN-1.status.json"
    plan_path.write_text(json.dumps(_plan(wps)))

    # Must not crash / not silently mangle WP ids into dicts.
    rc = plan_cmd.cmd_check(str(plan_path))
    out = capsys.readouterr().out
    # WP-3 is MERGED in the fixture; WP-1/WP-2 are not -> pending
    assert "wp WP-3 MERGED" in out
    assert "wp WP-1 state=APPROVED" in out
    assert "wp WP-2 state=APPROVED" in out
    assert rc == plan_cmd.RC_STOP
