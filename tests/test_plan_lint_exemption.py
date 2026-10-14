"""WP-03 rev5: audited, merge-only plan-lint exemptions.

Every behavioural fixture uses real Git subprocesses.  Source-binding cases use
an actual primary repository and, where relevant, an actual linked worktree;
only ``resolve_paths.main_repo`` is redirected to that temporary primary repo.
"""
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


EXEMPTION = {
    "approved": True,
    "approver": "release-owner",
    "justification": "preserve audited re-freeze history",
    "reviewed_at": "2026-10-14T08:00:00Z",
}


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _head(repo: Path, ref: str = "HEAD") -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _plan(*, state: str = "READY_TO_MERGE", exemption: object = None) -> dict:
    data = {
        "schema_version": "agentic-plan-status/v1",
        "plan_id": "PLAN-1",
        "iteration_id": "it-1",
        "state": state,
        "title": "exemption test",
        "git": {
            "base_branch": "plan/it-1",
            "target_branch": "main",
            "merged_commit": "",
        },
        "work_packages": ["WP-1"],
        "timestamps": {"created_at": "", "updated_at": ""},
    }
    if exemption is not None:
        data["lint_exemption"] = exemption
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _make_repo(
    root: Path,
    *,
    dirty: bool = True,
    wp_merged: bool = True,
    exemption: object = EXEMPTION,
    state: str = "READY_TO_MERGE",
) -> tuple[Path, Path, str]:
    """Create a primary repo with a real target/integration commit graph."""
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "WP-03 Test")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", "-M", "main")

    _git(repo, "checkout", "-q", "-b", "plan/it-1")
    wp_path = repo / "docs/plans/it-1/WP-1.status.json"
    _write_json(wp_path, {"state": "APPROVED", "git": {}, "plan_id": "PLAN-1"})
    _git(repo, "add", "docs/plans/it-1/WP-1.status.json")
    _git(repo, "commit", "-q", "-m", "freeze WP-1")

    if dirty:
        _write_json(
            wp_path,
            {
                "state": "APPROVED",
                "review": {"decision": "ACCEPT"},
                "git": {},
                "plan_id": "PLAN-1",
            },
        )
        _git(repo, "add", "docs/plans/it-1/WP-1.status.json")
        _git(repo, "commit", "-q", "-m", "review sync ACCEPT")

    (repo / "implementation.txt").write_text("implemented\n", encoding="utf-8")
    _git(repo, "add", "implementation.txt")
    _git(repo, "commit", "-q", "-m", "implement WP-1")
    wp_tip = _head(repo)

    final_state = "MERGED" if wp_merged else "APPROVED_FOR_MERGE"
    merged_commit = wp_tip if wp_merged else ""
    _write_json(
        wp_path,
        {
            "state": final_state,
            "git": {"merged_commit": merged_commit},
            "plan_id": "PLAN-1",
        },
    )
    _git(repo, "add", "docs/plans/it-1/WP-1.status.json")
    _git(repo, "commit", "-q", "-m", "finalize WP-1")
    integration_tip = _head(repo)

    _git(repo, "checkout", "-q", "main")
    plan_path = repo / "docs/plans/it-1/PLAN-1.status.json"
    _write_json(plan_path, _plan(state=state, exemption=exemption))
    _git(repo, "add", "docs/plans/it-1/PLAN-1.status.json")
    _git(repo, "commit", "-q", "-m", "track plan status")
    return repo, plan_path, integration_tip


def _bind_primary(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    monkeypatch.setattr(plan_cmd._rp, "main_repo", lambda: repo)
    monkeypatch.chdir(repo)


def _merge_rc(plan_path: Path | str) -> int:
    try:
        return plan_cmd.cmd_merge(str(plan_path))
    except SystemExit as exc:
        return int(exc.code)


def _merge_count(repo: Path) -> int:
    out = _git(repo, "rev-list", "--merges", "--count", "main").stdout.strip()
    return int(out)


def test_e0_dirty_no_exemption_must_fail(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_repo(tmp_path, exemption=None)
    _bind_primary(monkeypatch, repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "status-sync commits present" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e1_dirty_with_valid_exemption_merges(tmp_path, monkeypatch, capsys):
    repo, plan_path, integration_tip = _make_repo(tmp_path)
    _bind_primary(monkeypatch, repo)

    assert _merge_rc(plan_path) == plan_cmd.RC_OK
    output = capsys.readouterr().out
    assert "PLAN_MERGE_OK" in output
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
    assert len(parents) == 3
    assert integration_tip in parents


def test_e2_lint_output_unchanged(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_repo(tmp_path)
    _bind_primary(monkeypatch, repo)

    _write_json(plan_path, _plan(exemption=None))
    assert plan_cmd.cmd_lint(str(plan_path)) == plan_cmd.RC_STOP
    without = capsys.readouterr().out

    _write_json(plan_path, _plan(exemption=EXEMPTION))
    assert plan_cmd.cmd_lint(str(plan_path)) == plan_cmd.RC_STOP
    with_exemption = capsys.readouterr().out

    assert with_exemption == without
    assert "DIRTY" in without
    assert "review sync ACCEPT" in without
    assert "PLAN_LINT: dirty" in without


INVALID_EXEMPTIONS = [
    pytest.param({k: v for k, v in EXEMPTION.items() if k != "approved"}, id="missing-approved"),
    pytest.param({k: v for k, v in EXEMPTION.items() if k != "approver"}, id="missing-approver"),
    pytest.param({k: v for k, v in EXEMPTION.items() if k != "justification"}, id="missing-justification"),
    pytest.param({k: v for k, v in EXEMPTION.items() if k != "reviewed_at"}, id="missing-reviewed-at"),
    pytest.param({**EXEMPTION, "approved": False}, id="approved-false"),
    pytest.param({**EXEMPTION, "approved": "true"}, id="approved-string"),
    pytest.param({**EXEMPTION, "approved": 1}, id="approved-integer"),
    pytest.param({**EXEMPTION, "approver": "   "}, id="approver-blank"),
    pytest.param({**EXEMPTION, "justification": "   "}, id="justification-blank"),
    pytest.param({**EXEMPTION, "reviewed_at": "   "}, id="reviewed-at-blank"),
]


@pytest.mark.parametrize("invalid", INVALID_EXEMPTIONS)
def test_e3_partial_exemption_matrix_fails_closed(
    tmp_path, monkeypatch, capsys, invalid
):
    repo, plan_path, _ = _make_repo(tmp_path, exemption=invalid)
    _bind_primary(monkeypatch, repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "status-sync commits present" in capsys.readouterr().err
    assert _head(repo, "main") == before


def _untrusted_source(
    shape: str, root: Path, repo: Path, tracked_plan: Path
) -> Path:
    data = _plan(exemption=EXEMPTION)
    if shape == "linked-worktree":
        worktree = root / "linked"
        _git(repo, "worktree", "add", "-q", str(worktree), "plan/it-1")
        path = worktree / "docs/plans/it-1/LOCAL.status.json"
        _write_json(path, data)
        return path
    if shape == "outside-repo":
        path = root / "outside/PLAN.status.json"
        _write_json(path, data)
        return path
    if shape == "main-untracked":
        path = repo / "docs/plans/it-1/UNTRACKED.status.json"
        _write_json(path, data)
        return path
    if shape == "tracked-symlink-to-untracked":
        target = repo / "docs/plans/it-1/untracked-target.json"
        _write_json(target, data)
        link = repo / "docs/plans/it-1/TRACKED-LINK.status.json"
        link.symlink_to(target.name)
        _git(repo, "add", "docs/plans/it-1/TRACKED-LINK.status.json")
        _git(repo, "commit", "-q", "-m", "track logical symlink only")
        assert _git(
            repo,
            "ls-files",
            "--error-unmatch",
            "--",
            "docs/plans/it-1/TRACKED-LINK.status.json",
        ).returncode == 0
        assert _git(
            repo,
            "ls-files",
            "--error-unmatch",
            "--",
            "docs/plans/it-1/untracked-target.json",
            check=False,
        ).returncode != 0
        return link
    raise AssertionError(shape)


@pytest.mark.parametrize(
    "shape",
    [
        "linked-worktree",
        "outside-repo",
        "main-untracked",
        "tracked-symlink-to-untracked",
    ],
)
def test_e9_exemption_source_must_be_main_repo_tracked(
    tmp_path, monkeypatch, capsys, shape
):
    repo, tracked_plan, _ = _make_repo(tmp_path / "primary")
    _bind_primary(monkeypatch, repo)
    source = _untrusted_source(shape, tmp_path, repo, tracked_plan)
    before = _head(repo, "main")

    assert _merge_rc(source.resolve() if shape != "tracked-symlink-to-untracked" else source) == plan_cmd.RC_FAIL
    error = capsys.readouterr().err
    assert "lint exemption source is untrusted" in error
    assert _head(repo, "main") == before


def test_e4_exemption_does_not_waive_convergence(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_repo(tmp_path, wp_merged=False)
    _bind_primary(monkeypatch, repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "state=APPROVED_FOR_MERGE (not MERGED)" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e5_exemption_does_not_waive_state(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_repo(tmp_path, state="ACTIVE")
    _bind_primary(monkeypatch, repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "state must be READY_TO_MERGE" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e6_exemption_is_logged(tmp_path, monkeypatch, capsys):
    repo, plan_path, _ = _make_repo(tmp_path)
    _bind_primary(monkeypatch, repo)

    assert _merge_rc(plan_path) == plan_cmd.RC_OK
    output = capsys.readouterr().out
    assert EXEMPTION["approver"] in output
    assert EXEMPTION["justification"] in output


def test_e7_no_bypass_flag_or_environment_variable():
    source = (SRC / "agentic_loop/plan_cmd.py").read_text(encoding="utf-8").lower()
    for marker in ("skip-lint", "skip_lint", "force-merge", "force_merge"):
        assert marker not in source
    assert "agentic_skip_lint" not in source
    assert not any(
        "skip" in token and "lint" in token
        for token in source.replace('"', " ").replace("'", " ").split()
    )


def test_e8_clean_plan_unaffected(tmp_path, monkeypatch, capsys):
    outcomes = []
    for name, exemption in (("without", None), ("with", EXEMPTION)):
        repo, plan_path, integration_tip = _make_repo(
            tmp_path / name, dirty=False, exemption=exemption
        )
        _bind_primary(monkeypatch, repo)
        rc = _merge_rc(plan_path)
        output = capsys.readouterr().out
        parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
        outcomes.append((rc, len(parents), integration_tip in parents, "PLAN_LINT_EXEMPTION" in output))

    assert outcomes == [
        (plan_cmd.RC_OK, 3, True, False),
        (plan_cmd.RC_OK, 3, True, False),
    ]


def test_e10_exemption_does_not_waive_autonomy(
    tmp_path, monkeypatch, capsys
):
    repo, plan_path, _ = _make_repo(tmp_path)
    _bind_primary(monkeypatch, repo)
    config = repo / ".agentic/config.toml"
    config.parent.mkdir()
    config.write_text(
        '[autonomy]\ndefault_mode = "ask"\nultra_auto = ["local_merge_no_ff"]\nalways_stop = []\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("AGENTIC_AUTONOMY_APPROVE", raising=False)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_STOP
    assert "autonomy requires human approval" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e11_exemption_does_not_waive_target_branch(
    tmp_path, monkeypatch, capsys
):
    repo, plan_path, _ = _make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "not-main")
    _bind_primary(monkeypatch, repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "must run on target branch main" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e12_exemption_does_not_waive_already_merged(
    tmp_path, monkeypatch, capsys
):
    repo, plan_path, _ = _make_repo(tmp_path)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "plan/it-1")
    _bind_primary(monkeypatch, repo)
    before_tip = _head(repo, "main")
    before_merges = _merge_count(repo)

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "already merged" in capsys.readouterr().err
    assert _head(repo, "main") == before_tip
    assert _merge_count(repo) == before_merges


def test_schema_accepts_optional_exemption_but_does_not_require_it():
    assert plan_cmd.validate(_plan(exemption=EXEMPTION)) == []
    assert plan_cmd.validate(_plan(exemption=None)) == []
