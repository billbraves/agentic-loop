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
    if shape == "dotdot-cancelled-symlink-hop":
        # rev8 shape (still reachable through the caller's spelling, hence
        # M-2h): a REAL subdirectory `subdir` plus a symlink `hop` pointing at
        # it, both inside the canonical directory.  The caller spells the
        # canonical file as `<canonical_dir>/hop/../<plan_id>.status.json`.
        #
        # Under a rule that normalizes BEFORE comparing (rev7's
        # `_lexical_absolute`), `hop/..` collapses lexically and the symlinked
        # component survives in NO checked path, so all four faces pass
        # (lexical equality, resolved equality, leaf-not-a-link, committed
        # bytes) and the attack reaches PLAN_MERGE_OK.  Under rev8/rev11 the
        # raw spelling is classified first, `..` is rejected outright, and the
        # same call fails closed.
        canonical_dir = wt_plan / "docs/plans/it-1"
        subdir = canonical_dir / "subdir"
        subdir.mkdir(parents=True, exist_ok=True)
        (subdir / "marker.txt").write_text("real dir\n", encoding="utf-8")
        hop = canonical_dir / "hop"
        if hop.is_symlink() or hop.exists():
            hop.unlink()
        hop.symlink_to(subdir, target_is_directory=True)
        # `<canonical_dir>/hop/../<plan_id>.status.json` — spelled with the raw
        # `hop/..` so the symlinked component is present in the caller's path.
        source = canonical_dir / "hop" / ".." / "PLAN-1.status.json"

        # Self-proof that the attack shape is really constructed, and that the
        # rejection cannot come from the macOS /var vs /private/var mismatch
        # (a false green).  `root` is pytest tmp_path, already resolved.
        canonical = Path(wt_plan).resolve() / PLAN_REL
        assert Path(wt_plan).resolve() == Path(wt_plan)
        assert hop.is_symlink(), "the `hop` component must be a symlink"
        assert not source.is_symlink(), "the leaf PLAN file must not be a link"
        assert source.read_bytes() == _git_bytes(
            wt_plan, "show", "plan/it-1:{}".format(PLAN_REL)
        ).stdout, "bytes must be byte-identical to the committed blob"
        assert Path(os.path.normpath(os.path.abspath(source))) == canonical, (
            "normpath(abspath(source)) must equal the canonical path, i.e. the "
            "four rev7 faces all pass and only the RAW spelling can reject it"
        )
        return source
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
        "dotdot-cancelled-symlink-hop",
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

    # Double-read attack (INV-3c): the forged bytes are the ones the loader
    # parses, so they are `raw`; the committed bytes are then put back at the
    # path before the source check runs.  A helper that re-reads the path (or
    # resolves then reads) compares the swapped committed bytes and merges; the
    # binding must compare the bytes the loader actually parsed.
    real_load_and_validate = plan_cmd._load_and_validate

    # A load-and-validate wrapper that deep-copies the parsed bytes and returns
    # that copy as `raw`.  The bytes are value-equal (so `==` still holds when
    # they come from the same object) but object-distinct, so an identity-bound
    # `is` check would reject a legitimate merge: the binding must be by value.
    def binding_loader(plan_arg):
        data, path, raw = real_load_and_validate(plan_arg)
        return data, path, bytes(bytearray(raw))

    # The caller supplies a path, not bytes: `_load_and_validate` must go on
    # recording exactly the bytes it parsed, and the source check must judge
    # those bytes.
    monkeypatch.setattr(plan_cmd, "_load_and_validate", binding_loader)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    assert "lint exemption source is untrusted" in capsys.readouterr().err
    assert _head(repo, "main") == before

    # Positive control with the same instrumentation: once the working file
    # holds the committed bytes again, the identical fixture must merge.
    plan_path.write_bytes(committed)
    monkeypatch.setattr(plan_cmd, "_load_and_validate", plan_cmd._load_and_validate)
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


def test_e16_canonical_spellings_are_accepted(tmp_path, monkeypatch, capsys):
    """INV-3b R3-c compatibility control: BOTH canonical spellings must merge.

    This is the gate against a "fix" that silently rejects the documented
    relative CLI form.  Two branches:

    (a) canonical ABSOLUTE path;
    (b) canonical RELATIVE path, invoked while the CWD is the TARGET worktree
        (not the integration worktree), which proves the relative form maps
        onto the discovered integration worktree root and not onto the CWD.
    """
    # ---- (a) canonical absolute spelling ---------------------------------
    repo, plan_path, wt_plan, integration_tip = _make_repo(tmp_path / "absolute")
    absolute = str(wt_plan / PLAN_REL)
    assert os.path.isabs(absolute)
    monkeypatch.chdir(repo)

    assert _merge_rc(absolute) == plan_cmd.RC_OK
    assert "PLAN_MERGE_OK" in capsys.readouterr().out
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
    assert len(parents) == 3
    assert integration_tip in parents

    # ---- (b) canonical relative spelling, CWD = target worktree -----------
    repo, plan_path, wt_plan, integration_tip = _make_repo(tmp_path / "relative")
    # A branch can be checked out in one worktree only: park the physical
    # primary so `main` is free for wt-target.
    _git(repo, "checkout", "-q", "-b", "holder")
    wt_target = tmp_path / "relative/wt-target"
    _git(repo, "worktree", "add", "-q", str(wt_target), "main")
    monkeypatch.chdir(wt_target)

    # The documented contract spelling is relative and carries no CWD anchor.
    relative = PLAN_REL
    assert not os.path.isabs(relative)
    # The integration worktree exists but the physical-primary path does NOT
    # hold the file: only candidate discovery can find it.
    assert (wt_plan / PLAN_REL).is_file()
    assert not (repo / PLAN_REL).exists()

    assert _merge_rc(relative) == plan_cmd.RC_OK
    output = capsys.readouterr().out
    assert "PLAN_MERGE_OK" in output
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
    assert len(parents) == 3
    assert integration_tip in parents


BAD_ITERATION_IDS = ["../../etc", "it-1/..", ".", "..", "a/b"]


@pytest.mark.parametrize("iteration_id", BAD_ITERATION_IDS)
def test_e17_bad_iteration_id_fails_field_validation(
    tmp_path, monkeypatch, capsys, iteration_id
):
    """INV-3e: a path field that is not a single safe component must be rejected
    BY FIELD VALIDATION, not by an accidental file-not-found later."""
    repo, plan_path, _, _ = _make_repo(tmp_path / "primary")
    data = _plan(exemption=EXEMPTION)
    data["iteration_id"] = iteration_id
    _write_json(plan_path, data)
    monkeypatch.chdir(repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    error = capsys.readouterr().err
    # Reason-specific witness: the FIELD check, not "file does not exist".
    assert "PLAN_INVALID" in error
    assert "iteration_id must be a single relative path component" in error
    assert _head(repo, "main") == before


def test_e17_bad_plan_id_fails_field_validation(tmp_path, monkeypatch, capsys):
    """INV-3e, the `plan_id` half: `../PLAN-1` must be rejected as a field."""
    repo, plan_path, _, _ = _make_repo(tmp_path / "primary")
    data = _plan(exemption=EXEMPTION)
    data["plan_id"] = "../PLAN-1"
    _write_json(plan_path, data)
    monkeypatch.chdir(repo)
    before = _head(repo, "main")

    assert _merge_rc(plan_path) == plan_cmd.RC_FAIL
    error = capsys.readouterr().err
    assert "PLAN_INVALID" in error
    assert "plan_id must be a single relative path component" in error
    assert _head(repo, "main") == before


def _add_lane_worktree(repo: Path, root: Path, name: str, branch: str, start: str) -> Path:
    """Registered parallel-lane worktree STARTED from `start`, so it INHERITS
    every file at its own copy of the same relative paths."""
    lane = root / name
    _git(repo, "worktree", "add", "-q", "-b", branch, str(lane), start)
    return lane


def test_e18_relative_form_candidate_discovery(tmp_path, monkeypatch, capsys):
    """INV-3b R3-a relative form: all five branches (a / b / c1 / c2 / d).

    The uniqueness criterion must act on candidates that PASS the full stage-2
    trust check -- not on candidates that merely exist (rev11).  A lane worktree
    cut from the integration branch inherits the same file and must NOT cause a
    legitimate relative invocation to be rejected (c1), while two genuinely
    self-consistent candidates must fail closed (c2).
    """
    relative = PLAN_REL
    assert not os.path.isabs(relative)

    # ---- (a) unique candidate -> success, selects the integration worktree --
    repo, plan_path, wt_plan, integration_tip = _make_repo(tmp_path / "a")
    _git(repo, "checkout", "-q", "-b", "holder")
    wt_target = tmp_path / "a/wt-target"
    _git(repo, "worktree", "add", "-q", str(wt_target), "main")
    # Explicitly assert `_resolve_plan_path()` did NOT locate the file: it
    # anchors relative paths at main_repo(), where the plan file does not exist.
    # (main_repo() is the real repo root, not the primary checkout used here.)
    anchored = plan_cmd._resolve_plan_path(relative)
    assert not anchored.is_absolute() or anchored.name == Path(relative).name
    assert not anchored.exists(), "_resolve_plan_path must not locate the file"
    assert anchored != (wt_plan / relative)
    monkeypatch.chdir(wt_target)

    assert _merge_rc(relative) == plan_cmd.RC_OK
    assert "PLAN_MERGE_OK" in capsys.readouterr().out
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
    assert len(parents) == 3
    assert integration_tip in parents
    # The candidate discovery selected the INTEGRATION worktree, not the CWD
    # (wt_target) and not the physical primary (repo).
    assert Path(wt_plan).resolve() != Path(wt_target).resolve()
    assert Path(wt_plan).resolve() != Path(repo).resolve()

    # ---- (b) zero trusted candidate -> `no trusted candidate` -------------- 
    repo, plan_path, wt_plan, _ = _make_repo(tmp_path / "b")
    _git(repo, "checkout", "-q", "-b", "holder")
    wt_target = tmp_path / "b/wt-target"
    _git(repo, "worktree", "add", "-q", str(wt_target), "main")
    # Remove the file from the ONLY worktree that carried it: nothing is left
    # for candidate discovery to find.  `_resolve_plan_path()` would report the
    # same "missing" for an unrelated reason, so the witness must be the
    # candidate-discovery one.
    (wt_plan / PLAN_REL).unlink()
    assert not (repo / PLAN_REL).exists()
    assert not (wt_target / PLAN_REL).exists()
    monkeypatch.chdir(wt_target)
    before = _head(repo, "main")

    assert _merge_rc(relative) == plan_cmd.RC_FAIL
    error = capsys.readouterr().err
    assert "no trusted candidate" in error
    assert "does not exist" not in error
    assert _head(repo, "main") == before

    # ---- (c1) inherited same-named file must NOT cause a false rejection ---
    repo, plan_path, wt_plan, integration_tip = _make_repo(tmp_path / "c1")
    _git(repo, "checkout", "-q", "-b", "holder")
    wt_target = tmp_path / "c1/wt-target"
    _git(repo, "worktree", "add", "-q", str(wt_target), "main")
    lane = _add_lane_worktree(repo, tmp_path / "c1", "wt-lane", "lane/pl-1", "plan/it-1")
    # The lane branched off the integration branch, so it carries the very same
    # file at the very same relative path -- the real-world shape the
    # orchestrator measured (11 of 17 registered worktrees).
    assert (lane / PLAN_REL).read_bytes() == (wt_plan / PLAN_REL).read_bytes()
    assert (lane / PLAN_REL).is_file()
    monkeypatch.chdir(wt_target)

    assert _merge_rc(relative) == plan_cmd.RC_OK
    assert "PLAN_MERGE_OK" in capsys.readouterr().out
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
    assert len(parents) == 3
    assert integration_tip in parents

    # ---- (c2) two self-consistent candidates -> not unique -----------------
    repo, plan_path, wt_plan, _ = _make_repo(tmp_path / "c2")
    _git(repo, "checkout", "-q", "-b", "holder")
    wt_target = tmp_path / "c2/wt-target"
    _git(repo, "worktree", "add", "-q", str(wt_target), "main")
    # A second worktree, on its own branch, carrying its OWN commit of the same
    # path: its bytes and its branch are each self-consistent, so stage 2
    # trusts it too.  Two trusted candidates -> fail closed, never pick one.
    # The duel branch also carries the WP status file so that convergence
    # cannot mask the uniqueness witness under test.
    duel = tmp_path / "c2/wt-duel"
    _git(repo, "worktree", "add", "-q", "-b", "plan/it-2", str(duel), "main")
    duel_wp = duel / "docs/plans/it-1/WP-1.status.json"
    _write_json(
        duel_wp,
        {"state": "MERGED", "git": {"merged_commit": "deadbeef"}, "plan_id": "PLAN-1"},
    )
    duel_plan = _plan(exemption=EXEMPTION)
    duel_plan["git"] = dict(duel_plan["git"], base_branch="plan/it-2")
    _write_json(duel / PLAN_REL, duel_plan)
    _git(duel, "add", "docs/plans/it-1/WP-1.status.json", PLAN_REL)
    _git(duel, "commit", "-q", "-m", "duel plan status")
    assert _git(duel, "show", "plan/it-2:{}".format(PLAN_REL), check=False).returncode == 0
    assert _git(duel, "show", "plan/it-2:docs/plans/it-1/WP-1.status.json", check=False).returncode == 0
    assert _git(duel, "branch", "--show-current").stdout.strip() == "plan/it-2"
    monkeypatch.chdir(wt_target)
    before = _head(repo, "main")

    assert _merge_rc(relative) == plan_cmd.RC_FAIL
    error = capsys.readouterr().err
    assert "trusted candidate not unique" in error
    assert _head(repo, "main") == before

    # ---- (d) forged fields -> rejected ------------------------------------
    repo, plan_path, wt_plan, _ = _make_repo(tmp_path / "d")
    _git(repo, "checkout", "-q", "-b", "holder")
    wt_target = tmp_path / "d/wt-target"
    _git(repo, "worktree", "add", "-q", str(wt_target), "main")
    # The file sits at the legitimate canonical relative path and holds legal
    # exemption bytes, but its own id fields name somebody else.  Stage 2's
    # self-consistency re-check must catch that the spelling's path components
    # and the file's fields disagree -- a forged file cannot transfer trust.
    # The forged iteration dir also carries a converged WP status file, so the
    # convergence gate cannot mask the source-check witness under test.
    forged = _plan(exemption=EXEMPTION)
    forged["iteration_id"] = "it-9"
    forged["plan_id"] = "PLAN-9"
    _write_json(wt_plan / PLAN_REL, forged)
    _write_json(
        wt_plan / "docs/plans/it-9/WP-1.status.json",
        {"state": "MERGED", "git": {"merged_commit": "deadbeef"}, "plan_id": "PLAN-9"},
    )
    _git(wt_plan, "add", PLAN_REL, "docs/plans/it-9/WP-1.status.json")
    _git(wt_plan, "commit", "-q", "-m", "forged plan status")
    monkeypatch.chdir(wt_target)
    before = _head(repo, "main")

    assert _merge_rc(relative) == plan_cmd.RC_FAIL
    error = capsys.readouterr().err
    assert "lint exemption source is untrusted" in error
    assert _head(repo, "main") == before


def test_schema_accepts_optional_exemption_but_does_not_require_it():
    assert plan_cmd.validate(_plan(exemption=EXEMPTION)) == []
    assert plan_cmd.validate(_plan(exemption=None)) == []
