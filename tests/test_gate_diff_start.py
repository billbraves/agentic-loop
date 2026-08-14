"""WP-05: the merge gate's diff-start fallback prefers the engine-computed fork
point (``git merge-base <base_branch> <tip>``) over the human-recorded
``base_commit`` when the brief-introducing heuristic does not pin a start.

These tests prove the layered fallback and its observability:

1. stale ``base_commit`` (earlier than the real fork point) -> diff_start lands on
   ``merge-base``, not ``base_commit``, and the reviewed diff excludes the
   unrelated commit between the stale base and the fork;
2. not-stale ``base_commit`` -> ``merge-base == base_commit``, so the diff range
   is unchanged from the previous behavior;
3. brief-introducing hit -> still uses the brief-introducing commit (unchanged);
4. ``merge-base`` unresolvable -> falls through to ``base_commit`` with an
   observable log line naming the layer and reason.

The gate is exercised end-to-end against an isolated git repo (no real codex;
``codex`` is a shell stub), mirroring the carrier suite in
``packages/data-app/tests/test_codex_merge_gate.py``. A direct unit test pins
the ``git_merge_base`` helper itself.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.gate import MERGE_BASE_AMBIGUOUS  # noqa: E402
from agentic_loop.gate import git_merge_base  # noqa: E402

ITERATION = "it-1"
BRIEF_REL = f"docs/plans/{ITERATION}/WP-01-brief.md"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    _git(repo, "config", "user.email", "t@e.com")
    _git(repo, "config", "user.name", "T")
    (repo / "docs" / "plans" / ITERATION).mkdir(parents=True)
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    _git(repo, "branch", "-M", "main")
    return repo


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _checkout_new(repo: Path, branch: str) -> None:
    _git(repo, "checkout", "-q", "-b", branch)


def _make_criss_cross(repo: Path) -> tuple[str, str, str]:
    """Build the canonical criss-cross topology that yields two best common
    ancestors, returning ``(seed, left_tip, right_tip)``.

        seed(A)
         /   \\
        L     R
        |\\   /|
        | X X |
        |/   \\|
       left  right (each merged the other, so neither L nor R is unique)

    ``git merge-base --all left right`` must report both L and R.
    """
    seed = _git(repo, "rev-parse", "HEAD")
    _checkout_new(repo, "left")
    _write(repo, "left.txt", "left\n")
    _commit(repo, "left work")
    left_commit = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "main")
    _checkout_new(repo, "right")
    _write(repo, "right.txt", "right\n")
    _commit(repo, "right work")
    right_commit = _git(repo, "rev-parse", "HEAD")

    # Two independent criss-cross merges: each merges the *original* other tip
    # by hash (not by branch ref), so neither merge commit becomes an ancestor of
    # the other. That yields two best common ancestors: left_commit and
    # right_commit.
    _git(repo, "merge", "--no-ff", "-m", "merge left into right", left_commit)
    _git(repo, "checkout", "-q", "left")
    _git(repo, "merge", "--no-ff", "-m", "merge right into left", right_commit)
    left_tip = _git(repo, "rev-parse", "HEAD")
    right_tip = _git(repo, "rev-parse", "refs/heads/right")
    return seed, left_tip, right_tip


def make_codex_stub(
    tmp_path: Path, capture: Path | None = None, decision: str = "ACCEPT"
) -> Path:
    """A fake ``codex`` that honors ``-o <file>`` and writes a schema-valid
    verdict; when ``capture`` is given, it also dumps the prompt it receives on
    stdin so tests can assert on the actual diff contents sent to codex."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "codex"
    lines = [
        "#!/usr/bin/env bash",
        'out=""',
        'while [[ $# -gt 0 ]]; do',
        '  case "$1" in -o) out="$2"; shift 2;; *) shift;; esac',
        "done",
    ]
    if capture is not None:
        lines.append(f"cat > {capture}")
    lines.append(
        f"v='{{\"decision\":\"{decision}\",\"rationale\":\"stub\",\"findings\":[]}}'"
    )
    lines.append('[[ -n "$out" ]] && printf \'%s\' "$v" > "$out"')
    lines.append('printf \'%s\' "$v"')
    stub.write_text("\n".join(lines) + "\n")
    stub.chmod(0o755)
    return bindir


def run_gate(repo: Path, status_rel: str, bindir: Path | None = None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    if bindir:
        env["PATH"] = f"{bindir}:{env['PATH']}"
    return subprocess.run(
        [sys.executable, "-m", "agentic_loop.gate", status_rel],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )


def _write_status(repo: Path, rel: str, **over) -> None:
    data = {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": "WP-01",
        "iteration_id": ITERATION,
        "phase": "P0",
        "state": "READY_FOR_REVIEW",
        "role": "Developer",
        "executor": {"tool": "kimi-cli"},
        "orchestrator": {"tool": "claude-code"},
        "reviewer": {"tool": "claude-code"},
        "git": {"base_branch": "main", "base_commit": None, "branch": None,
                "worktree": ".", "commit": None},
        "scope": {"allowed_paths": ["x"], "forbidden_paths": []},
        "risk": {"production_writes_authorized": False, "network_authorized": False,
                 "real_notifications_authorized": False,
                 "irreversible_actions_authorized": False},
        "evidence": {"tests": [{"cmd": "pytest", "exit_code": 0}]},
        "review": {
            "decision": "ACCEPT",
            "attestation": {
                "reviewer_role": "orchestrator",
                "reviewer_tool": "claude-code",
                "fresh_session": True,
                "adversarial_prompt": True,
                "attested_by": "orchestrator",
                "attested_at": "2026-08-14T00:00:00Z",
            },
        },
        "consult": {"decision": None},
        "timestamps": {},
    }
    data.update(over)
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Unit tests for the git_merge_base helper itself.
# ---------------------------------------------------------------------------
def test_git_merge_base_helper_returns_fork_point(tmp_repo):
    repo = tmp_repo
    base = _git(repo, "rev-parse", "HEAD")
    _checkout_new(repo, "feat/x")
    _write(repo, "wp.txt", "wp\n")
    _commit(repo, "wp work")
    tip = _git(repo, "rev-parse", "HEAD")
    # feature was cut from main at ``base``, so that is the fork point.
    assert git_merge_base(repo, "main", tip) == base


def test_git_merge_base_helper_empty_on_unresolvable(tmp_repo):
    repo = tmp_repo
    tip = _git(repo, "rev-parse", "HEAD")
    assert git_merge_base(repo, "no-such-branch", tip) == ""


def test_git_merge_base_helper_ambiguous_sentinel(tmp_repo):
    repo = tmp_repo
    _seed, left_tip, _right_tip = _make_criss_cross(repo)
    # The criss-cross topology must genuinely produce multiple best common
    # ancestors; otherwise this test would not be exercising ambiguity.
    bases = _git(repo, "merge-base", "--all", "right", left_tip).splitlines()
    assert len(bases) == 2
    assert git_merge_base(repo, "right", left_tip) == MERGE_BASE_AMBIGUOUS


# ---------------------------------------------------------------------------
# End-to-end layered fallback.
# ---------------------------------------------------------------------------
def test_stale_base_commit_uses_merge_base_not_base_commit(tmp_repo, tmp_path):
    repo = tmp_repo
    # brief is added before the recorded (stale) base, so the brief-introducing
    # heuristic misses; two unrelated main commits land before/at the real fork.
    _write(repo, BRIEF_REL, "# brief v0\n")
    _commit(repo, "brief: add WP-01 brief")
    _write(repo, "pre_fork_unrelated.txt", "unrelated pre-fork commit\n")
    _commit(repo, "main: unrelated pre-fork commit")
    stale_base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "fork_adjacent.txt", "unrelated fork-adjacent commit\n")
    _commit(repo, "main: unrelated fork-adjacent commit")
    fork_commit = _git(repo, "rev-parse", "HEAD")

    _checkout_new(repo, "feat/x")
    _write(repo, "wp_change.txt", "wp code change\n")
    _commit(repo, "impl: wp code change")
    tip = _git(repo, "rev-parse", "HEAD")

    assert git_merge_base(repo, "main", tip) == fork_commit
    assert fork_commit != stale_base  # base_commit is genuinely stale

    _write_status(
        repo,
        "docs/plans/it-1/WP-01.status.json",
        git={"base_branch": "main", "base_commit": stale_base,
             "branch": "feat/x", "worktree": ".", "commit": tip},
        scope={"allowed_paths": ["wp_change.txt", "pre_fork_unrelated.txt",
                                  "fork_adjacent.txt", "docs/plans/it-1/",
                                  "seed.txt"],
               "forbidden_paths": []},
    )
    capture = tmp_path / "captured_prompt.txt"
    bindir = make_codex_stub(tmp_path, capture=capture, decision="ACCEPT")
    res = run_gate(repo, "docs/plans/it-1/WP-01.status.json", bindir=bindir)

    assert res.returncode == 0, res.stderr
    assert f"diff start = merge-base {fork_commit}" in res.stderr
    assert f"diff start = base_commit {stale_base}" not in res.stderr
    sent = capture.read_text()
    diff_section = sent.split("## Diff under review")[1]
    assert "wp code change" in diff_section
    # The unrelated fork-adjacent commit would be present if diff_start were the
    # stale base (base..tip); it is absent because diff_start is the real fork.
    assert "unrelated fork-adjacent commit" not in diff_section
    assert "unrelated pre-fork commit" not in diff_section
    assert "brief v0" not in diff_section


def test_not_stale_merge_base_equals_base_commit(tmp_repo, tmp_path):
    repo = tmp_repo
    # brief added before base -> heuristic misses; base IS the real fork point,
    # so merge-base == base_commit and the diff range is unchanged.
    _write(repo, BRIEF_REL, "# brief v0\n")
    _commit(repo, "brief: add WP-01 brief")
    base = _git(repo, "rev-parse", "HEAD")

    _checkout_new(repo, "feat/x")
    _write(repo, "wp_change.txt", "wp code change\n")
    _commit(repo, "impl: wp code change")
    tip = _git(repo, "rev-parse", "HEAD")

    assert git_merge_base(repo, "main", tip) == base

    _write_status(
        repo,
        "docs/plans/it-1/WP-01.status.json",
        git={"base_branch": "main", "base_commit": base,
             "branch": "feat/x", "worktree": ".", "commit": tip},
        scope={"allowed_paths": ["wp_change.txt", "docs/plans/it-1/", "seed.txt"],
               "forbidden_paths": []},
    )
    capture = tmp_path / "captured_prompt.txt"
    bindir = make_codex_stub(tmp_path, capture=capture, decision="ACCEPT")
    res = run_gate(repo, "docs/plans/it-1/WP-01.status.json", bindir=bindir)

    assert res.returncode == 0, res.stderr
    assert f"diff start = merge-base {base}" in res.stderr
    sent = capture.read_text()
    diff_section = sent.split("## Diff under review")[1]
    assert "wp code change" in diff_section
    assert "brief v0" not in diff_section


def test_brief_introducing_hit_keeps_brief_path(tmp_repo, tmp_path):
    repo = tmp_repo
    base = _git(repo, "rev-parse", "HEAD")
    _checkout_new(repo, "feat/x")
    _write(repo, BRIEF_REL, "# brief v1\n")
    _commit(repo, "setup: add WP-01 brief")
    brief_commit = _git(repo, "rev-parse", "HEAD")
    _write(repo, "wp_change.txt", "wp code change\n")
    _commit(repo, "impl: wp code change")
    tip = _git(repo, "rev-parse", "HEAD")

    _write_status(
        repo,
        "docs/plans/it-1/WP-01.status.json",
        git={"base_branch": "main", "base_commit": base,
             "branch": "feat/x", "worktree": ".", "commit": tip},
        scope={"allowed_paths": ["wp_change.txt", "docs/plans/it-1/", "seed.txt"],
               "forbidden_paths": []},
    )
    bindir = make_codex_stub(tmp_path, decision="ACCEPT")
    res = run_gate(repo, "docs/plans/it-1/WP-01.status.json", bindir=bindir)

    assert res.returncode == 0, res.stderr
    assert f"diff start moved to brief-introducing commit {brief_commit}" in res.stderr
    assert "diff start = merge-base" not in res.stderr
    assert "diff start = base_commit" not in res.stderr


def test_merge_base_failure_falls_back_to_base_commit(tmp_repo, tmp_path):
    repo = tmp_repo
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "wp_change.txt", "wp code change\n")
    _commit(repo, "impl: wp code change")
    tip = _git(repo, "rev-parse", "HEAD")

    # brief never exists -> heuristic misses; base_branch unresolvable -> the
    # merge-base layer fails, so the gate falls through to base_commit.
    _write_status(
        repo,
        "docs/plans/it-1/WP-01.status.json",
        git={"base_branch": "no-such-branch", "base_commit": base,
             "branch": "main", "worktree": ".", "commit": tip},
        scope={"allowed_paths": ["wp_change.txt", "seed.txt"],
               "forbidden_paths": []},
    )
    bindir = make_codex_stub(tmp_path, decision="ACCEPT")
    res = run_gate(repo, "docs/plans/it-1/WP-01.status.json", bindir=bindir)

    assert res.returncode == 0, res.stderr
    assert f"diff start = base_commit {base}" in res.stderr
    assert "merge-base unavailable for base_branch 'no-such-branch'" in res.stderr


def test_ambiguous_merge_base_fails_closed(tmp_repo):
    repo = tmp_repo
    seed, left_tip, _right_tip = _make_criss_cross(repo)

    # Pin the ambiguity up front, so the fail-closed assertion below is provably
    # about ambiguity and not some unrelated failure.
    bases = _git(repo, "merge-base", "--all", "right", left_tip).splitlines()
    assert len(bases) == 2

    # brief never exists -> heuristic misses; merge-base(base_branch=right, tip)
    # is ambiguous -> the gate must stop, not silently pick a fork point.
    _write_status(
        repo,
        "docs/plans/it-1/WP-01.status.json",
        git={"base_branch": "right", "base_commit": seed,
             "branch": "left", "worktree": ".", "commit": left_tip},
        scope={"allowed_paths": ["left.txt", "right.txt", "seed.txt"],
               "forbidden_paths": []},
    )
    res = run_gate(repo, "docs/plans/it-1/WP-01.status.json")

    assert res.returncode == 2, res.stderr
    assert "merge-base ambiguous" in res.stderr
    assert "refusing to guess" in res.stderr
    assert "2 common ancestors" in res.stderr
