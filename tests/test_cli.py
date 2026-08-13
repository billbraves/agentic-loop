"""Forwarding-contract tests for the agentic CLI.

These never invoke real codex/kimi: forwarding is exercised against a fake git
repo whose scripts/agentic/*.sh simply echo their argv and exit with a chosen
code, so we can assert argv passthrough + exit-code transparency in isolation.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"


def _run_cli(argv, cwd, extra_env=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", "from agentic_loop.cli import main; raise SystemExit(main())", *argv],
        cwd=str(cwd), env=env, capture_output=True, text=True,
    )


@pytest.fixture
def fake_repo(tmp_path):
    """A git repo with fake echoing scripts/agentic/*.sh wrappers."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    sad = tmp_path / "scripts" / "agentic"
    sad.mkdir(parents=True)
    # every subcommand maps to a wrapper; fake each one
    wrappers = {
        "codex_merge_gate.sh": 0,
        "redispatch.sh": 0,
        "preflight.sh": 0,
        "finalize_merge.sh": 0,
        "dispatch_lint.sh": 0,
        "quality-gate.sh": 0,
        "lock.sh": 0,
        "kimi-health.sh": 7,  # non-zero to prove exit-code passthrough
    }
    for name, rc in wrappers.items():
        p = sad / name
        p.write_text(
            "#!/usr/bin/env bash\n"
            'echo "WRAPPER={0} ARGV=$*"\n'
            'echo "on stderr" >&2\n'
            "exit {1}\n".format(name, rc)
        )
        p.chmod(0o755)
    return tmp_path


def test_no_args_prints_usage_rc0(fake_repo):
    r = _run_cli([], fake_repo)
    assert r.returncode == 0
    assert "usage: agentic" in r.stdout
    for sub in ("gate", "redispatch", "preflight", "finalize",
                "dispatch-lint", "quality-gate", "lock", "health"):
        assert sub in r.stdout


def test_help_flag_rc0(fake_repo):
    for flag in ("-h", "--help"):
        r = _run_cli([flag], fake_repo)
        assert r.returncode == 0
        assert "usage: agentic" in r.stdout


def test_unknown_subcommand_rc_nonzero_with_usage(fake_repo):
    r = _run_cli(["bogus-sub"], fake_repo)
    assert r.returncode != 0
    assert "unknown subcommand" in r.stderr
    assert "usage: agentic" in r.stderr


@pytest.mark.parametrize("sub,wrapper", [
    ("gate", "codex_merge_gate.sh"),
    ("redispatch", "redispatch.sh"),
    ("preflight", "preflight.sh"),
    ("finalize", "finalize_merge.sh"),
    ("dispatch-lint", "dispatch_lint.sh"),
    ("quality-gate", "quality-gate.sh"),
    ("lock", "lock.sh"),
    ("health", "kimi-health.sh"),
])
def test_subcommand_maps_to_wrapper(fake_repo, sub, wrapper):
    r = _run_cli([sub, "a", "b c"], fake_repo)
    assert "WRAPPER={}".format(wrapper) in r.stdout


def test_argv_passthrough_verbatim(fake_repo):
    r = _run_cli(["lock", "acquire", "--kind", "wp", "--key", "x y"], fake_repo)
    # the fake wrapper echoes "$*"; assert every token survived in order
    assert "ARGV=acquire --kind wp --key x y" in r.stdout


def test_exit_code_passthrough(fake_repo):
    # health -> kimi-health.sh fake exits 7
    r = _run_cli(["health", "s", "o", "n"], fake_repo)
    assert r.returncode == 7


def test_locates_main_repo_from_linked_worktree(fake_repo):
    """From a real linked worktree, git-common-dir resolves the MAIN repo root.

    This exercises the actual worktree semantics the wrappers depend on: the
    worktree has no scripts/agentic of its own, yet ``agentic gate`` must still
    find the main repo's wrapper via ``git rev-parse --git-common-dir`` (whose
    parent is the main root), not via the worktree toplevel.
    """
    # Seed a commit WITHOUT scripts/agentic so the wrappers stay untracked and
    # do NOT propagate into the linked worktree checkout. The worktree can only
    # reach them by resolving git-common-dir to the main root.
    (fake_repo / "README").write_text("seed\n")
    subprocess.run(["git", "-C", str(fake_repo), "add", "README"], check=True)
    subprocess.run(
        ["git", "-C", str(fake_repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "seed"],
        check=True,
    )
    wt = fake_repo.parent / (fake_repo.name + "_wt")
    subprocess.run(
        ["git", "-C", str(fake_repo), "worktree", "add", "-q", "-d", str(wt)],
        check=True,
    )
    # the linked worktree has NO scripts/agentic of its own (wrappers untracked)
    assert not (wt / "scripts" / "agentic").exists()
    r = _run_cli(["gate", "z"], wt)
    assert "WRAPPER=codex_merge_gate.sh" in r.stdout
    assert "ARGV=z" in r.stdout


# --------------------------------------------------------------------------
# WP-23 dual-copy wrapper resolution: main-repo first, else bundled, else clean
# error. The tests below install the package into an isolated venv so the
# bundled wrappers/ copy is reachable exactly as an external consumer would see
# it, and stub out the resource-resolution / git-root helpers where a case needs
# the "neither present" branch.
# --------------------------------------------------------------------------

BUNDLED_WRAPPERS = SRC / "agentic_loop" / "wrappers"


def test_all_eight_wrappers_are_bundled():
    """Every forwarding subcommand has a bundled .sh fallback (external case)."""
    for wrapper in (
        "codex_merge_gate.sh", "redispatch.sh", "preflight.sh",
        "finalize_merge.sh", "dispatch_lint.sh", "kimi-health.sh",
        "lock.sh", "quality-gate.sh",
    ):
        assert (BUNDLED_WRAPPERS / wrapper).is_file(), wrapper


def test_main_repo_copy_wins_over_bundled(fake_repo):
    """When a main-repo scripts/agentic/<wrapper>.sh exists it is used, not the
    bundled copy — proving dogfood priority. The fake wrapper echoes a sentinel
    the bundled real wrapper never would."""
    r = _run_cli(["gate", "z"], fake_repo)
    assert r.returncode == 0
    assert "WRAPPER=codex_merge_gate.sh" in r.stdout  # the fake main-repo copy
    assert "ARGV=z" in r.stdout


def test_bundled_copy_runs_when_no_scripts_dir(tmp_path):
    """External-consumer case: no scripts/agentic/ and not even a git repo, yet a
    forwarding subcommand runs the *bundled* wrapper (not a 'wrapper not found'
    error from the CLI).

    Proof vehicle: ``gate`` with no args reaches the bundled
    ``codex_merge_gate.sh``, whose own arg-count guard fires (``$# -ne 1`` ->
    prints ``usage: <bundled-path>/codex_merge_gate.sh`` and exits 64) *before*
    it ever touches git. So rc 64 + a usage line naming the bundled script's own
    path is unambiguous evidence the bundled bash body executed — while the CLI's
    own 'not found' branch (rc 2) did not fire.
    """
    # tmp_path is a bare directory: no git, no scripts/agentic/.
    assert not (tmp_path / "scripts").exists()
    r = _run_cli(["gate"], tmp_path)  # zero forwarded args -> wrapper's own usage
    assert r.returncode == 64, (r.returncode, r.stdout, r.stderr)
    combined = r.stdout + r.stderr
    assert "codex_merge_gate.sh" in combined
    assert "usage:" in combined
    # It was the bundled copy, not a main-repo scripts/agentic/ path.
    assert "scripts/agentic" not in combined
    # And crucially NOT the CLI's own clean-error branch.
    assert "not found" not in r.stderr


def test_clean_error_when_neither_copy_present(tmp_path):
    """When neither a main-repo copy nor a bundled copy resolves, the CLI emits a
    clean one-line error (rc 2), never a Python traceback.

    Simulated by pointing the CLI at a wrapper package that has no such file:
    monkeypatch _WRAPPER_PACKAGE to an empty temp package and run with no git
    repo present so the main-repo branch also misses.
    """
    # A throwaway importable package with NO .sh files.
    empty_pkg = tmp_path / "empty_wrappers_pkg"
    empty_pkg.mkdir()
    (empty_pkg / "__init__.py").write_text("")
    prog = (
        "import sys; sys.path.insert(0, {sp!r}); sys.path.insert(0, {emp!r}); "
        "from agentic_loop import cli; "
        "cli._WRAPPER_PACKAGE = 'empty_wrappers_pkg'; "
        "raise SystemExit(cli.main(['gate', 'x']))"
    ).format(sp=str(SRC), emp=str(tmp_path))
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    r = subprocess.run(
        [sys.executable, "-c", prog],
        cwd=str(tmp_path), env=env, capture_output=True, text=True,
    )
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "not found" in r.stderr
    assert "Traceback" not in r.stderr


def test_wrapper_missing_rc_nonzero(tmp_path):
    """No main-repo scripts/agentic AND bundled package stubbed empty -> clean
    'not found' (rc 2), not a traceback. (Superseded semantics: a bare git repo
    now falls back to the bundled copy; the 'not found' path requires *both* to
    be absent, which this test forces via the empty wrapper package.)"""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    empty_pkg = tmp_path / "empty_wrappers_pkg2"
    empty_pkg.mkdir()
    (empty_pkg / "__init__.py").write_text("")
    prog = (
        "import sys; sys.path.insert(0, {sp!r}); sys.path.insert(0, {emp!r}); "
        "from agentic_loop import cli; "
        "cli._WRAPPER_PACKAGE = 'empty_wrappers_pkg2'; "
        "raise SystemExit(cli.main(['gate', 'x']))"
    ).format(sp=str(SRC), emp=str(tmp_path))
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    r = subprocess.run(
        [sys.executable, "-c", prog],
        cwd=str(tmp_path), env=env, capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "not found" in r.stderr
    assert "Traceback" not in r.stderr


# --------------------------------------------------------------------------
# WP-23 rework, finding ①: a bundled fat wrapper must resolve its sibling .sh
# calls relative to its OWN directory (``here="$(cd "$(dirname "$0")" && pwd)"``),
# not via ``$main_root``/``$repo_root`` + ``/scripts/agentic/``. Otherwise, in an
# external ``pip install`` project that has no ``scripts/agentic/``, the CLI finds
# the bundled preflight/finalize wrapper and then crashes on the missing sibling.
#
# These tests run the *bundled* copies directly (as the CLI would, via the
# resource path) inside a synthetic external project — a git repo + linked
# worktree with NO scripts/agentic/ anywhere — and prove the wrappers reach their
# own success logic by driving the co-located bundled siblings (dispatch_lint.sh,
# lock.sh) through ``$here``.
# --------------------------------------------------------------------------

PKG_SRC = SRC  # importable agentic_loop.* lives directly under src/


def _external_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    # lock.sh derives its owner from this; set it so acquire/release do not abort.
    env.setdefault("CLAUDE_CODE_SESSION_ID", "wp23extconsumer")
    return env


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True,
                   capture_output=True, text=True)


def test_bundled_preflight_resolves_siblings_in_external_project(tmp_path):
    """External-consumer sim for finding ①: bundled preflight.sh reaches
    PREFLIGHT_PASS in a git project that has NO scripts/agentic/ — which is only
    possible if its dispatch_lint.sh AND lock.sh sibling calls resolved to the
    co-located bundled copies via ``$here`` (not ``$main_root/scripts/agentic``)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    _git(proj, "config", "user.email", "t@t")
    _git(proj, "config", "user.name", "t")
    (proj / ".agentic").mkdir()
    iterdir = proj / "docs" / "plans" / "it-1"
    iterdir.mkdir(parents=True)
    (iterdir / "WP-01-brief.md").write_text(
        "## Acceptance tests\nx\n"
        "## Allowed and forbidden paths\nx\n"
        "## Completion definition\nx\n"
    )
    status = {
        "schema_version": "agentic-wp-status/v1", "work_package_id": "WP-01",
        "iteration_id": "it-1", "phase": "P0", "state": "IMPLEMENTING",
        "role": "Developer", "executor": {"tool": "kimi-cli"},
        "orchestrator": {"tool": "claude-code"}, "reviewer": {"tool": "claude-code"},
        "git": {"base_branch": "main", "base_commit": "0" * 7, "branch": "feat/x",
                "worktree": "wt"},
        "scope": {"allowed_paths": ["docs/"], "forbidden_paths": []},
        "risk": {"production_writes_authorized": False, "network_authorized": False,
                 "real_notifications_authorized": False,
                 "irreversible_actions_authorized": False},
        "evidence": {"tests": []}, "review": {"decision": None}, "timestamps": {},
    }
    import json as _json
    (iterdir / "WP-01.status.json").write_text(_json.dumps(status))
    _git(proj, "add", "-A")
    _git(proj, "commit", "-qm", "seed")
    _git(proj, "branch", "-M", "main")
    _git(proj, "worktree", "add", "-q", "-b", "feat/x", str(proj / "wt"))

    # The whole synthetic project has NO scripts/agentic/ — the only reachable
    # dispatch_lint.sh / lock.sh are the bundled siblings next to preflight.sh.
    assert not (proj / "scripts").exists()
    assert not ((proj / "wt") / "scripts").exists()

    bundled_preflight = BUNDLED_WRAPPERS / "preflight.sh"
    r = subprocess.run(
        ["bash", str(bundled_preflight), "docs/plans/it-1/WP-01.status.json"],
        cwd=str(proj / "wt"), env=_external_env(), capture_output=True, text=True,
    )
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "PREFLIGHT_PASS" in r.stdout, (r.stdout, r.stderr)
    # lock.sh (a bundled sibling) actually ran and acquired the WP lock.
    assert "LOCK_ACQUIRED" in r.stderr or "LOCK_REACQUIRED" in r.stderr, r.stderr
    # No missing-file crash from the pre-fix $main_root/scripts/agentic/ path.
    assert "No such file" not in r.stderr
    assert "scripts/agentic" not in r.stderr


# --------------------------------------------------------------------------
# WP-23 rework round 2, finding ①: the git-coupled preamble
#   main_root="$(dirname "$(cd "$(git rev-parse --git-common-dir)" && pwd)")"
# hard-failed under ``set -euo pipefail`` in a directory with NO git repo, so an
# external ``pip install`` consumer running ``agentic gate <status>`` from a
# non-git project died at the shell before ever reaching the Python engine. The
# fix makes the preamble git-OPTIONAL (best-effort ``git rev-parse``; prepend the
# live source path only when inside the framework repo, else rely on the already
# installed module).
#
# Discriminator used below: the string ``RESOLVE_FAIL`` is printed ONLY by the
# Python engine (agentic_loop.resolve_paths._fail / the engine modules). Under the
# OLD preamble the bare command-substitution ``$(git rev-parse ...)`` failed and
# ``set -e`` killed the script *before* any engine ran, so ``RESOLVE_FAIL`` could
# never appear — only a bare shell ``fatal: not a git repository`` line. Its
# presence therefore proves the preamble passed through and the wrapper reached
# its own body / the Python engine. A bare ``fatal:`` line NOT wrapped in a
# ``RESOLVE_FAIL`` message would mean the old set -e death survived.
# --------------------------------------------------------------------------

_ALL_WRAPPERS_MINARGS = {
    "codex_merge_gate.sh": ["s.json"],
    "redispatch.sh": ["s.json"],
    "preflight.sh": ["s.json"],
    "finalize_merge.sh": ["s.json"],
    "dispatch_lint.sh": ["s.json"],
    "quality-gate.sh": ["s.json"],
    "lock.sh": ["status"],
    "kimi-health.sh": ["s.json", "o.txt", "snap.json"],
}


def _nongit_env():
    """agentic_loop importable via PYTHONPATH, but CWD will be a non-git dir so
    the wrappers' git-optional preamble must not hard-fail."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env.setdefault("CLAUDE_CODE_SESSION_ID", "wp23standalone")
    return env


@pytest.mark.parametrize("wrapper,args", list(_ALL_WRAPPERS_MINARGS.items()))
def test_bundled_wrapper_survives_nongit_preamble(tmp_path, wrapper, args):
    """finding ① standalone pin: every bundled wrapper, run from a directory with
    NO git repo and NO scripts/agentic/, must pass through its git-optional
    preamble and reach its OWN logic / the Python engine — never die at the shell
    on ``git rev-parse --git-common-dir``.

    Proven by: the engine-only ``RESOLVE_FAIL`` token appears, and no bare shell
    ``fatal: not a git repository`` line survives outside a RESOLVE_FAIL wrapper
    (which would signal the pre-fix set -e death)."""
    # tmp_path is a bare directory: NOT a git repo, no scripts/agentic/.
    assert not (tmp_path / ".git").exists()
    (tmp_path / "s.json").write_text('{"x": 1}\n')
    r = subprocess.run(
        ["bash", str(BUNDLED_WRAPPERS / wrapper), *args],
        cwd=str(tmp_path), env=_nongit_env(), capture_output=True, text=True,
    )
    combined = r.stdout + r.stderr
    # The wrapper reached the Python engine (only the engine prints RESOLVE_FAIL).
    assert "RESOLVE_FAIL" in combined, (wrapper, r.returncode, r.stdout, r.stderr)
    # No un-wrapped bare shell fatal (the pre-fix set -e preamble death signature).
    bare_fatals = [
        ln for ln in combined.splitlines()
        if "not a git repository" in ln and "RESOLVE_FAIL" not in ln
    ]
    assert not bare_fatals, (wrapper, bare_fatals)


def test_bundled_gate_and_redispatch_reach_python_engine_nongit(tmp_path):
    """finding ① minimum bar (per acceptance §1): from a non-git dir, ``gate`` and
    ``redispatch`` — the two thin ``exec python3 -m agentic_loop.X`` shells — must
    reach the Python engine's arg-validation / normal path rather than dying at
    the preamble.

    With NO args each wrapper's own ``$# -ne 1`` guard fires first (usage, rc 64),
    proving the shell body ran; with a status arg the engine module runs and its
    own resolver reports RESOLVE_FAIL (rc 2) — either way the git-coupled preamble
    no longer blocks reaching python3 -m agentic_loop.X."""
    assert not (tmp_path / ".git").exists()
    env = _nongit_env()
    for wrapper in ("codex_merge_gate.sh", "redispatch.sh"):
        # No args -> the wrapper's own usage guard (shell body reached).
        r0 = subprocess.run(
            ["bash", str(BUNDLED_WRAPPERS / wrapper)],
            cwd=str(tmp_path), env=env, capture_output=True, text=True,
        )
        assert r0.returncode == 64, (wrapper, r0.returncode, r0.stdout, r0.stderr)
        assert "usage" in (r0.stdout + r0.stderr).lower(), (wrapper, r0.stderr)
        # One arg -> python3 -m agentic_loop.X runs; engine's own resolver speaks.
        (tmp_path / "s.json").write_text('{"x": 1}\n')
        r1 = subprocess.run(
            ["bash", str(BUNDLED_WRAPPERS / wrapper), "s.json"],
            cwd=str(tmp_path), env=env, capture_output=True, text=True,
        )
        assert "RESOLVE_FAIL" in (r1.stdout + r1.stderr), (
            wrapper, r1.returncode, r1.stdout, r1.stderr)


def test_bundled_finalize_resolves_lock_sibling_in_external_project(tmp_path):
    """External-consumer sim for finding ①: bundled finalize_merge.sh reaches
    FINALIZE_OK in a git project with NO scripts/agentic/ — proving its
    ``lock.sh release`` sibling call resolved to the bundled copy via ``$here``
    rather than ``$repo_root/scripts/agentic/lock.sh`` (which does not exist)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    _git(proj, "config", "user.email", "t@t")
    _git(proj, "config", "user.name", "t")
    (proj / ".agentic").mkdir()
    (proj / "seed.txt").write_text("s\n")
    _git(proj, "add", "-A")
    _git(proj, "commit", "-qm", "seed")
    _git(proj, "branch", "-M", "main")
    base = subprocess.run(["git", "-C", str(proj), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
    _git(proj, "checkout", "-q", "-b", "feat/x")
    (proj / "f.txt").write_text("f\n")
    _git(proj, "add", "-A")
    _git(proj, "commit", "-qm", "feat")
    feat = subprocess.run(["git", "-C", str(proj), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
    _git(proj, "checkout", "-q", "main")
    _git(proj, "merge", "-q", "--no-ff", "feat/x", "-m", "merge feat/x")

    env = _external_env()
    # Pre-acquire the WP lock through the SAME bundled lock.sh so finalize's
    # release has a live lock to remove.
    subprocess.run(
        ["bash", str(BUNDLED_WRAPPERS / "lock.sh"), "acquire",
         "--kind", "wp", "--key", "it-1__WP-01"],
        cwd=str(proj), env=env, capture_output=True, text=True, check=True,
    )

    import json as _json
    status = {
        "schema_version": "agentic-wp-status/v2", "work_package_id": "WP-01",
        "iteration_id": "it-1", "phase": "P0", "state": "APPROVED_FOR_MERGE",
        "role": "Developer", "executor": {"tool": "kimi-cli"},
        "orchestrator": {"tool": "claude-code"}, "reviewer": {"tool": "claude-code"},
        "git": {"base_branch": "main", "base_commit": base, "branch": "feat/x",
                "worktree": ".", "commit": feat, "merged_commit": None},
        "scope": {"allowed_paths": ["docs/"], "forbidden_paths": []},
        "risk": {"production_writes_authorized": False, "network_authorized": False,
                 "real_notifications_authorized": False,
                 "irreversible_actions_authorized": False},
        "evidence": {"tests": [{"name": "t", "command": "x", "exit_code": 0,
                                "result": "pass"}]},
        "review": {"decision": "ACCEPT"}, "consult": {"decision": "ACCEPT"},
        "timestamps": {},
    }
    (proj / "docs").mkdir(exist_ok=True)
    (proj / "docs" / "wp.status.json").write_text(_json.dumps(status))

    r = subprocess.run(
        ["bash", str(BUNDLED_WRAPPERS / "finalize_merge.sh"), "docs/wp.status.json"],
        cwd=str(proj), env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "FINALIZE_OK" in r.stdout, (r.stdout, r.stderr)
    # The bundled lock.sh sibling ran without a WARN about a failed release, and
    # the pre-fix $repo_root/scripts/agentic/lock.sh missing-file path is gone.
    assert "No such file" not in r.stderr
    assert "scripts/agentic" not in r.stderr
