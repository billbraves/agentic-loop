"""WP-02 / A36: ``finalize_merge.sh`` must stamp sequential work packages.

AGENTS.md §4.3 permits a sequential WP to work directly on the plan's
integration branch. In that layout ``git.branch == git.base_branch`` and
``wp_tip == base_tip``, so the "merge commit whose second parent is wp_tip"
that :380 looks for cannot exist by construction -> 0 candidates -> exit 2,
while ``plan merge`` refuses to converge until every WP is ``MERGED``. Deadlock.

The fix routes on BRANCH IDENTITY (the two status fields comparing equal), not
on "the candidate list came back empty". The distinction is the whole point:
an empty candidate list is also what a genuine parallel-lane failure looks
like (never merged, or a rebase rewrote the merge commit away), so keying the
split on emptiness would forge a ``merged_commit`` for an unintegrated WP.

Case map (brief §具名用例 -> invariant):

* ``S1``  sequential happy path                    -> INV-1
* ``S1b`` static data-flow assertion on the tip    -> INV-1b
* ``S2``  parallel happy path (positive control)   -> INV-2
* ``S3``  parallel unmerged must fail              -> INV-3  (decisive)
* ``S4``  parallel multi-candidate must fail       -> INV-2
* ``S5``  double sign still load-bearing           -> INV-4
* ``S6``  sequential idempotency                   -> INV-5

Every runtime case drives the real ``finalize_merge.sh`` through a subprocess
against a real temporary git repository. Fixture idiom follows
``tests/test_finalize_merge_first_call.py`` (``_run_git`` helper, derived
default branch name -- never a hardcoded ``main``).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"
FINALIZE_SH = PKG_SRC / "agentic_loop" / "wrappers" / "finalize_merge.sh"

PLAN_DIR = Path("docs/plans/wp02-sequential")
STATUS_NAME = "WP-SEQ.status.json"

# Witness strings. These are the reason-specific oracles the negative cases
# assert on; a bare "exit 2" would also be satisfied by dying at an unrelated
# earlier step.
WITNESS_NO_UNIQUE = "cannot uniquely resolve merge commit"
WITNESS_NOT_MERGED = "merge not detected"
WITNESS_CONSULT = "consult.decision must be ACCEPT"


@pytest.fixture
def session_env():
    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = "wp02-sequential-test"
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


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    """Fresh temp repo with one commit. Returns (repo, default_branch)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "init")
    return repo, _default_branch(repo)


def _status(
    *,
    base_branch: str,
    branch: str,
    commit: str,
    state: str = "APPROVED_FOR_MERGE",
    consult_decision: str = "ACCEPT",
    merged_commit: str | None = None,
) -> dict:
    """Schema-valid v2 status. ``git.merged_commit`` omitted unless requested
    (finalize writes that field itself)."""
    git: dict = {
        "base_branch": base_branch,
        "base_commit": "0" * 40,
        "branch": branch,
        "worktree": "../wp-seq",
        "commit": commit,
    }
    if merged_commit is not None:
        git["merged_commit"] = merged_commit
    return {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": "WP-SEQ",
        "iteration_id": "wp02-sequential",
        "phase": "P1",
        "state": state,
        "role": "Developer",
        "executor": {"tool": "kimi-cli", "session": "test"},
        "orchestrator": {"tool": "claude-code", "session": "test"},
        "reviewer": {"tool": "claude-code", "session": "test"},
        "git": git,
        "scope": {"allowed_paths": ["src/"], "forbidden_paths": [".env"]},
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
        "consult": {"decision": consult_decision, "reviewed_by": "codex-cli"},
        "timestamps": {"created_at": "2026-10-12T00:00:00Z"},
    }


def _write_status(repo: Path, payload: dict) -> Path:
    status_path = repo / PLAN_DIR / STATUS_NAME
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return status_path


def _finalize(repo: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(FINALIZE_SH), str(PLAN_DIR / STATUS_NAME)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def _git_block(status_path: Path) -> dict:
    return json.loads(status_path.read_text(encoding="utf-8"))["git"]


# --------------------------------------------------------------------------
# Fixtures for the two layouts
# --------------------------------------------------------------------------
def _make_sequential_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """Sequential layout: the WP works directly on the integration branch.

    No second branch exists; ``branch == base_branch`` and the WP's own tip is
    its integration point. Returns (repo, base_branch, wp_tip).
    """
    repo, base = _init_repo(tmp_path)
    (repo / "wp.txt").write_text("sequential wp work\n", encoding="utf-8")
    _run_git(repo, "add", "wp.txt")
    _run_git(repo, "commit", "-q", "-m", "WP-SEQ implementation on integration branch")
    wp_tip = _head(repo)
    # Premise of the whole case: the two tips really are the same commit, which
    # is exactly why no "second parent == wp_tip" merge commit can exist.
    assert (
        _run_git(repo, "rev-parse", f"refs/heads/{base}").stdout.strip() == wp_tip
    )
    return repo, base, wp_tip


def _make_parallel_merged_repo(tmp_path: Path) -> tuple[Path, str, str, str]:
    """Parallel lane, properly merged --no-ff.

    Returns (repo, base_branch, wp_tip, merge_commit).
    """
    repo, base = _init_repo(tmp_path)
    _run_git(repo, "checkout", "-q", "-b", "feature/x")
    (repo / "wp.txt").write_text("parallel wp work\n", encoding="utf-8")
    _run_git(repo, "add", "wp.txt")
    _run_git(repo, "commit", "-q", "-m", "parallel wp work")
    wp_tip = _head(repo)
    _run_git(repo, "checkout", "-q", base)
    _run_git(repo, "merge", "-q", "--no-ff", "feature/x", "-m", "Merge feature/x")
    return repo, base, wp_tip, _head(repo)


def _make_parallel_never_merged_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """Parallel lane that was never merged at all.

    The WP branch tip is NOT an ancestor of base, so this dies at the :371
    ancestor precondition. Returns (repo, base_branch, wp_tip).
    """
    repo, base = _init_repo(tmp_path)
    _run_git(repo, "checkout", "-q", "-b", "feature/x")
    (repo / "wp.txt").write_text("parallel wp work\n", encoding="utf-8")
    _run_git(repo, "add", "wp.txt")
    _run_git(repo, "commit", "-q", "-m", "parallel wp work")
    wp_tip = _head(repo)
    _run_git(repo, "checkout", "-q", base)
    # Base moves on independently; feature/x is never merged.
    (repo / "base.txt").write_text("base moves on\n", encoding="utf-8")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base work")
    assert subprocess.run(
        ["git", "merge-base", "--is-ancestor", wp_tip, _head(repo)], cwd=repo
    ).returncode != 0
    return repo, base, wp_tip


def _make_parallel_ancestor_without_merge_repo(
    tmp_path: Path,
) -> tuple[Path, str, str]:
    """Parallel lane whose merge commit does NOT exist, yet the tip IS an
    ancestor of base -- the fast-forward / rebased-away shape.

    This is the decisive INV-3 fixture: it clears the :371 ancestor
    precondition and reaches the candidate resolution with 0 candidates, which
    is precisely the state a "candidate_count == 0" discriminator would
    misread as "sequential" and stamp. Returns (repo, base_branch, wp_tip).
    """
    repo, base = _init_repo(tmp_path)
    _run_git(repo, "checkout", "-q", "-b", "feature/x")
    (repo / "wp.txt").write_text("parallel wp work\n", encoding="utf-8")
    _run_git(repo, "add", "wp.txt")
    _run_git(repo, "commit", "-q", "-m", "parallel wp work")
    wp_tip = _head(repo)
    _run_git(repo, "checkout", "-q", base)
    # Fast-forward: wp_tip becomes an ancestor of base with NO merge commit.
    _run_git(repo, "merge", "-q", "--ff-only", "feature/x")
    assert subprocess.run(
        ["git", "merge-base", "--is-ancestor", wp_tip, _head(repo)], cwd=repo
    ).returncode == 0
    merges = _run_git(repo, "rev-list", "--merges", "HEAD").stdout.strip()
    assert merges == "", f"fixture must contain no merge commits, got {merges!r}"
    return repo, base, wp_tip


def _make_parallel_multi_candidate_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """Two distinct merge commits in base history whose SECOND parent is the
    same ``wp_tip``.

    A second ``git merge`` of an already-merged branch is a no-op ("Already up
    to date"), so the second merge commit is built with ``git commit-tree``
    plumbing -- a real commit object in the real object database, reached
    through the real ref. Returns (repo, base_branch, wp_tip).
    """
    repo, base = _init_repo(tmp_path)
    _run_git(repo, "checkout", "-q", "-b", "feature/x")
    (repo / "wp.txt").write_text("parallel wp work\n", encoding="utf-8")
    _run_git(repo, "add", "wp.txt")
    _run_git(repo, "commit", "-q", "-m", "parallel wp work")
    wp_tip = _head(repo)

    _run_git(repo, "checkout", "-q", base)
    _run_git(repo, "merge", "-q", "--no-ff", "feature/x", "-m", "Merge feature/x (1)")
    first_merge = _head(repo)

    (repo / "base.txt").write_text("base moves on\n", encoding="utf-8")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base work")
    carrier = _head(repo)

    tree = _run_git(repo, "rev-parse", f"{carrier}^{{tree}}").stdout.strip()
    second_merge = _run_git(
        repo,
        "commit-tree",
        tree,
        "-p",
        carrier,
        "-p",
        wp_tip,
        "-m",
        "Merge feature/x (2)",
    ).stdout.strip()
    _run_git(repo, "update-ref", f"refs/heads/{base}", second_merge)
    _run_git(repo, "reset", "-q", "--hard", second_merge)

    # Premise: the resolver really does see two candidates.
    listing = _run_git(repo, "rev-list", "--merges", "--parents", second_merge).stdout
    seconds = [
        line.split()[0] for line in listing.splitlines() if line.split()[2:3] == [wp_tip]
    ]
    assert sorted(seconds) == sorted([first_merge, second_merge]), seconds
    return repo, base, wp_tip


# ==========================================================================
# S1 [sequential-happy] -> INV-1
# ==========================================================================
def test_s1_sequential_happy_stamps_wp_tip(tmp_path: Path, session_env) -> None:
    repo, base, wp_tip = _make_sequential_repo(tmp_path)
    status_path = _write_status(
        repo, _status(base_branch=base, branch=base, commit=wp_tip)
    )
    assert "merged_commit" not in _git_block(status_path)

    res = _finalize(repo, session_env)

    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert res.stdout.strip() == f"FINALIZE_OK merged_commit={wp_tip}"
    final = json.loads(status_path.read_text(encoding="utf-8"))
    assert final["state"] == "MERGED"
    assert final["git"]["merged_commit"] == wp_tip


# ==========================================================================
# S1b [sequential-tip-source-static-assert] -> INV-1b
# ==========================================================================
# Both tips resolve from the SAME branch name in the sequential layout, so
# `rev-parse refs/heads/<name>` necessarily returns the same commit and a
# wrong `merged_commit = base_tip` is runtime-indistinguishable from the
# correct `= wp_tip`. S1 alone is therefore vacuous on this point. The
# load-bearing assertion has to be static data flow over the script bytes.
#
# Deliberately NOT a full-text search for "$wp_tip": that would pass even if
# the assignment read `$base_tip` and `$wp_tip` merely appeared elsewhere or
# in a comment. This parses to the assignment statement itself.

_ASSIGN_RE = re.compile(r"^merged_commit=(?P<rhs>.*)$")


def _strip_comment(line: str) -> str:
    """Drop a trailing/whole-line shell comment outside quotes."""
    out: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote is None and char == "\\":
            out.append(line[index : index + 2])
            index += 2
            continue
        if quote is None and char in "\"'":
            quote = char
        elif quote is not None and char == quote:
            quote = None
        elif quote is None and char == "#":
            break
        out.append(char)
        index += 1
    return "".join(out)


def _sequential_branch_body(text: str) -> list[str]:
    """Return the executable lines of the ``branch == base_branch`` then-block.

    Comments are stripped first, so nothing a comment says can satisfy the
    assertion. The block is delimited by real ``if``/``fi`` nesting, so lines
    belonging to some other construct cannot leak in.
    """
    code = [_strip_comment(raw).strip() for raw in text.splitlines()]

    opener = re.compile(
        r'^if\s+\[\[\s+"\$(branch|base_branch)"\s+==\s+"\$(branch|base_branch)"\s+\]\]\s*;\s*then$'
    )
    starts = [i for i, line in enumerate(code) if opener.match(line)]
    assert len(starts) == 1, (
        "expected exactly one `if [[ \"$branch\" == \"$base_branch\" ]]; then` "
        f"discriminator in finalize_merge.sh, found {len(starts)}"
    )
    start = starts[0]

    # Walk to the matching `fi`/`else` at depth 0 of this block.
    body: list[str] = []
    depth = 0
    for line in code[start + 1 :]:
        if depth == 0 and (line == "else" or line == "fi" or line.startswith("elif ")):
            break
        if re.search(r"(^|;\s*)then$", line) or line.endswith(" do") or line.endswith(" in"):
            depth += 1
        elif line in {"fi", "done", "esac"}:
            depth -= 1
        body.append(line)
    else:  # pragma: no cover - defensive
        pytest.fail("sequential branch is not terminated by `fi`/`else`")

    # The assignment must sit at the block's own nesting level: any assignment
    # buried inside a nested conditional would not be unconditionally reached
    # when the branch is taken, and would not be load-bearing.
    top_level: list[str] = []
    depth = 0
    for line in body:
        if depth == 0:
            top_level.append(line)
        if re.search(r"(^|;\s*)then$", line) or line.endswith(" do") or line.endswith(" in"):
            depth += 1
        elif line in {"fi", "done", "esac"}:
            depth -= 1
    return top_level


def test_s1b_sequential_merged_commit_is_assigned_from_wp_tip() -> None:
    text = FINALIZE_SH.read_text(encoding="utf-8")
    body = _sequential_branch_body(text)

    assignments = [
        match.group("rhs").strip()
        for match in (_ASSIGN_RE.match(line) for line in body)
        if match
    ]
    assert assignments, (
        "no executable `merged_commit=` assignment found at the top level of "
        "the sequential branch; the static tip-source assertion cannot be "
        "evaluated (dead code and comments are excluded by construction)"
    )

    # The FINAL assignment is the one whose value survives to the write-back.
    final_rhs = assignments[-1]
    normalized = final_rhs.strip('"')
    assert normalized == "$wp_tip", (
        "sequential branch must assign merged_commit from $wp_tip; the "
        f"effective assignment is `merged_commit={final_rhs}`"
    )
    assert "$base_tip" not in final_rhs, (
        f"sequential merged_commit must not be sourced from $base_tip: {final_rhs}"
    )


def test_s1b_helper_rejects_base_tip_assignment() -> None:
    """Meta-check: the S1b parser actually discriminates the wrong source.

    Guards against the assertion silently degrading into something that
    accepts any assignment (which is how a static check goes vacuously green).
    """
    mutated = FINALIZE_SH.read_text(encoding="utf-8").replace(
        'merged_commit="$wp_tip"', 'merged_commit="$base_tip"', 1
    )
    body = _sequential_branch_body(mutated)
    assignments = [
        match.group("rhs").strip()
        for match in (_ASSIGN_RE.match(line) for line in body)
        if match
    ]
    assert assignments and assignments[-1].strip('"') == "$base_tip"

    # A comment mentioning $wp_tip must not rescue a $base_tip assignment.
    commented = FINALIZE_SH.read_text(encoding="utf-8").replace(
        'merged_commit="$wp_tip"',
        'merged_commit="$base_tip"  # should be "$wp_tip"',
        1,
    )
    body = _sequential_branch_body(commented)
    assignments = [
        match.group("rhs").strip()
        for match in (_ASSIGN_RE.match(line) for line in body)
        if match
    ]
    assert assignments and assignments[-1].strip('"') == "$base_tip"


# ==========================================================================
# S2 [parallel-happy] -> INV-2 (oracle item 1: positive reachability control)
# ==========================================================================
def test_s2_parallel_happy_stamps_the_merge_commit(tmp_path: Path, session_env) -> None:
    repo, base, wp_tip, merge_commit = _make_parallel_merged_repo(tmp_path)
    status_path = _write_status(
        repo, _status(base_branch=base, branch="feature/x", commit=wp_tip)
    )

    res = _finalize(repo, session_env)

    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert res.stdout.strip() == f"FINALIZE_OK merged_commit={merge_commit}"
    final = json.loads(status_path.read_text(encoding="utf-8"))
    assert final["state"] == "MERGED"
    # The merge commit, NOT the branch tip -- this is what separates the
    # parallel path from the sequential one.
    assert final["git"]["merged_commit"] == merge_commit
    assert final["git"]["merged_commit"] != wp_tip


# ==========================================================================
# S3 [parallel-unmerged-must-fail] -> INV-3 (decisive)
# ==========================================================================
# Two shapes of "not integrated", because the script has two fail-closed
# layers and they are reached by different fixtures:
#
#   S3a: tip is not an ancestor of base at all -> dies at the :371 ancestor
#        precondition with "merge not detected".
#   S3b: tip IS an ancestor but no merge commit exists (ff / rebased away) ->
#        clears :371, reaches candidate resolution, 0 candidates ->
#        "cannot uniquely resolve merge commit".
#
# S3b is the one that pins INV-3: it is the exact state in which a
# "candidate_count == 0" discriminator would conclude "sequential" and stamp a
# merged_commit for an unintegrated WP. See the report note on the brief's S3
# witness string.


def test_s3a_parallel_never_merged_fails_closed(tmp_path: Path, session_env) -> None:
    repo, base, wp_tip = _make_parallel_never_merged_repo(tmp_path)
    status_path = _write_status(
        repo, _status(base_branch=base, branch="feature/x", commit=wp_tip)
    )

    res = _finalize(repo, session_env)
    combined = res.stdout + res.stderr

    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert WITNESS_NOT_MERGED in combined, combined
    assert "FINALIZE_OK" not in combined
    # merged_commit must NOT have been written, and above all must not be wp_tip.
    git_block = _git_block(status_path)
    assert "merged_commit" not in git_block, git_block
    assert git_block.get("merged_commit") != wp_tip
    assert json.loads(status_path.read_text(encoding="utf-8"))["state"] == (
        "APPROVED_FOR_MERGE"
    )


def test_s3b_parallel_without_merge_commit_fails_closed(
    tmp_path: Path, session_env
) -> None:
    repo, base, wp_tip = _make_parallel_ancestor_without_merge_repo(tmp_path)
    status_path = _write_status(
        repo, _status(base_branch=base, branch="feature/x", commit=wp_tip)
    )

    res = _finalize(repo, session_env)
    combined = res.stdout + res.stderr

    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    # Reason-specific witness (oracle item 2): the run reached the candidate
    # resolution and found it empty, rather than dying somewhere earlier.
    assert WITNESS_NO_UNIQUE in combined, combined
    assert "(found 0)" in combined, combined
    assert "FINALIZE_OK" not in combined
    git_block = _git_block(status_path)
    assert "merged_commit" not in git_block, git_block
    assert git_block.get("merged_commit") != wp_tip
    assert json.loads(status_path.read_text(encoding="utf-8"))["state"] == (
        "APPROVED_FOR_MERGE"
    )


# ==========================================================================
# S4 [parallel-multi-candidate] -> INV-2 (second half)
# ==========================================================================
def test_s4_parallel_multi_candidate_fails_closed(tmp_path: Path, session_env) -> None:
    repo, base, wp_tip = _make_parallel_multi_candidate_repo(tmp_path)
    status_path = _write_status(
        repo, _status(base_branch=base, branch="feature/x", commit=wp_tip)
    )

    res = _finalize(repo, session_env)
    combined = res.stdout + res.stderr

    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert WITNESS_NO_UNIQUE in combined, combined
    assert "(found 2)" in combined, combined
    assert "FINALIZE_OK" not in combined
    assert "merged_commit" not in _git_block(status_path)


# ==========================================================================
# S5 [sequential-double-sign-still-load-bearing] -> INV-4
# ==========================================================================
# S5a is the end-to-end statement: a sequential WP with consult REWORK is
# refused. In this repository the schema validator ALSO refuses that status
# (validate_wp_status rejects consult != ACCEPT in APPROVED_FOR_MERGE for v2),
# so S5a alone cannot tell which of the two layers did the refusing -- and a
# mutation that removes the script's own gate would leave S5a green.
#
# S5b closes that gap by shadowing agentic_loop.validate_wp_status with a
# permissive `validate` via PYTHONPATH precedence (the same injection idiom as
# tests/test_finalize_merge_first_call.py uses for agentic_loop.gate). With the
# validator neutralized, the script's own double-sign gate is the only thing
# left, so its witness string proves that gate fires on the sequential path.

_SHADOW_PACKAGE_INIT = '''\
import os

__path__.append(os.path.join(os.environ["AGENTIC_REAL_SRC"], "agentic_loop"))
'''

_PERMISSIVE_VALIDATOR = '''\
"""WP-02 S5b fixture: a validator that accepts everything.

Neutralizes the schema layer so the only remaining double-sign enforcement is
finalize_merge.sh's own gate, making that gate independently observable.
"""
from pathlib import Path


def validate(data):
    return []


def load_status(path):
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    return 0
'''


def test_s5a_sequential_consult_rework_fails_closed(
    tmp_path: Path, session_env
) -> None:
    repo, base, wp_tip = _make_sequential_repo(tmp_path)
    status_path = _write_status(
        repo,
        _status(
            base_branch=base, branch=base, commit=wp_tip, consult_decision="REWORK"
        ),
    )

    res = _finalize(repo, session_env)
    combined = res.stdout + res.stderr

    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert "FINALIZE_OK" not in combined
    git_block = _git_block(status_path)
    assert "merged_commit" not in git_block, git_block
    assert json.loads(status_path.read_text(encoding="utf-8"))["state"] == (
        "APPROVED_FOR_MERGE"
    )


def test_s5b_sequential_double_sign_gate_is_itself_load_bearing(
    tmp_path: Path, session_env
) -> None:
    repo, base, wp_tip = _make_sequential_repo(tmp_path)
    status_path = _write_status(
        repo,
        _status(
            base_branch=base, branch=base, commit=wp_tip, consult_decision="REWORK"
        ),
    )

    inject = tmp_path / "inject"
    (inject / "agentic_loop").mkdir(parents=True)
    (inject / "agentic_loop" / "__init__.py").write_text(
        _SHADOW_PACKAGE_INIT, encoding="utf-8"
    )
    (inject / "agentic_loop" / "validate_wp_status.py").write_text(
        _PERMISSIVE_VALIDATOR, encoding="utf-8"
    )

    env = dict(session_env)
    env["AGENTIC_REAL_SRC"] = str(PKG_SRC)
    env["PYTHONPATH"] = str(inject) + os.pathsep + env["PYTHONPATH"]

    # Premise: the shadow is in effect and the sibling modules still import.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import agentic_loop.validate_wp_status as v, agentic_loop.gate, "
            "agentic_loop.resolve_paths; "
            "assert v.validate({'anything': True}) == []",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert probe.returncode == 0, (probe.stdout, probe.stderr)

    res = _finalize(repo, env)
    combined = res.stdout + res.stderr

    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    # Reason-specific witness from the SCRIPT's gate, not the validator.
    assert WITNESS_CONSULT in combined, combined
    assert "FINALIZE_OK" not in combined
    assert "merged_commit" not in _git_block(status_path)

    # Positive reachability control (oracle item 1): the same fixture and the
    # same neutralized validator, with consult flipped to ACCEPT, reaches the
    # finalize endpoint. Proves the refusal above was the double-sign gate and
    # not some unrelated earlier failure under the injection.
    _write_status(
        repo,
        _status(
            base_branch=base, branch=base, commit=wp_tip, consult_decision="ACCEPT"
        ),
    )
    control = _finalize(repo, env)
    assert control.returncode == 0, (
        control.returncode,
        control.stdout,
        control.stderr,
    )
    assert control.stdout.strip() == f"FINALIZE_OK merged_commit={wp_tip}"


# ==========================================================================
# S6 [sequential-idempotent] -> INV-5
# ==========================================================================
def test_s6_sequential_idempotent_then_tampered_record_fails(
    tmp_path: Path, session_env
) -> None:
    repo, base, wp_tip = _make_sequential_repo(tmp_path)
    status_path = _write_status(
        repo, _status(base_branch=base, branch=base, commit=wp_tip)
    )

    first = _finalize(repo, session_env)
    assert first.returncode == 0, (first.returncode, first.stdout, first.stderr)
    assert json.loads(status_path.read_text(encoding="utf-8"))["git"][
        "merged_commit"
    ] == wp_tip

    # Re-run on the already-MERGED status: exit 0, reported as already done.
    second = _finalize(repo, session_env)
    assert second.returncode == 0, (second.returncode, second.stdout, second.stderr)
    assert second.stdout.strip() == (
        f"FINALIZE_OK merged_commit={wp_tip} (already finalized)"
    )

    # Tamper the recorded value: the mismatch must fail closed.
    tampered = json.loads(status_path.read_text(encoding="utf-8"))
    bogus = "1" * 40
    assert bogus != wp_tip
    tampered["git"]["merged_commit"] = bogus
    status_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")

    third = _finalize(repo, session_env)
    combined = third.stdout + third.stderr
    assert third.returncode == 2, (third.returncode, third.stdout, third.stderr)
    assert "recorded merged_commit != resolved" in combined, combined
    assert "FINALIZE_OK" not in combined
    # The tampered record must be left alone, not silently repaired.
    assert _git_block(status_path)["merged_commit"] == bogus
