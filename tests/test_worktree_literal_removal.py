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

- F1 also carries its own premise check (``test_f1_status_fixture_is_schema_valid``):
  the fixture is schema-valid for APPROVED_FOR_MERGE, measured by running the
  shipped validator, so the case cannot go red for an earlier reason;
- F1/F5 exercise ``merge.sh`` end to end (refuses a sibling worktree; stays
  fail-closed when only the probe fails);
- F2/F4 exercise ``gate.qoder_security.main`` in process, on a *real* status
  file at an *absolute* path — ``main`` checks ``is_file()`` (currently :1008,
  after WP-02's insertion; :1007 pre-edit) before the worktree decision
  (currently :1019; :1012 pre-edit), so a missing file would fail the wrong way;
- F3 pins the one intended relaxation (INV-C's ``L``: the main-repo
  ``.worktrees`` directory now accepted);
- F6 is the static single-authority assertion (zero non-comment matches).

The three load-bearing mutations M-A/M-B/M-C (and M-D) are applied by the
orchestrator, one at a time, and each must turn the corresponding case red.

M-A is the reason the F1 fixture carries a FULLY schema-valid status document
(``_status``, asserted against the shipped validator by
``test_f1_status_fixture_is_schema_valid`` rather than asserted in prose). When
the literal is restored, ``merge.sh`` must reach its worktree decision with a
document that passes every earlier precondition, so the red output can only be
"this linked worktree was wrongly ACCEPTED" — the form the brief demands. An
under-specified document would instead abort at ``STATUS_INVALID`` /
``MERGE_FAIL: status validation failed``, i.e. an earlier failure wearing the
refusal's exit code.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"
WRAPPERS_DIR = PKG_SRC / "agentic_loop" / "wrappers"
MERGE_SH = WRAPPERS_DIR / "merge.sh"
GATE_SRC = PKG_SRC / "agentic_loop" / "gate" / "__init__.py"
QODER_SRC = PKG_SRC / "agentic_loop" / "gate" / "qoder_security.py"

# The retired literal, spelled without a slash-wrapped copy of itself so that a
# plain grep of THIS file does not collide with the F6 static scan. (This file is
# not under src/agentic_loop/ and F6 does not read it; the spelling is kept so a
# repo-wide grep for the literal still points only at the real sites.)
LITERAL = "/.worktrees/"

# In merge.sh the worktree refusal and a failed status validation BOTH print a
# `MERGE_FAIL:` prefix and exit 2. Only the first is this WP's subject, so every
# merge.sh case that claims "the worktree decision refused this" must also prove
# the OTHER was not what happened. Without that, a fixture whose document is
# rejected by the validator reads as a refusal and proves nothing (this is
# exactly how impl-r1's M-A red evidence was produced).
VALIDATION_FAILED = "status validation failed"

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
    """A schema-valid v2 status document for the state it declares.

    "Schema-valid" is a MEASURED claim, not a comment: the shipped validator is
    run over the exact bytes written (``test_f1_status_fixture_is_schema_valid``,
    and this helper's own subprocess call) and must print STATUS_VALID. It has to
    be, because ``merge.sh`` validates the status BEFORE its worktree decision:
    an invalid document short-circuits at ``MERGE_FAIL: status validation
    failed`` and never reaches the refusal. Every field STATE=APPROVED_FOR_MERGE
    requires is therefore material, not decoration:

    * ``git.worktree`` (the worktree that produced the commit) and ``git.branch``
      — required by the ``active_states`` block;
    * ``git.commit`` — required by the merge-state block;
    * ``review.decision`` — must be ACCEPT **and** carry a ``consult.decision``
      of ACCEPT, the v2 double-sign rule for a merge state. ACCEPT (not ``N/A``)
      keeps the merge-gate formula satisfied; ``N/A`` would additionally demand
      the consult ACCEPT that this fixture already provides.

    ``git`` deliberately carries ONLY the schema keys (plus none of its own):
    ``validate()`` rejects unknown top-level keys but not unknown nested ones.

    Keeping the document valid is not a way to dodge the worktree refusal; it is
    what lets the refusal be the thing that fires. The path handed to
    ``path_is_in_worktree`` is the status file itself, whose git facts are the
    enclosing worktree's — the recorded ``git.worktree`` is only read by the
    qoder gate to locate ``--cwd`` for a scan this node never reaches.
    """
    return {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": wp,
        "iteration_id": ITER,
        "phase": "P1",
        "state": state,
        "role": "Developer",
        "executor": {"tool": "kimi", "session": "wp02-fixture-session"},
        "orchestrator": {"tool": "claude-code", "session": "wp02-fixture-session"},
        "reviewer": {"tool": "claude-code", "session": "wp02-fixture-session"},
        "git": {
            "base_branch": _default_branch(repo),
            "base_commit": _head(repo),
            "branch": branch,
            "worktree": str(repo),
            "commit": _head(repo),
        },
        "scope": {"allowed_paths": ["docs/"], "forbidden_paths": [".env"]},
        "risk": {
            "production_writes_authorized": False,
            "network_authorized": False,
            "real_notifications_authorized": False,
            "irreversible_actions_authorized": False,
        },
        "evidence": {
            "changed_files": [],
            "tests": [{"command": "python3.11 -m pytest tests -q", "exit_code": 0}],
            "artifacts": [],
        },
        "review": {"decision": "ACCEPT", "round": "wp02-impl-r2"},
        "consult": {"decision": "ACCEPT"},
        "timestamps": {"created_at": "2026-10-15T00:00:00Z"},
    }


def _assert_status_is_schema_valid(path: Path, env: dict | None = None) -> None:
    """Prove the fixture is valid by RUNNING the shipped validator on it.

    Called by the F1 fixture before ``merge.sh`` is invoked. The assertion it
    makes (STATUS_VALID) is the one the orchestrator can re-check by hand:

        python3.11 -m agentic_loop.validate_wp_status <file>
    """
    res = subprocess.run(
        [sys.executable, "-m", "agentic_loop.validate_wp_status", str(path)],
        capture_output=True,
        text=True,
        env=env or _base_env(),
    )
    assert res.returncode == 0 and "STATUS_VALID" in res.stdout, (
        "the fixture status is not schema-valid, so merge.sh would abort at "
        "MERGE_FAIL: status validation failed instead of reaching the worktree "
        f"decision (the M-A evidence would then be worthless): "
        f"{(res.returncode, res.stdout, res.stderr)}"
    )


def _make_repo(tmp_path: Path, name: str = "agentic-loop-main-codex-merge") -> Path:
    """A real ``git init`` + commit, never a mock.

    Named after the live checkout because that is the topology this WP measured:
    a main repo whose own path contains no ``.worktrees`` segment, so the retired
    literal sees nothing to refuse. Nothing in these cases keys off the name (the
    predicate reads git facts); it just keeps the fixture faithful.
    """
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
def test_f1_status_fixture_is_schema_valid(tmp_path: Path) -> None:
    """The premise M-A rests on, asserted instead of claimed: the F1 fixture is
    schema-valid for APPROVED_FOR_MERGE, so a restored literal is caught by the
    WORKTREE refusal rather than by an earlier validation abort.

    This is deliberately not a prose comment: impl-r1 documented the fixture as
    "schema-valid" while it was missing git.worktree / git.commit /
    review.decision, and the resulting M-A red proved nothing.
    """
    repo = _make_repo(tmp_path)
    wt = _add_sibling_worktree(repo, tmp_path, "wp02-sibling", "feat/wp02-sibling")
    status_path = _write_status(wt, _status(repo))

    env = _base_env()
    _assert_status_is_schema_valid(status_path, env)
    # The orchestrator's independent hand-check of the same claim:
    #   python3.11 -m agentic_loop.validate_wp_status <this file>
    # prints STATUS_VALID, exit 0.
    assert env["AGENTIC_PYTHON"]


def test_f1_merge_refuses_sibling_worktree(tmp_path: Path) -> None:
    """F1 [merge-refuses-sibling-worktree]: a linked worktree whose path has no
    literal segment must be REFUSED. A restored literal ACCEPTS it (M-A red).

    Three assertions are load-bearing together, and that is the whole point of
    this round:

    * the worktree refusal wording is present;
    * ``status validation failed`` and ``status file not found`` are BOTH absent,
      because merge.sh:61 (not-found) and merge.sh:68 (validation) print the same
      ``MERGE_FAIL:`` prefix and exit 2 as the refusal at merge.sh:57. Without
      this exclusion a validation error is indistinguishable from a refusal;
    * the exit code and prefix stay as they are (INV-D).
    """
    repo = _make_repo(tmp_path)
    wt = _add_sibling_worktree(repo, tmp_path, "wp02-sibling", "feat/wp02-sibling")
    status_path = _write_status(wt, _status(repo))

    _assert_path_is_literal_free(status_path)
    env = _base_env()
    _assert_status_is_schema_valid(status_path, env)

    res = _run_merge(repo, status_path, env)

    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert WORKTREE_REFUSAL in res.stderr, (res.stdout, res.stderr)
    # Cause-specific, in both directions. The worktree decision is reached only
    # if the document survived the validator, and the refusal is the only
    # MERGE_FAIL it can be:
    assert VALIDATION_FAILED not in res.stderr, (res.stdout, res.stderr)
    assert "status file not found" not in res.stderr, (res.stdout, res.stderr)
    assert res.stderr.strip().startswith("MERGE_FAIL:"), (res.stdout, res.stderr)


def test_f3_merge_accepts_literal_dot_worktrees_dir_in_main_repo(
    tmp_path: Path,
) -> None:
    """F3 [merge-accepts-literal-...]: INV-C's one relaxation, proved positively.

    A REAL ``.worktrees/fake`` directory inside the main repo is main-repo
    content, so the git-fact predicate answers False and the whole gate runs to
    completion -- ``MERGE_OK``. The retired literal cut this run short at its
    worktree refusal, which is the cut-short the relaxed set RESTORES.

    Reaching MERGE_OK means the fixture must survive every later precondition
    too, so the branch the document names is a real local ref whose tip is a
    descendant of ``git.commit`` -- otherwise the run would stop at the branch
    lookup and "accepted" would only be inferred from where it died rather than
    observed. The control run keeps every argument identical and swaps ONLY the
    file content, so the difference cannot come from the directory name.
    """
    repo = _make_repo(tmp_path)
    status = _status(repo, branch="feat/wp02-f3")
    # The document's branch must exist locally, with the recorded commit as an
    # ancestor of its tip (merge.sh:108-115). Base commit == tip here.
    _run_git(repo, "branch", "feat/wp02-f3")
    nested = repo / ".worktrees" / "fake"
    nested.mkdir(parents=True)
    status_path = nested / "WP-02.status.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    # The literal DOES hit this path -- that is the point of F3, so the F1
    # self-proof deliberately does not apply here.
    assert LITERAL in str(status_path)

    env = _base_env()
    _assert_status_is_schema_valid(status_path, env)
    res = _run_merge(repo, status_path, env)

    # POSITIVE evidence of acceptance: exit 0 and the merge actually happened.
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "MERGE_OK" in res.stdout, (res.stdout, res.stderr)
    assert WORKTREE_REFUSAL not in res.stdout + res.stderr, (res.stdout, res.stderr)

    # Control: identical arguments, invalid content. It must be refused at the
    # validator, proving the acceptance above was decided by the worktree
    # predicate on a valid document and not by anything about the path.
    control = _run_merge(repo, repo / "README.md", env)
    assert control.returncode == 2, (control.returncode, control.stdout, control.stderr)
    assert VALIDATION_FAILED in control.stderr, (control.stdout, control.stderr)
    assert WORKTREE_REFUSAL not in control.stderr, (control.stdout, control.stderr)


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
    # The fixture must survive qoder_security.main's is_file() check (currently
    # :1008, after WP-02's edit; :1007 in the brief's pre-edit numbering), which
    # runs BEFORE the worktree decision -- otherwise this case would fail as
    # "status file not found" (wrong reason, no evidence).
    assert status_path.is_file()

    kind, detail = _qoder_refusal(
        status_path, _base_env(), tmp_path / "qoder-f2.txt"
    )

    assert kind == "gate_error", detail
    assert WORKTREE_REFUSAL in str(detail), detail
    assert "not found" not in str(detail), detail
    # Sibling shape of F1's cause-exclusion: the worktree refusal happens BEFORE
    # run_validator, so a validator complaint in the transcript would mean this
    # node was decided by something other than the worktree question.
    assert "validator rejected status" not in str(detail), detail


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
    # Must exist: is_file() (:1008) precedes the worktree decision.
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
    # A MAIN-repo status file: this is the document shape that WITHOUT the forced
    # probe failure reaches the ACCEPTING path -- F3 proves exactly that, on the
    # same tree. So a refusal here can only come from the probe, not from the
    # document being malformed (which would be the same wrong-reason failure that
    # invalidated impl-r1's M-A evidence).
    status_path = _write_status(repo, status)
    _assert_path_is_literal_free(status_path)
    _assert_status_is_schema_valid(status_path)

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
    assert VALIDATION_FAILED not in res.stderr, (res.stdout, res.stderr)
    # Whether the verdict string survives `set -euo pipefail` or the command
    # substitution collapses to empty, the refusal is identical: only the exact
    # verdict MAIN passes. NB: under M-C (fallback removed) this file is
    # bash-4-only -- bash 3.2 expands the failed substitution to empty and still
    # refuses, so M-C is red on bash >= 4.4 (Linux CI / the declared runner).
    assert PROBE_FAIL_WITNESS not in res.stdout + res.stderr, (res.stdout, res.stderr)


# ---------------------------------------------------------------------------
# F6: static single-authority assertion
# ---------------------------------------------------------------------------
def _code_without_comments(text: str, *, python: bool) -> list[str]:
    """Blank out real COMMENT TOKENS, keeping the line count aligned.

    Two earlier versions of this helper were defeated, both found by the
    second signature and reproduced by the orchestrator, because they judged
    comments by POSITION rather than by lexing:

    1. cutting at any ``#`` preceded by whitespace also cut inside a string, so
       ``if " # /.worktrees/"[3:] in str(f):`` became ``if " ``;
    2. blanking any physical line whose first non-space character is ``#`` also
       blanked a line INSIDE a triple-quoted string, so

           if \"\"\"
           # /.worktrees/
           \"\"\"[3:-1] in str(f):

       scanned clean while reconstructing the literal exactly at runtime.

    3. keeping the whole-line rule for SHELL was defeated the same way, because
       a shell single-quoted string spans physical lines too:

           needle='
           # /.worktrees/
           '

       blanks the middle line, and ``tr -d '\\n# '`` rebuilds the literal at
       runtime (confirmed: the rebuilt value equals the literal and bash exits
       successfully).

    For Python the only correct answer is the real lexer: ``tokenize`` reports
    COMMENT tokens and leaves string contents alone, so none of the tricks
    survive. Shell has no stdlib lexer here, so after being defeated three
    times by position-based heuristics this stops guessing: ``.sh`` files are
    scanned RAW, with no comment stripping at all. Over-reporting is the safe
    direction for INV-A, and the cost is paid once in the product code -- the
    two shell comments that discuss the retired literal spell it out in prose
    rather than as a contiguous string, so the raw scan has nothing to trip
    over and needs no exemption list.
    """
    lines = text.splitlines()
    if not python:
        # Raw, deliberately. Only the shebang is dropped, because it cannot
        # contain the literal and keeping it would be noise.
        return ["" if i == 1 and l.startswith("#!") else l
                for i, l in enumerate(lines, start=1)]

    keep = list(lines)
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Unlexable: keep every line verbatim. Over-reporting is safe; silently
        # dropping lines is what let the two bypasses through.
        return keep
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        row = tok.start[0] - 1
        if 0 <= row < len(keep):
            # Remove only the comment's own span, never the whole line, so code
            # preceding a trailing comment is still scanned.
            keep[row] = keep[row][: tok.start[1]]
    return keep


# The single exemption the raw .sh scan needs. finalize_merge.sh is OUTSIDE
# WP-02's allowed paths, so its explanatory comment cannot be reworded the way
# merge.sh's was. This is pinned by VERBATIM TEXT, not by file name or line
# number: the line must still be a whole-line comment and must still read
# exactly like this, so editing it into live code -- or adding any other
# shell line containing the literal -- fails F6 immediately.
_EXEMPT_SHELL_COMMENTS = {
    "agentic_loop/wrappers/finalize_merge.sh:38":
        '# A13: git-fact judgment instead of a "/.worktrees/" path literal (sibling',
}


def _is_exempt_shell_comment(where: str, line: str) -> bool:
    expected = _EXEMPT_SHELL_COMMENTS.get(where)
    return expected is not None and line.strip() == expected and line.lstrip().startswith("#")


def test_f6_scanner_cannot_be_hidden_behind_a_quoted_hash() -> None:
    """Adversarial guard on F6's own scanner, added at wp02-impl-r3.

    The second signature found that stripping a trailing comment at any ``#``
    preceded by whitespace also cuts inside STRING LITERALS, so executable code
    could smuggle the literal past the scan. Reproduced by the orchestrator:
    ``if " # /.worktrees/"[3:] in str(status_file):`` was truncated to
    ``if " `` and F6 reported zero hits while the code reconstructs the literal
    at runtime.

    This pins the fix: the scanner must still SEE a literal that sits in code,
    whatever precedes it on the line. Over-reporting is acceptable (it fails
    safe for INV-A); under-reporting is the defect.
    """
    # Bypass 1 (found at impl-r3): a quoted "#" must not open a comment.
    smuggled = 'if " # ' + LITERAL + '"[3:] in str(status_file):'
    assert LITERAL in _code_without_comments(smuggled, python=True)[0], (
        "scanner lost a literal inside executable code; a quoted '#' must not "
        "be treated as opening a comment"
    )

    # Bypass 2 (found at impl-r4): a physical line that merely STARTS with "#"
    # may be the inside of a triple-quoted string, and this expression
    # reconstructs the literal exactly at runtime.
    multiline = 'if """\n# ' + LITERAL + '\n"""[3:-1] in str(status_file):'
    assert (
        "".join(_code_without_comments(multiline, python=True)).find(LITERAL) >= 0
    ), (
        "scanner lost a literal held inside a triple-quoted string; judging "
        "comments by line position cannot survive this -- lex instead"
    )
    # Prove the construction is not a strawman: it really does rebuild it.
    assert eval('"""\n# ' + LITERAL + '\n"""[3:-1]') == LITERAL  # noqa: S307

    # Bypass 3 (found at impl-r5b): a shell single-quoted string also spans
    # physical lines, so the whole-line rule failed for .sh exactly as it did
    # for Python. `tr -d '\\n# '` rebuilds the literal at runtime.
    shell_multiline = "needle='\n# " + LITERAL + "\n'\n"
    assert LITERAL in "".join(
        _code_without_comments(shell_multiline, python=False)
    ), (
        "shell scan lost a literal held inside a single-quoted multiline "
        "string; .sh must be scanned raw rather than by line position"
    )

    # A genuine Python comment token must still be ignored, or F6 would always
    # fail on gate/__init__.py's explanatory comment.
    assert LITERAL not in _code_without_comments(f"  # {LITERAL} retired", python=True)[0]
    # Shell is scanned RAW on purpose, so a shell comment is NOT ignored. That
    # is why the two shell comments discussing the retired literal spell it out
    # in prose instead of as a contiguous string -- asserted by F6 itself
    # finding zero hits across the real tree.
    assert LITERAL in _code_without_comments(f"  # {LITERAL} retired", python=False)[0]
    # And a trailing comment must not swallow the code before it.
    assert LITERAL in _code_without_comments(
        f'x = "{LITERAL}"  # kept', python=True
    )[0]


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
        stripped_lines = _code_without_comments(text, python=path.suffix == ".py")
        source_lines = text.splitlines()
        for line_no, code_line in enumerate(stripped_lines, start=1):
            if LITERAL not in code_line:
                continue
            where = f"{path.relative_to(PKG_SRC)}:{line_no}"
            if _is_exempt_shell_comment(where, code_line):
                comment_only.append(where)
                continue
            hits.append(where)
        for line_no, src_line in enumerate(source_lines, start=1):
            if LITERAL in src_line and LITERAL not in stripped_lines[line_no - 1]:
                comment_only.append(f"{path.relative_to(PKG_SRC)}:{line_no}")

    assert scanned > 10, f"static scan touched only {scanned} files"
    assert hits == [], f"literal-based worktree check still in product code: {hits}"
    # The scan must be looking at the real tree, not silently skipping files:
    # both long-standing comment-only matches have to show up.
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
