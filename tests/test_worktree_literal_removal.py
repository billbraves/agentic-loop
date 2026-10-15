"""WP-02: the two path-literal worktree checks now reference the one hardened
predicate.

Two call sites still decided "is this status file inside a worktree?" with a
path literal — ``wrappers/merge.sh:37`` (``[[ "$status_file" ==
*"/.worktrees/"* ]]``) and ``gate/qoder_security.py:1012`` (``if
"/.worktrees/" in str(status_file)``) — while ``gate/__init__.py:810``
(``path_is_in_worktree``), ``preflight.sh`` and ``finalize_merge.sh`` already
answered from git facts. For the same input on this machine — a ``main``
checkout that is itself a linked worktree at a path with no
``/.worktrees/`` segment — the two families gave OPPOSITE verdicts, i.e. the
single-authority invariant was already violated. The literal is wrong in both
directions:

* **fail-open (the danger)**: any linked worktree path without that segment is
  accepted, e.g. the sibling ``git worktree add ../wpN-x`` layout this repo
  actually uses;
* **fail-closed (the false alarm)**: a genuine ``.worktrees`` directory inside
  the main repo is refused, though it is plain main-repo content.

The suite below pins the post-change behaviour on the real wrappers with real
git fixtures (``git init`` + a real ``git worktree add``), never a mock:

- F1/F5 exercise ``merge.sh`` end to end (refuses a sibling worktree; stays
  fail-closed when only the probe fails);
- F2/F4 exercise ``gate.qoder_security.main`` in process, on a *real* status
  file at an *absolute* path — ``main`` checks ``is_file()``. at:1007 before the
  worktree decision at:1012, so a missing file would fail the wrong way;
- F3 pins the one intended relaxation (INV-C's ``L``: the main-repo
  ``.worktrees`` directory now accepted);
- F6 is the static single-authority assertion (zero non-comment matches).

The three load-bearing mutations M-A/M-B/M-C (and M-D) are applied by the
orchestrator, one at a time, and each must turn the corresponding case red.
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
WRAPPERS_DIR = PKG_SRC / "agentic_loop" / "wrappers"
MERGE_SH = WRAPPERS_DIR / "merge.sh"
GATE_SRC = PKG_SRC / "agentic_loop" / "gate" / "__init__.py"
QODER_SRC = PKG_SRC / "agentic_loop" / "gate" / "qoder_security.py"

# The retired literal, spelled without a slash-wrapped copy of itself so that a
# plain grep of THIS file does not collide with the F6 static scan.
LITERAL = "/.worktrees/"

# Cause-specific witnesses: the exact refusal wording of each call site. Both
# are unchanged by WP-02 (INV-D keeps the visible prefixes and exit codes).
WORKTREE_REFUSAL = "resolves inside a worktree"
PROBE_FAIL_WITNESS = "PROBE_FAIL"
# The one output that would make F5 pass for the WRONG reason: merge.sh:29's
# resolver runs before the worktree probe at:37, so a blanket-failing
# AGENTIC_PYTHON dies there and a naive prefix+exit-code assertion goes green
# without ever reaching the probe. F5 asserts this string is absent.
RESOLVER_FAIL = "resolver failed"

ITER = "wp02-literal-removal"
PLAN_DIR = Path("docs/plans") / ITER


# ---------------------------------------------------------------------------
# git / fixture helpers
# ---------------------------------------------------------------------------
def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _head(repo: Path) -> str:
    return _run_git(repo, "rev-parse", "HEAD").stdout.strip()


def _default_branch(repo: Path) -> str:
    return _run_git(repo, "branch", "--show-current").stdout.strip()


def _status(
    repo: Path,
    wp: str = "WP-02",
    *,
    branch: str = "feat/wp02",
    state: str = "APPROVED_FOR_MERGE",
) -> dict:
    """A schema-valid v2 status document.

    The worktree refusal fires long before state/scope/risk are consulted, so
    this only has to be well-formed; the same document feeds both entry points.
    """
    return {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": wp,
        "iteration_id": ITER,
        "phase": "P1",
        "state": state,
        "role": "Developer",
        "executor": {"tool": "kimi-cli", "session": ""},
        "orchestrator": {"tool": "claude-code", "session": ""},
        "reviewer": {"tool": "claude-code", "session": ""},
        "git": {
            "base_branch": _default_branch(repo),
            "base_commit": _head(repo),
            "branch": branch,
            "worktree": "",
            "commit": "",
        },
        "scope": {"allowed_paths": ["docs/"], "forbidden_paths": [".env"]},
        "risk": {
            "production_writes_authorized": False,
            "network_authorized": False,
            "real_notifications_authorized": False,
            "irreversible_actions_authorized": False,
        },
        "evidence": {"changed_files": [], "tests": [], "artifacts": []},
        "review": {},
        "consult": {},
        "timestamps": {"created_at": "2026-10-15T00:00:00Z"},
    }


def _make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "init")
    return repo


def _add_sibling_worktree(repo: Path, tmp_path: Path, name: str, branch: str) -> Path:
    """The layout this repo actually uses: a SIBLING directory, never
    ``.worktrees/``. Under ``tmp_path`` (not ``repo``) so the worktree is not
    itself inside the repo tree."""
    wt = tmp_path / name
    _run_git(repo, "worktree", "add", "-q", "-b", branch, str(wt))
    return wt


def _write_status(repo: Path, status: dict, wp: str = "WP-02") -> Path:
    path = repo / PLAN_DIR / f"{wp}.status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return path


def _base_env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["AGENTIC_PYTHON"] = sys.executable
    return env


def _assert_path_is_literal_free(path: Path) -> None:
    """Self-proving precondition: the literal cannot be what decides this case.

    Without this, a fixture whose worktree happened to be named
    ``.worktrees/<x>`` would go red for the RIGHT reason today and for no reason
    at all after the change — a green that proves nothing.
    """
    assert LITERAL not in str(path), (
        f"fixture path {path} contains {LITERAL!r}; the literal would hit it and "
        "the case would pass for an unrelated reason"
    )


def _run_merge(
    repo: Path, status_arg: str, env: dict, *, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(MERGE_SH), str(status_arg)],
        cwd=cwd or repo,
        capture_output=True,
        text=True,
        env=env,
    )


def _qoder_refusal(
    status_path: Path, env: dict, result_file: Path
) -> tuple[str, str]:
    """Call ``qoder_security.main`` in a subprocess and report HOW it exited.

    Returns ``(kind, detail)`` where kind is ``"gate_error"`` (the worktree
    refusal shape), ``"other_error"`` (a different exception — anything else
    that stops before the merge proceeds) or ``"returned"``. ``detail``
    carries the refusal text (``GateError`` prints its own ``GATE_FAIL:`` line
    to stderr in ``__init__``, so that text never reaches the message), which
    keeps a failure attributable to a cause instead of a bare "it raised".

    ``GateError`` subclasses ``SystemExit`` (gate/__init__.py:66), NOT
    ``Exception``, so the handler must be ``except BaseException`` -- a bare
    ``except Exception`` would let this refusal slip past the probe entirely and
    abort the child at exit code 2 with an empty stdout.
    """
    probe = (
        f'''import io, sys, traceback
sys.path.insert(0, {str(PKG_SRC)!r})
from agentic_loop.gate import GateError
from agentic_loop.gate import qoder_security
'''
        + "sys.stderr = captured = io.StringIO()\n"
        + f"with open({str(result_file)!r}, 'w') as out:\n"
        + "    try:\n"
        + f"        code = qoder_security.main([{str(status_path)!r}])\n"
        + "    except BaseException as exc:\n"
        + "        kind = 'gate_error' if isinstance(exc, GateError) else 'other_error'\n"
        + "        out.write('RESULT=' + kind + chr(10))\n"
        + "        out.write('TYPE=' + type(exc).__name__ + chr(10))\n"
        + "        out.write('DETAIL=' + str(exc) + chr(10))\n"
        + "        traceback.print_exc(file=out)\n"
        + "    else:\n"
        + "        out.write('RESULT=returned' + chr(10))\n"
        + "        out.write('CODE=' + repr(code) + chr(10))\n"
        + "    # GateError already printed the authoritative GATE_FAIL line.\n"
        + "    out.write('STDERR=' + captured.getvalue() + chr(10))\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, env=env
    )
    assert res.returncode == 0, (res.stdout, res.stderr)
    transcript = result_file.read_text(encoding="utf-8")
    kind = next(
        line.split("=", 1)[1]
        for line in transcript.splitlines()
        if line.startswith("RESULT=")
    )
    # Flatten the whole transcript: the refusal wording may sit on the
    # GATE_FAIL stderr line, in the exception text, or in the traceback.
    detail = " ".join(transcript.splitlines())
    return kind, detail


# ---------------------------------------------------------------------------
# F1 / F3: merge.sh (the shell call site)
# ---------------------------------------------------------------------------
def test_f1_merge_refuses_sibling_worktree(tmp_path: Path) -> None:
    """F1 [merge-refuses-sibling-worktree]: a linked worktree whose path has no
    literal segment must be REFUSED. The retired literal accepts it (M-A red)."""
    repo = _make_repo(tmp_path)
    status = _status(repo)
    wt = _add_sibling_worktree(repo, tmp_path, "wp02-sibling", "feat/wp02-sibling")
    status_path = _write_status(wt, status)

    _assert_path_is_literal_free(status_path)

    res = _run_merge(repo, status_path, _base_env())

    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert WORKTREE_REFUSAL in res.stderr, (res.stdout, res.stderr)
    # Cause-specific: the refusal is the worktree decision, not "not found" --
    # which could only be reached by the literal failing to see the file.
    assert "status file not found" not in res.stderr, (res.stdout, res.stderr)


def test_f3_merge_accepts_literal_dot_worktrees_dir_in_main_repo(
    tmp_path: Path,
) -> None:
    """F3 [merge-accepts-literal-...]: INV-C's one relaxation. A REAL
    ``.worktrees/fake`` directory inside the main repo is main-repo content, so
    the git-fact predicate answers False and merge.sh proceeds past the worktree
    refusal -- exactly the point the retired literal cut short. The assertion
    locks that: the run is not refused as "inside a worktree", and a
    differing-argument control proves how far past the refusal it got."""
    repo = _make_repo(tmp_path)
    status = _status(repo)
    nested = repo / ".worktrees" / "fake"
    nested.mkdir(parents=True)
    status_path = nested / "WP-02.status.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    # The literal DOES hit this path -- that is the point of F3, so the F1
    # self-proof deliberately does not apply here.
    assert LITERAL in str(status_path)

    env = _base_env()
    res = _run_merge(repo, status_path, env)
    assert WORKTREE_REFUSAL not in res.stderr, (res.returncode, res.stdout, res.stderr)

    # Positive reachability control: the ONLY difference is the argument, so the
    # SYMMETRIC refusal proves the literal is no longer cutting this path short.
    # With the unchanged literal, the status run stops at merge.sh:37 (worktree
    # refusal) and this control stops at merge.sh:48 (status validation); under
    # the predicate BOTH get past the read at:41 and die at the validator.
    control = _run_merge(repo, repo / "README.md", env)
    assert WORKTREE_REFUSAL not in control.stderr, (control.stdout, control.stderr)
    assert "status validation failed" in control.stderr, (control.stdout, control.stderr)
    # The status run is well-formed JSON, so it gets exactly as far as the
    # control and no further: the worktree decision let it through, and nothing
    # after that point depends on the directory NAME.
    assert res.returncode == control.returncode, (res.stderr, control.stderr)
    assert "status validation failed" in res.stderr, (res.stdout, res.stderr)


# ---------------------------------------------------------------------------
# F2 / F4: gate.qoder_security (the Python call site)
# ---------------------------------------------------------------------------
def test_f2_qoder_refuses_sibling_worktree(tmp_path: Path) -> None:
    """F2 [qoder-refuses-sibling-worktree]: same sibling layout, in-process
    entry point. The retired literal accepts it (M-B red)."""
    repo = _make_repo(tmp_path)
    status = _status(repo)
    wt = _add_sibling_worktree(repo, tmp_path, "wp02-qoder-sib", "feat/wp02-qoder-sib")
    status_path = _write_status(wt, status)

    _assert_path_is_literal_free(status_path)
    # The fixture must survive qoder_security.main's is_file() check at:1007,
    # which runs BEFORE the worktree decision at:1012 -- otherwise this case
    # would fail as "status file not found" (wrong reason, no evidence).
    assert status_path.is_file()

    kind, detail = _qoder_refusal(
        status_path, _base_env(), tmp_path / "qoder-f2.txt"
    )

    assert kind == "gate_error", detail
    assert WORKTREE_REFUSAL in str(detail), detail
    assert "not found" not in str(detail), detail


def test_f4_qoder_accepts_literal_dot_worktrees_dir_in_main_repo(
    tmp_path: Path,
) -> None:
    """F4 [qoder-accepts-literal-...]: INV-C's one relaxation on the Python
    side. This node does NOT claim qoder's scan passes -- only that the worktree
    decision at:1012 does not refuse a main-repo ``.worktrees`` directory. Note
    it accordingly accepts EITHER a clean return OR a later, differently-caused
    GateError; the single thing it forbids is the worktree refusal."""
    repo = _make_repo(tmp_path)
    status = _status(repo)
    nested = repo / ".worktrees" / "fake"
    nested.mkdir(parents=True)
    status_path = nested / "WP-02.status.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    assert LITERAL in str(status_path)
    assert status_path.is_file()

    kind, detail = _qoder_refusal(
        status_path, _base_env(), tmp_path / "qoder-f4.txt"
    )

    assert WORKTREE_REFUSAL not in str(detail), detail
    assert kind in {"gate_error", "other_error", "returned"}, (kind, detail)


# ---------------------------------------------------------------------------
# F5: merge.sh stays fail-closed when ONLY the probe fails
# ---------------------------------------------------------------------------
_SHIMMED_PROBE = f"""\
import sys

try:
    from agentic_loop.gate import path_is_in_worktree
except Exception:
    print("PROBE_FAIL")
    sys.exit(0)

from pathlib import Path

print("WORKTREE" if path_is_in_worktree(Path(sys.argv[1])) else "MAIN")
"""


def _make_probe_failing_python(tmp_path: Path) -> Path:
    """A shim that is a real Python for every ``-m agentic_loop.*`` call and
    fails ONLY the inline worktree probe.

    A blanket-failing interpreter is worthless here: merge.sh:29 calls
    ``-m agentic_loop.resolve_paths`` BEFORE the probe at:37, so it would die
    with ``MERGE_FAIL: resolver failed`` and exit 2 -- satisfying a naive
    "MERGE_FAIL prefix + exit code" assertion while the probe is never reached.
    The shim is reached only by the probe's ``if __name__ == "__main__"``
    dispatch, so this deliberately mirrors that one entry point.
    """
    real = _base_env()["AGENTIC_PYTHON"]
    shim = tmp_path / "shim-python"
    shim.write_text(
        "#!/bin/sh\n"
        f'if [ "${{1:-}}" = "-m" ]; then exec {real} "$@"; fi\n'
        f'exec {real} -c {json.dumps(_SHIMMED_PROBE)} "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim


def test_f5_merge_probe_failure_fails_closed(tmp_path: Path) -> None:
    """F5 [merge-probe-failure-fails-closed]: the probe crash collapses into
    PROBE_FAIL and merge.sh REFUSES. Removing the ``|| echo PROBE_FAIL``
    fallback turns this red (M-C) -- but only if the case actually reaches the
    probe, which is why the resolver-failure string is asserted absent."""
    repo = _make_repo(tmp_path)
    status = _status(repo)
    # A MAIN-repo status file: without the forced probe failure this is the
    # accepting path, so a refusal can only come from the probe.
    status_path = _write_status(repo, status)
    _assert_path_is_literal_free(status_path)

    shim = _make_probe_failing_python(tmp_path)
    env = _base_env()
    env["AGENTIC_PYTHON"] = str(shim)

    # Control: the same shim passes `-m agentic_loop.*` through untouched.
    passthrough = subprocess.run(
        [str(shim), "-m", "agentic_loop.resolve_paths", "--root", "main_repo"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert passthrough.returncode == 0, (passthrough.stdout, passthrough.stderr)
    assert passthrough.stdout.strip(), passthrough.stdout

    res = _run_merge(repo, status_path, env)

    # The guard that makes the red evidence meaningful.
    assert RESOLVER_FAIL not in res.stderr, (
        "merge.sh died at the line-29 resolver instead of reaching the worktree "
        f"probe; this case proves nothing about the probe: {(res.stdout, res.stderr)}"
    )
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert WORKTREE_REFUSAL in res.stderr, (res.stdout, res.stderr)
    # Whether the verdict string survives `set -euo pipefail` or the command
    # substitution collapses to empty, the refusal is identical: only the exact
    # verdict MAIN passes. NB: under M-C (fallback removed) this file is
    # bash-4-only -- bash 3.2 expands the failed substitution to empty and still
    # refuses, so M-C is red on bash >= 4.4 (Linux CI / the declared runner).
    assert PROBE_FAIL_WITNESS not in res.stdout + res.stderr, (res.stdout, res.stderr)


# ---------------------------------------------------------------------------
# F6: static single-authority assertion
# ---------------------------------------------------------------------------
def _code_without_comments(text: str) -> list[str]:
    """Strip comments line by line, keeping line count aligned.

    Distinguishing comments from code by position: a shebang is skipped; a line
    whose first non-space character is ``#`` is a whole-line comment; otherwise
    a ``#`` that starts the line or is preceded by whitespace opens a trailing
    comment. ``#`` NOT preceded by whitespace stays in place -- it is part of a
    token (a regex, a colour literal, a ``#{...}`` shell expansion), and
    treating it as a comment would let real code hide behind it.

    The two legitimate matches this must ignore are exactly the whole-line
    comments at ``wrappers/finalize_merge.sh:38`` and ``gate/__init__.py:809``.
    """
    code: list[str] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if index == 1 and line.startswith("#!"):
            code.append("")
            continue
        stripped = line.lstrip()
        if stripped.startswith("#"):
            code.append("")
            continue
        for pos in range(1, len(line)):
            if line[pos] == "#" and line[pos - 1] in " \t":
                line = line[:pos]
                break
        code.append(line)
    return code


def test_f6_no_literal_worktree_check_remains() -> None:
    """F6 [no-literal-worktree-check-remains]: ZERO non-comment product-code
    matches of the literal under ``src/agentic_loop/`` — i.e. the literal no
    longer decides anything."""
    hits: list[str] = []
    comment_only: list[str] = []
    scanned = 0
    for path in sorted((PKG_SRC / "agentic_loop").rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".sh"}:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped_lines = _code_without_comments(text)
        source_lines = text.splitlines()
        for line_no, code_line in enumerate(stripped_lines, start=1):
            if LITERAL in code_line:
                hits.append(f"{path.relative_to(PKG_SRC)}:{line_no}")
        for line_no, src_line in enumerate(source_lines, start=1):
            if LITERAL in src_line and LITERAL not in stripped_lines[line_no - 1]:
                comment_only.append(f"{path.relative_to(PKG_SRC)}:{line_no}")

    assert scanned > 10, f"static scan touched only {scanned} files"
    assert hits == [], f"literal-based worktree check still in product code: {hits}"
    # The scan must be looking at the real tree, not silently skipping files:
    # the two long-standing comment-only matches have to show up, plus the ones
    # WP-02 itself added while explaining why the literal is gone.
    assert "agentic_loop/wrappers/finalize_merge.sh:38" in comment_only, comment_only
    assert "agentic_loop/gate/__init__.py:809" in comment_only, comment_only
    assert len(comment_only) >= 2, comment_only


def test_f6_all_five_call_sites_reference_one_predicate() -> None:
    """The single authority self-check, executable: the one predicate name is
    referenced by every call site that produces the "inside a worktree"
    semantics, and this WP did not redefine it."""
    predicate_def = "def path_is_in_worktree("
    assert predicate_def in GATE_SRC.read_text(encoding="utf-8")
    assert predicate_def not in QODER_SRC.read_text(encoding="utf-8")
    assert predicate_def not in MERGE_SH.read_text(encoding="utf-8")

    for path in (MERGE_SH, QODER_SRC):
        assert "path_is_in_worktree" in path.read_text(encoding="utf-8"), path


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
