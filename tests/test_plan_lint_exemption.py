"""WP-03 rev7: audited, merge-only plan-lint exemptions.

Rev7 deployment model (INV-3b/3c/3d):

- the plan status file is committed ONLY on the integration branch; the
  exemption source check binds the loaded raw bytes to that branch's
  committed canonical blob — never to any checkout's index;
- the file is read through a linked worktree checked out at
  ``git.base_branch``, at the canonical
  ``<iterations_dir>/<iteration_id>/<plan_id>.status.json`` path;
- the real ``git merge --no-ff`` runs in the caller's current worktree, which
  may be a different linked worktree than the physical primary (E13/E14).

Every behavioural fixture uses real Git subprocesses and real linked
worktrees; only the working directory is pointed at the temporary repo.
"""
from __future__ import annotations

import json
import os
import shutil
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

PLAN_REL = "docs/plans/it-1/PLAN-1.status.json"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _git_bytes(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True)


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
) -> tuple[Path, Path, Path, str]:
    """Primary + linked integration worktree fixture.

    The plan status file is committed ONLY on the integration branch
    ``plan/it-1`` and is read from the canonical path of a linked worktree
    checked out at that branch.  The physical primary stays on the target
    branch ``main`` and never receives a copy of the plan file (no fake-green
    pre-commit on the target).
    """
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

    # The plan file is introduced on the integration branch only.
    _write_json(repo / PLAN_REL, _plan(state=state, exemption=exemption))
    _git(repo, "add", PLAN_REL)
    _git(repo, "commit", "-q", "-m", "freeze plan status")
    integration_tip = _head(repo)

    _git(repo, "checkout", "-q", "main")
    wt_plan = root / "wt-plan"
    _git(repo, "worktree", "add", "-q", str(wt_plan), "plan/it-1")
    plan_path = wt_plan / PLAN_REL
    assert plan_path.is_file()
    return repo, plan_path, wt_plan, integration_tip


def _merge_rc(plan_path: Path | str) -> int:
    try:
        return plan_cmd.cmd_merge(str(plan_path))
    except SystemExit as exc:
        return int(exc.code)


def _merge_count(repo: Path) -> int:
    out = _git(repo, "rev-list", "--merges", "--count", "main").stdout.strip()
    return int(out)


def test_e0_dirty_no_exemption_must_fail(tmp_path, monkeypatch, capsys):
    repo, plan_path, _, _ = _make_repo(tmp_path, exemption=None)
    monkeypatch.chdir(repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "status-sync commits present" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e1_dirty_with_valid_exemption_merges(tmp_path, monkeypatch, capsys):
    repo, plan_path, _, integration_tip = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    assert _merge_rc(plan_path) == plan_cmd.RC_OK
    output = capsys.readouterr().out
    assert "PLAN_MERGE_OK" in output
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
    assert len(parents) == 3
    assert integration_tip in parents


def test_e2_lint_output_unchanged(tmp_path, monkeypatch, capsys):
    repo, plan_path, wt_plan, _ = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

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
    repo, plan_path, _, _ = _make_repo(tmp_path, exemption=invalid)
    monkeypatch.chdir(repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "status-sync commits present" in capsys.readouterr().err
    assert _head(repo, "main") == before


def _untrusted_source(shape: str, root: Path, repo: Path, wt_plan: Path) -> Path:
    """Build one rejected exemption-source shape on the real input surface
    (file bytes in a real checkout).  The positive control is the canonical
    committed file in wt_plan, used by E1."""
    data = _plan(exemption=EXEMPTION)
    if shape == "target-worktree-copy":
        # A copy at the canonical path of the TARGET-branch checkout: the
        # branch binding (worktree must be on git.base_branch) rejects it.
        path = repo / PLAN_REL
        _write_json(path, data)
        return path
    if shape == "outside-repo":
        path = root / "outside/PLAN.status.json"
        _write_json(path, data)
        return path
    if shape == "outside-alias-to-canonical":
        # A symlink OUTSIDE the repository pointing at the real, canonical,
        # *committed* plan file of the integration worktree.  The link
        # resolves exactly to the canonical file and holds the committed
        # bytes, so only the lexical-path face of the source check can reject
        # it: a resolve-only (or bytes-only) check would trust this alias.
        target = wt_plan / PLAN_REL
        assert target.is_file()
        link = root / "outside-alias.status.json"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target)
        assert link.is_symlink()
        assert link.resolve() == target.resolve()
        assert link.read_bytes() == target.read_bytes()
        return link
    if shape == "integration-untracked":
        # Inside the integration worktree but not at the canonical path.
        path = wt_plan / "docs/plans/it-1/UNTRACKED.status.json"
        _write_json(path, data)
        return path
    if shape == "canonical-symlink":
        # The canonical path is a symlink to an untracked file: the resolved
        # path no longer equals the canonical path.
        target = wt_plan / "docs/plans/it-1/untracked-target.json"
        _write_json(target, data)
        link = wt_plan / PLAN_REL
        link.unlink()
        link.symlink_to(target.name)
        return link
    if shape == "committed-then-dirty":
        # Canonical path and branch, but the working file was modified after
        # the commit: loaded bytes != committed blob.
        path = wt_plan / PLAN_REL
        _write_json(path, _plan(exemption={**EXEMPTION, "justification": "dirty working-tree variant"}))
        return path
    if shape == "parent-dir-symlink":
        # The integration worktree's whole `docs/` tree is moved OUTSIDE the
        # repository and replaced by a symlink of the same name.  The lexical
        # spelling the caller uses is unchanged, the leaf PLAN file is still a
        # real file (not a link) and its bytes are still the committed blob —
        # so the lexical-equality, leaf-lstat, resolved-equality and
        # committed-blob faces all pass.  Only a per-component lstat of the
        # PARENT path can reject this alias.
        docs = wt_plan / "docs"
        moved = root / "moved-docs"
        if moved.exists() or moved.is_symlink():
            shutil.rmtree(moved, ignore_errors=True)
        moved.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(docs), str(moved))
        docs.symlink_to(moved, target_is_directory=True)
        path = wt_plan / PLAN_REL

        # Self-proof: this is the intended attack shape, and the assertions
        # below also guard against the macOS /var vs /private/var trap that
        # would make the lexical check fail for an UNRELATED reason (a false
        # green).  `root` is tmp_path, which is already resolved.
        assert Path(wt_plan).resolve() == Path(wt_plan)
        assert docs.is_symlink(), "parent component must be a symlink"
        assert not path.is_symlink(), "the leaf PLAN file must not be a link"
        assert path.read_bytes() == _git_bytes(
            wt_plan, "show", "plan/it-1:{}".format(PLAN_REL)
        ).stdout, "bytes must be byte-identical to the committed blob"
        canonical = Path(wt_plan).resolve() / PLAN_REL
        assert Path(os.path.normpath(os.path.abspath(path))) == canonical, (
            "lexical absolute path must equal the canonical path"
        )
        assert path.resolve() == canonical.resolve()
        return path
    raise AssertionError(shape)


@pytest.mark.parametrize(
    "shape",
    [
        "target-worktree-copy",
        "outside-repo",
        "outside-alias-to-canonical",
        "integration-untracked",
        "canonical-symlink",
        "committed-then-dirty",
        "parent-dir-symlink",
    ],
)
def test_e9_exemption_source_must_be_base_committed(
    tmp_path, monkeypatch, capsys, shape
):
    repo, plan_path, wt_plan, _ = _make_repo(tmp_path / "primary")
    source = _untrusted_source(shape, tmp_path, repo, wt_plan)
    monkeypatch.chdir(repo)
    before = _head(repo, "main")

    assert _merge_rc(source) == plan_cmd.RC_FAIL
    error = capsys.readouterr().err
    assert "lint exemption source is untrusted" in error
    assert _head(repo, "main") == before


def test_e13_first_introduction_bootstrap(tmp_path, monkeypatch, capsys):
    repo, plan_path, _, integration_tip = _make_repo(tmp_path / "primary")
    # A branch can be checked out in only one worktree: park the physical
    # primary on a holder branch so the target branch is free for wt-target.
    _git(repo, "checkout", "-q", "-b", "holder")
    wt_target = tmp_path / "wt-target"
    _git(repo, "worktree", "add", "-q", str(wt_target), "main")

    # M-2g fixture self-check: the PLAN file must be wholly absent from the
    # target history, index and filesystem before the merge.  Pre-committing
    # or staging it on the target would make this test a fake green.
    assert _git(repo, "cat-file", "-e", "main:{}".format(PLAN_REL), check=False).returncode != 0
    assert _git(repo, "rev-list", "--format=%H", "main", "--", PLAN_REL).stdout.strip() == ""
    assert PLAN_REL not in _git(wt_target, "ls-files").stdout.split()
    assert not (wt_target / PLAN_REL).exists()

    monkeypatch.chdir(wt_target)
    assert _merge_rc(plan_path) == plan_cmd.RC_OK
    output = capsys.readouterr().out
    assert "PLAN_MERGE_OK" in output

    # Exactly one --no-ff merge on main, second parent = integration tip.
    assert _merge_count(repo) == 1
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
    assert len(parents) == 3
    assert integration_tip in parents
    # The merge introduced the plan file into the target worktree.
    assert (wt_target / PLAN_REL).is_file()


def test_e14_physical_primary_may_be_dirty_and_off_target(
    tmp_path, monkeypatch, capsys
):
    repo, plan_path, _, integration_tip = _make_repo(tmp_path / "primary")

    # Physical primary: off-target branch + unrelated dirty bytes.
    _git(repo, "checkout", "-q", "-b", "user-work")
    (repo / "seed.txt").write_bytes(b"seed modified by user\n")
    (repo / "scratch.bin").write_bytes(b"\x00\xffuser-data\xff\x00")
    before = {
        "head": _head(repo),
        "branch": _git(repo, "branch", "--show-current").stdout.strip(),
        "status": _git(repo, "status", "--porcelain").stdout,
        "index": _git(repo, "ls-files", "--stage").stdout,
        "seed": (repo / "seed.txt").read_bytes(),
        "scratch": (repo / "scratch.bin").read_bytes(),
    }

    wt_target = tmp_path / "wt-target"
    _git(repo, "worktree", "add", "-q", str(wt_target), "main")
    monkeypatch.chdir(wt_target)

    assert _merge_rc(plan_path) == plan_cmd.RC_OK
    assert "PLAN_MERGE_OK" in capsys.readouterr().out
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
    assert len(parents) == 3
    assert integration_tip in parents

    # The physical-primary checkout/index/dirty bytes are byte-for-byte
    # untouched (M-2f: mutation must not happen in main_repo()'s checkout).
    assert _head(repo) == before["head"]
    assert _git(repo, "branch", "--show-current").stdout.strip() == before["branch"]
    assert _git(repo, "status", "--porcelain").stdout == before["status"]
    assert _git(repo, "ls-files", "--stage").stdout == before["index"]
    assert (repo / "seed.txt").read_bytes() == before["seed"]
    assert (repo / "scratch.bin").read_bytes() == before["scratch"]


def test_e15_loaded_bytes_are_bound(tmp_path, monkeypatch, capsys):
    repo, plan_path, _, _ = _make_repo(tmp_path / "primary")
    monkeypatch.chdir(repo)
    committed = _git_bytes(repo, "show", "plan/it-1:{}".format(PLAN_REL)).stdout

    # Forge different bytes that still carry a legal four-field exemption.
    forged = _plan(exemption={**EXEMPTION, "justification": "forged in-memory variant"})
    plan_path.write_text(json.dumps(forged, indent=2) + "\n", encoding="utf-8")
    assert plan_path.read_bytes() != committed

    # Double-read attack (INV-3c): after the loader parsed the forged bytes,
    # restore the committed bytes to the path before the source check.  A
    # helper that re-reads the path would compare the swapped committed bytes
    # and pass; the binding must compare the bytes actually loaded.
    real_lint = plan_cmd._lint_report

    def swapping_lint(data, repo_):
        plan_path.write_bytes(committed)
        return real_lint(data, repo_)

    monkeypatch.setattr(plan_cmd, "_lint_report", swapping_lint)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "lint exemption source is untrusted" in capsys.readouterr().err
    assert _head(repo, "main") == before

    # Positive control with the same instrumentation: once the working file
    # holds the committed bytes again, the identical fixture must merge.
    plan_path.write_bytes(committed)
    assert _merge_rc(plan_path) == plan_cmd.RC_OK
    assert "PLAN_MERGE_OK" in capsys.readouterr().out


def test_e4_exemption_does_not_waive_convergence(tmp_path, monkeypatch, capsys):
    repo, plan_path, _, _ = _make_repo(tmp_path, wp_merged=False)
    monkeypatch.chdir(repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "state=APPROVED_FOR_MERGE (not MERGED)" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e5_exemption_does_not_waive_state(tmp_path, monkeypatch, capsys):
    repo, plan_path, _, _ = _make_repo(tmp_path, state="ACTIVE")
    monkeypatch.chdir(repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "state must be READY_TO_MERGE" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e6_exemption_is_logged(tmp_path, monkeypatch, capsys):
    repo, plan_path, _, _ = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

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
        repo, plan_path, _, integration_tip = _make_repo(
            tmp_path / name, dirty=False, exemption=exemption
        )
        monkeypatch.chdir(repo)
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
    repo, plan_path, _, _ = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
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
    repo, plan_path, wt_plan, _ = _make_repo(tmp_path)
    monkeypatch.chdir(wt_plan)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "must run on target branch main" in capsys.readouterr().err
    assert _head(repo, "main") == before


def test_e12_exemption_does_not_waive_already_merged(
    tmp_path, monkeypatch, capsys
):
    repo, plan_path, _, _ = _make_repo(tmp_path)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "plan/it-1")
    monkeypatch.chdir(repo)
    before_tip = _head(repo, "main")
    before_merges = _merge_count(repo)

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "already merged" in capsys.readouterr().err
    assert _head(repo, "main") == before_tip
    assert _merge_count(repo) == before_merges


def test_schema_accepts_optional_exemption_but_does_not_require_it():
    assert plan_cmd.validate(_plan(exemption=EXEMPTION)) == []
    assert plan_cmd.validate(_plan(exemption=None)) == []
