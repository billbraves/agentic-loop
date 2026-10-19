"""WP-01 + WP-23: quality-gate.sh reads its path->test rules from the project's
.agentic/config.toml unified ``[[gate]]`` array (kind=command, stage=pre_review)
instead of hard-coding baofu paths.

These tests build a self-contained tmp git repo (which is therefore its own
`main_repo`, so resolve_paths' --config-section reads the tmp config), drop in
the real de-baofu'd quality-gate.sh + resolve_paths.py, and assert the emitted
``QUALITY_GATE_PLAN:`` lines — i.e. the expanded pytest/npm targets — for a
given changed set. The script announces the full plan before executing, so the
expansion is observable without running real suites.

The equivalence proof (``test_config_expansion_equivalent_to_old_hardcoded``)
pins the config-driven expansion to the exact target set the prior hard-coded
bash `case` produced, per changed-path category and in the same order.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Resolve the real wrapper + resolver from THIS package (parents[1] = package
# root packages/agentic-loop/), not the monorepo root. This keeps the test
# runnable both inside the monorepo and in the standalone extracted repo, where
# no top-level scripts/agentic/ exists — the package bundles its own copy.
PKG_ROOT = Path(__file__).resolve().parents[1]
QG = PKG_ROOT / "src" / "agentic_loop" / "wrappers" / "quality-gate.sh"
RESOLVER = PKG_ROOT / "src" / "agentic_loop" / "resolve_paths.py"
PKG_SRC = PKG_ROOT / "src"

# Direct reader tests import resolve_paths from the package under test.
if str(PKG_SRC) not in sys.path:
    sys.path.insert(0, str(PKG_SRC))
from agentic_loop import resolve_paths  # noqa: E402

# baofu's full command gate rule set (mirrors .agentic/config.toml after WP-01).
BAOFU_QG_CONFIG = """\
[[gate]]
name  = "tests"
kind  = "command"
stage = "pre_review"
[[gate.rule]]
match = "packages/engine/**"
run = [
  "uv run pytest packages/engine/tests -q",
  "uv run pytest tests/test_baseline_regression.py -q",
]
[[gate.rule]]
match = "packages/data-app/**"
run = [
  "uv run pytest packages/data-app/tests -q",
  "uv run pytest tests/test_baseline_regression.py -q",
]
[[gate.rule]]
match = "packages/mcp-server/**"
run = ["uv run pytest packages/mcp-server/tests -q"]
[[gate.rule]]
match = "packages/research-app/dashboard/frontend/**"
run = ["npm --prefix packages/research-app/dashboard/frontend run build"]
[[gate.rule]]
match = "packages/research-app/**"
run = [
  "uv run pytest packages/research-app/tests -q",
  "uv run pytest packages/research-app/dashboard/backend/tests -q",
]
[[gate.rule]]
match = "tests/**"
run = ["uv run pytest tests/test_baseline_regression.py -q"]
[[gate.rule]]
match = "tools/baseline/**"
run = ["uv run pytest tests/test_baseline_regression.py -q"]
"""

# The exact target set the OLD hard-coded quality-gate.sh produced, per changed
# path, in the order it emitted them. Reference (pre-WP-23):
#   packages/engine/*     -> run_engine + run_baseline
#   packages/data-app/*   -> run_data   + run_baseline
#   packages/mcp-server/* -> run_mcp
#   research/.../frontend/* -> npm build (matched BEFORE the research prefix)
#   packages/research-app/* -> research tests + backend tests
#   tests/* | tools/baseline/* -> run_baseline
# Emission order in the old script: engine, data, mcp, research(2), frontend,
# baseline. With de-dup, a shared baseline command runs once.
OLD_HARDCODED = {
    "packages/engine/foo.py": [
        "uv run pytest packages/engine/tests -q",
        "uv run pytest tests/test_baseline_regression.py -q",
    ],
    "packages/data-app/bar.py": [
        "uv run pytest packages/data-app/tests -q",
        "uv run pytest tests/test_baseline_regression.py -q",
    ],
    "packages/mcp-server/x.py": [
        "uv run pytest packages/mcp-server/tests -q",
    ],
    "packages/research-app/dashboard/frontend/app.tsx": [
        "npm --prefix packages/research-app/dashboard/frontend run build",
    ],
    "packages/research-app/svc.py": [
        "uv run pytest packages/research-app/tests -q",
        "uv run pytest packages/research-app/dashboard/backend/tests -q",
    ],
    "tests/test_x.py": [
        "uv run pytest tests/test_baseline_regression.py -q",
    ],
    "tools/baseline/gen.py": [
        "uv run pytest tests/test_baseline_regression.py -q",
    ],
}


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """Self-contained git repo = its own main_repo, carrying baofu's QG config."""
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    _git(r, "config", "user.email", "t@e.com")
    _git(r, "config", "user.name", "T")
    sd = r / "scripts" / "agentic"
    sd.mkdir(parents=True)
    (sd / "quality-gate.sh").write_bytes(QG.read_bytes())
    (sd / "quality-gate.sh").chmod(0o755)
    # resolve_paths must be importable as agentic_loop.resolve_paths; the script
    # sets PYTHONPATH to the package src, so we rely on the real package (via
    # PKG_SRC on PYTHONPATH) rather than copying the module in.
    (r / ".agentic").mkdir()
    (r / ".agentic" / "config.toml").write_text(BAOFU_QG_CONFIG, encoding="utf-8")
    (r / "seed.txt").write_text("s\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")
    _git(r, "branch", "-M", "main")
    return r


def _status(repo: Path, allowed, forbidden=None):
    base_c = _git(repo, "rev-parse", "HEAD")
    d = {
        "schema_version": "agentic-wp-status/v1", "work_package_id": "WP-01",
        "iteration_id": "it-1", "phase": "P0", "state": "IMPLEMENTING",
        "role": "Developer", "executor": {"tool": "kimi-cli"},
        "orchestrator": {"tool": "claude-code"}, "reviewer": {"tool": "claude-code"},
        "git": {"base_branch": "main", "base_commit": base_c, "branch": "feat/x",
                "worktree": "."},
        "scope": {"allowed_paths": allowed, "forbidden_paths": forbidden or []},
        "risk": {"production_writes_authorized": False, "network_authorized": False,
                 "real_notifications_authorized": False,
                 "irreversible_actions_authorized": False},
        "evidence": {"tests": []}, "review": {"decision": None}, "timestamps": {},
    }
    f = repo / "docs" / "status.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False))
    return f


def _run_qg(repo: Path, status: Path, *extra):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        ["bash", str(repo / "scripts/agentic/quality-gate.sh"), str(status), *extra],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )


def _plan(stdout: str):
    """Extract the ordered QUALITY_GATE_PLAN: command list from stdout."""
    return [
        line[len("QUALITY_GATE_PLAN:"):].strip()
        for line in stdout.splitlines()
        if line.startswith("QUALITY_GATE_PLAN:")
    ]


def _make_change(repo: Path, rel: str):
    """Create a changed file at `rel` on a feature branch off main."""
    _git(repo, "checkout", "-q", "-b", "feat/x")
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x\n")


def test_no_baofu_literals_in_script():
    """The de-baofu'd wrapper carries zero project-specific path literals."""
    text = QG.read_text(encoding="utf-8")
    assert "packages/data-app" not in text
    assert "packages/engine" not in text
    assert "packages/mcp-server" not in text
    assert "packages/research-app" not in text


@pytest.mark.parametrize("changed_rel,expected", list(OLD_HARDCODED.items()))
def test_config_expansion_equivalent_to_old_hardcoded(repo, changed_rel, expected):
    """Config-driven expansion == the old hard-coded target set, per category.

    Allowed scope is set wide (the whole packages/ + tests/ + tools/ tree) so the
    scope check passes and we observe the pure path->target expansion.
    """
    _make_change(repo, changed_rel)
    status = _status(repo, allowed=["packages/", "tests/", "tools/", "docs/"])
    res = _run_qg(repo, status)
    plan = _plan(res.stdout)
    assert plan == expected, (changed_rel, plan, res.stdout, res.stderr)


def test_full_mode_selects_every_rule_deduped(repo):
    """--full expands to every rule's commands, first-occurrence de-duplicated."""
    _make_change(repo, "packages/engine/z.py")
    status = _status(repo, allowed=["packages/", "tests/", "tools/", "docs/"])
    res = _run_qg(repo, status, "--full")
    plan = _plan(res.stdout)
    expected = [
        "uv run pytest packages/engine/tests -q",
        "uv run pytest tests/test_baseline_regression.py -q",  # deduped: engine+data+tests+tools
        "uv run pytest packages/data-app/tests -q",
        "uv run pytest packages/mcp-server/tests -q",
        "npm --prefix packages/research-app/dashboard/frontend run build",
        "uv run pytest packages/research-app/tests -q",
        "uv run pytest packages/research-app/dashboard/backend/tests -q",
    ]
    assert plan == expected, (plan, res.stdout, res.stderr)


def test_frontend_precedence_over_research(repo):
    """A frontend-only change selects the npm build rule, NOT the research tests
    — proving declaration-order first-match (frontend rule precedes research)."""
    _make_change(repo, "packages/research-app/dashboard/frontend/a.tsx")
    status = _status(repo, allowed=["packages/", "tests/", "tools/", "docs/"])
    res = _run_qg(repo, status)
    plan = _plan(res.stdout)
    assert plan == ["npm --prefix packages/research-app/dashboard/frontend run build"]


def test_docs_only_change_expands_to_no_targets(repo):
    """A change matching no rule expands to an empty plan and still reaches PASS
    (mirrors the old 'no case matched -> nothing runs -> PASS')."""
    _make_change(repo, "docs/note.md")
    status = _status(repo, allowed=["docs/"])
    res = _run_qg(repo, status)
    assert res.returncode == 0, res.stderr
    assert _plan(res.stdout) == []
    assert any(l.strip() == "QUALITY_GATE_RESULT=PASS" for l in res.stdout.splitlines())


# --------------------------------------------------------------------------
# WP-23 rework, finding ②: the rc 4/5 -> skip semantics must apply ONLY to
# pytest commands (mirroring the old run_pytest_dir), not to every command in
# the run loop. A non-pytest command (npm build, a raw shell command, ...) that
# exits 4 or 5 must stay FATAL — the old script never swallowed those.
# --------------------------------------------------------------------------

def _write_config(repo: Path, run_cmds):
    """Overwrite the repo's command-gate config with a single catch-all rule
    whose `run` list is exactly `run_cmds`, so we can drive arbitrary exit codes
    through the execution loop and observe the skip/fatal decision."""
    lines = [
        "[[gate]]",
        'name = "tests"',
        'kind = "command"',
        'stage = "pre_review"',
        "[[gate.rule]]",
        'match = "src/**"',
        "run = [",
    ]
    for c in run_cmds:
        # TOML basic strings share JSON string escaping; json.dumps quotes with
        # double quotes and escapes correctly, leaving the command's inner single
        # quotes intact (a naive repr+replace would corrupt `sh -c 'exit 4'`).
        lines.append("  {},".format(json.dumps(c)))
    lines.append("]")
    (repo / ".agentic" / "config.toml").write_text("\n".join(lines) + "\n",
                                                    encoding="utf-8")


@pytest.mark.parametrize("rc", [4, 5])
def test_pytest_command_rc4_5_still_skips(repo, rc):
    """A pytest command exiting 4 (no target) or 5 (no tests) is still SKIPPED,
    not fatal — the equivalence-preserving behavior for baofu's rule set."""
    # A command that contains 'pytest' but just returns the chosen rc.
    _write_config(repo, ["sh -c 'exit {}'  # pytest".format(rc)])
    _make_change(repo, "src/a.py")
    status = _status(repo, allowed=["src/", "docs/", ".agentic/"])
    res = _run_qg(repo, status)
    assert res.returncode == 0, (rc, res.stdout, res.stderr)
    assert "QUALITY_GATE_SKIP" in res.stdout, (rc, res.stdout, res.stderr)
    assert any(l.strip() == "QUALITY_GATE_RESULT=PASS"
               for l in res.stdout.splitlines()), (rc, res.stdout)


@pytest.mark.parametrize("rc", [4, 5])
def test_non_pytest_command_rc4_5_is_fatal(repo, rc):
    """A NON-pytest command exiting 4 or 5 is FATAL (the finding-② regression
    proof): the gate propagates the exit code instead of silently skipping.

    Uses a command with no 'pytest' token, mimicking `npm ... run build`."""
    _write_config(repo, ["sh -c 'exit {}'  # npm-like build".format(rc)])
    _make_change(repo, "src/a.py")
    status = _status(repo, allowed=["src/", "docs/", ".agentic/"])
    res = _run_qg(repo, status)
    assert res.returncode == rc, (rc, res.returncode, res.stdout, res.stderr)
    assert "QUALITY_GATE_FAIL" in res.stderr, (rc, res.stdout, res.stderr)
    assert "QUALITY_GATE_SKIP" not in res.stdout, (rc, res.stdout, res.stderr)


def test_non_pytest_command_rc0_still_passes(repo):
    """Guard: a non-pytest command that succeeds (rc 0) still passes cleanly, so
    the finding-② fix does not turn legitimate non-pytest successes into failures."""
    _write_config(repo, ["sh -c 'exit 0'  # npm-like build"])
    _make_change(repo, "src/a.py")
    status = _status(repo, allowed=["src/", "docs/", ".agentic/"])
    res = _run_qg(repo, status)
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert any(l.strip() == "QUALITY_GATE_RESULT=PASS"
               for l in res.stdout.splitlines()), res.stdout


# --------------------------------------------------------------------------
# WP-23 rework ROUND 2, finding ② (re-pointed at the unified [[gate]] by WP-01):
# the gate must FAIL-CLOSED when a project's .agentic/config.toml defines no
# usable command gate (kind=command, stage=pre_review) rule list, rather than
# silently reporting PASS on an empty plan.
#
# Discriminator (verified against resolve_paths behavior):
#   * config.toml present but command gate / rule list absent -> FAIL
#     (non-zero exit, QUALITY_GATE_FAIL), NEVER pass on undefined rules.
#   * config.toml present, command gate rules defined, current changed set
#     matches none of them -> legitimate empty plan -> PASS.
#   * no config.toml at all (bare bootstrap) -> keep built-in default behavior,
#     no project config to betray -> PASS (this is the P0 test_quality_gate.py
#     in_scope case, preserved verbatim).
# --------------------------------------------------------------------------

def test_missing_command_gate_fails_closed(repo):
    """finding ② core: a config.toml that OMITS the command gate entirely makes
    the gate refuse (non-zero exit + QUALITY_GATE_FAIL), NOT pass with undefined
    rules."""
    (repo / ".agentic" / "config.toml").write_text(
        '[project]\niterations_dir = "docs/plans"\n', encoding="utf-8"
    )
    _make_change(repo, "docs/a.md")
    status = _status(repo, allowed=["docs/", ".agentic/"])
    res = _run_qg(repo, status)
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "QUALITY_GATE_FAIL" in res.stderr, (res.stdout, res.stderr)
    # Must NOT have emitted the PASS token.
    assert not any(l.strip() == "QUALITY_GATE_RESULT=PASS"
                   for l in res.stdout.splitlines()), res.stdout


def test_empty_command_gate_rule_list_fails_closed(repo):
    """finding ②: a command gate present but with an empty rule list is still
    'no rules defined' -> fail-closed, not pass."""
    (repo / ".agentic" / "config.toml").write_text(
        '[[gate]]\nname = "tests"\nkind = "command"\nstage = "pre_review"\nrule = []\n',
        encoding="utf-8",
    )
    _make_change(repo, "docs/a.md")
    status = _status(repo, allowed=["docs/", ".agentic/"])
    res = _run_qg(repo, status)
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "QUALITY_GATE_FAIL" in res.stderr, (res.stdout, res.stderr)
    assert not any(l.strip() == "QUALITY_GATE_RESULT=PASS"
                   for l in res.stdout.splitlines()), res.stdout


def test_command_gate_present_but_unmatched_is_legitimate_pass(repo):
    """finding ② distinction: a command gate WITH rules whose matches don't hit
    the current changed set is a legitimate empty plan -> PASS. The fail-closed
    refusal must NOT fire here (only absent gate / empty rules do)."""
    _write_config(repo, ["uv run pytest packages/never/tests -q"])  # match src/**
    _make_change(repo, "docs/a.md")  # nothing under src/** changed
    status = _status(repo, allowed=["docs/", ".agentic/"])
    res = _run_qg(repo, status)
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert _plan(res.stdout) == [], (res.stdout, res.stderr)
    assert any(l.strip() == "QUALITY_GATE_RESULT=PASS"
               for l in res.stdout.splitlines()), res.stdout


# --------------------------------------------------------------------------
# An empty plan stays a PASS, but it must be AUDIBLE. A silently-identical
# PASS is what let consumer-repo WP-41 report "the import gate is live" twice
# when the gate had never executed: the WP added the [[gate.rule]] on its own
# branch while this wrapper reads the main-repo config, so nothing matched.
# --------------------------------------------------------------------------

def test_empty_plan_emits_explicit_marker(repo):
    """An empty plan announces itself instead of passing silently."""
    _write_config(repo, ["uv run pytest packages/never/tests -q"])  # match src/**
    _make_change(repo, "docs/a.md")  # nothing under src/** changed
    status = _status(repo, allowed=["docs/", ".agentic/"])
    res = _run_qg(repo, status)
    marker = [l for l in res.stdout.splitlines()
              if l.startswith("QUALITY_GATE_PLAN_EMPTY:")]
    assert len(marker) == 1, (res.stdout, res.stderr)
    # the counts are what distinguish "nothing to do" from "nothing matched"
    assert "1 configured rule(s)" in marker[0], marker[0]
    # and the marker must not be mistakable for evidence that a rule ran
    assert "NOT evidence" in marker[0], marker[0]
    # exit code and PASS are deliberately unchanged
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert any(l.strip() == "QUALITY_GATE_RESULT=PASS"
               for l in res.stdout.splitlines()), res.stdout


def test_non_empty_plan_has_no_empty_marker(repo):
    """The marker must not fire when a rule actually drove a command."""
    _make_change(repo, "packages/engine/z.py")
    status = _status(repo, allowed=["packages/", "tests/", "tools/", "docs/"])
    res = _run_qg(repo, status)
    assert _plan(res.stdout), (res.stdout, res.stderr)
    assert "QUALITY_GATE_PLAN_EMPTY" not in res.stdout, res.stdout


def test_no_config_file_keeps_default_behavior_pass():
    """finding ② boundary: a repo with NO .agentic/config.toml at all is a bare
    bootstrap — no project config to betray — so the built-in default behavior is
    preserved and a docs-only change reaches PASS. Pins that the fail-closed
    discriminator keys on 'config file present but rules undefined', not on the
    mere absence of a config file (which would break P0 test_quality_gate.py's
    in_scope case)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r = Path(td) / "repo"
        r.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=r, check=True)
        _git(r, "config", "user.email", "t@e.com")
        _git(r, "config", "user.name", "T")
        sd = r / "scripts" / "agentic"
        sd.mkdir(parents=True)
        (sd / "quality-gate.sh").write_bytes(QG.read_bytes())
        (sd / "quality-gate.sh").chmod(0o755)
        # NO .agentic/config.toml is created.
        (r / "seed.txt").write_text("s\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "seed")
        _git(r, "branch", "-M", "main")
        _git(r, "checkout", "-q", "-b", "feat/x")
        (r / "docs").mkdir()
        (r / "docs" / "a.md").write_text("a\n")
        status = _status(r, allowed=["docs/"])
        res = _run_qg(r, status)
        assert res.returncode == 0, (res.stdout, res.stderr)
        assert any(l.strip() == "QUALITY_GATE_RESULT=PASS"
                   for l in res.stdout.splitlines()), res.stdout


def test_comment_no_longer_claims_safe_defaults():
    """finding ②: the misleading 'fails closed to its built-in safe defaults'
    comment is gone and replaced with an accurate fail-closed description."""
    text = QG.read_text(encoding="utf-8")
    assert "safe defaults" not in text, "misleading 'safe defaults' comment survives"
    # The accurate fail-closed intent is documented.
    assert "fail-closed" in text.lower() or "fail closed" in text.lower()


# --------------------------------------------------------------------------
# WP-23 rework ROUND 3, Codex three-sign finding: in a LINKED WORKTREE the
# fail-closed guard must resolve .agentic/config.toml from the SAME root the plan
# read uses. The plan read (resolve_paths --config-section) reads main_repo()
# (INV-4: config is a main-repo/iteration concern). The prior guard open-coded
# ${main_root:-$repo_root}; its fallback could read the worktree while the plan
# read main_repo, so the two could diverge. This pins that the guard and the plan
# see the SAME (main_repo) config even when they run from a linked worktree whose
# own .agentic/config.toml differs from main's.
# --------------------------------------------------------------------------

def test_guard_reads_main_repo_config_from_linked_worktree(tmp_path):
    """Round-3: run quality-gate.sh from a linked worktree whose branch-local
    .agentic/config.toml has a DIFFERENT command gate than main. The guard
    must resolve config the same way the plan does — main_repo() — not the
    worktree copy. Here main has a valid rule set and the worktree omits the
    gate entirely; because the guard reads MAIN (which is valid), it must NOT
    fail-closed on the worktree's absent gate."""
    main = tmp_path / "main"
    main.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main, check=True)
    _git(main, "config", "user.email", "t@e.com")
    _git(main, "config", "user.name", "T")
    sd = main / "scripts" / "agentic"
    sd.mkdir(parents=True)
    (sd / "quality-gate.sh").write_bytes(QG.read_bytes())
    (sd / "quality-gate.sh").chmod(0o755)
    # main carries a VALID command-gate rule set.
    (main / ".agentic").mkdir()
    (main / ".agentic" / "config.toml").write_text(BAOFU_QG_CONFIG, encoding="utf-8")
    (main / "seed.txt").write_text("s\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "seed")
    _git(main, "branch", "-M", "main")

    # Create a linked worktree on a feature branch.
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat/x", str(wt), "main")
    # The worktree's own config OMITS the command gate entirely. If the guard read
    # the worktree (the bug), it would wrongly fail-closed; reading main (correct)
    # sees the valid rules and proceeds.
    (wt / ".agentic" / "config.toml").write_text(
        '[project]\niterations_dir = "docs/plans"\n', encoding="utf-8"
    )
    # A docs-only change so the plan (read from main's rules) matches nothing ->
    # legitimate empty-plan PASS. The point is the guard does NOT fail-closed.
    (wt / "docs").mkdir(parents=True, exist_ok=True)
    (wt / "docs" / "a.md").write_text("a\n")

    status = _status(wt, allowed=["docs/", ".agentic/"])
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    res = subprocess.run(
        ["bash", str(wt / "scripts/agentic/quality-gate.sh"), str(status)],
        cwd=str(wt), capture_output=True, text=True, env=env,
    )
    # Guard read main (valid rules) -> no fail-closed; docs-only change -> PASS.
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "QUALITY_GATE_FAIL" not in res.stderr, (res.stdout, res.stderr)
    assert any(l.strip() == "QUALITY_GATE_RESULT=PASS"
               for l in res.stdout.splitlines()), res.stdout

# --------------------------------------------------------------------------
# WP-01: reader reads the unified [[gate]] array + [autonomy] section directly
# (resolve_paths.get_gates / get_command_gate / get_autonomy).
# --------------------------------------------------------------------------

def test_reader_reads_unified_gate_and_autonomy(repo):
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        BAOFU_QG_CONFIG
        + '\n[[gate]]\nname = "qoder_security"\nkind = "qoder_security"\nstage = "merge"\n'
        + '[autonomy]\ndefault_mode = "ask"\n',
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    assert len(gates) == 2

    command_gate = resolve_paths.get_command_gate(repo)
    assert command_gate is not None
    assert command_gate["name"] == "tests"
    assert command_gate["kind"] == "command"
    assert command_gate["stage"] == "pre_review"
    assert command_gate["blocking"] is True
    assert command_gate["enabled"] is True
    assert command_gate["apply"] == "first_match"
    assert [r["match"] for r in command_gate["rule"]] == [
        "packages/engine/**",
        "packages/data-app/**",
        "packages/mcp-server/**",
        "packages/research-app/dashboard/frontend/**",
        "packages/research-app/**",
        "tests/**",
        "tools/baseline/**",
    ]

    qoder = next(g for g in gates if g["kind"] == "qoder_security")
    assert qoder["level"] == "L3"
    assert qoder["stage"] == "merge"

    autonomy = resolve_paths.get_autonomy(repo)
    assert autonomy["default_mode"] == "ask"
    assert autonomy["ultra_auto"] == [
        "local_edit", "test_run", "worktree_lifecycle",
        "dispatch_developer", "review", "merge_gate",
        "local_merge_no_ff", "finalize_merge",
    ]
    assert autonomy["always_stop"] == [
        "push", "feishu_send", "production_write",
        "cron_change", "release_deploy", "credential_rw",
        "irreversible_git",
    ]
    assert autonomy["soft_limit_signals"] == ["frozen_hard", "rework_twice", "circuit_breaker"]


def test_reader_applies_gate_defaults_and_overlay(repo):
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "t"\nkind = "command"\nstage = "pre_review"\n'
        'apply = "overlay"\nblocking = false\n'
        '[[gate.rule]]\nmatch = "skills/**"\nrun = ["x"]\n',
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    assert len(gates) == 1
    g = gates[0]
    assert g["apply"] == "overlay"
    assert g["blocking"] is False
    assert g["enabled"] is True  # default


def test_reader_no_command_gate_returns_none(repo):
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "codex"\nkind = "codex"\nstage = "merge"\neffort = "high"\n',
        encoding="utf-8",
    )
    assert resolve_paths.get_command_gate(repo) is None
    assert [g["kind"] for g in resolve_paths.get_gates(repo)] == ["codex"]


def test_reader_qoder_security_level_default_and_codex_effort(repo):
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "qs"\nkind = "qoder_security"\nstage = "merge"\n'
        '[[gate]]\nname = "cs"\nkind = "codex"\nstage = "merge"\neffort = "high"\n',
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    qs = next(g for g in gates if g["kind"] == "qoder_security")
    assert qs["level"] == "L3"
    cs = next(g for g in gates if g["kind"] == "codex")
    assert cs["effort"] == "high"


# --------------------------------------------------------------------------
# WP-01 rework (Codex two-sign, enum fail-closed): brief Required 1 freezes
# kind/stage/apply as enums. The reader must enforce them — illegal apply falls
# back to first_match (fail-closed), and illegal kind/stage entries are DROPPED
# from get_gates() so they can never reach get_command_gate() or a runner.
# --------------------------------------------------------------------------

def test_invalid_apply_falls_back_to_first_match(repo):
    """apply = "bogus" (non-empty string passes the type check, so it would be
    read through verbatim without the enum guard) must normalize to first_match."""
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "t"\nkind = "command"\nstage = "pre_review"\n'
        'apply = "bogus"\n'
        '[[gate.rule]]\nmatch = "src/**"\nrun = ["x"]\n',
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    assert len(gates) == 1
    assert gates[0]["apply"] == "first_match"
    # The (valid kind/stage) gate is still selectable, with the fail-closed apply.
    cg = resolve_paths.get_command_gate(repo)
    assert cg is not None
    assert cg["apply"] == "first_match"


def test_invalid_kind_entry_is_dropped(repo):
    """An illegal kind is DROPPED (not guessed), so it never appears in
    get_gates() nor get_command_gate()."""
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "bad"\nkind = "bogus"\nstage = "pre_review"\n'
        '[[gate.rule]]\nmatch = "src/**"\nrun = ["x"]\n'
        '[[gate]]\nname = "good"\nkind = "command"\nstage = "pre_review"\n'
        '[[gate.rule]]\nmatch = "src/**"\nrun = ["y"]\n',
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    assert [g["name"] for g in gates] == ["good"]
    assert [g["kind"] for g in gates] == ["command"]
    cg = resolve_paths.get_command_gate(repo)
    assert cg is not None
    assert cg["name"] == "good"


def test_invalid_stage_entry_is_dropped(repo):
    """An illegal stage is DROPPED (not guessed), so it never appears in
    get_gates() nor get_command_gate()."""
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "bad"\nkind = "command"\nstage = "bogus"\n'
        '[[gate.rule]]\nmatch = "src/**"\nrun = ["x"]\n'
        '[[gate]]\nname = "good"\nkind = "command"\nstage = "pre_review"\n'
        '[[gate.rule]]\nmatch = "src/**"\nrun = ["y"]\n',
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    assert [g["name"] for g in gates] == ["good"]
    cg = resolve_paths.get_command_gate(repo)
    assert cg is not None
    assert cg["name"] == "good"


def test_only_invalid_kind_entry_dropped_no_command_gate(repo):
    """A lone illegal-kind gate yields no usable gate and no command gate."""
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "bad"\nkind = "bogus"\nstage = "pre_review"\n',
        encoding="utf-8",
    )
    assert resolve_paths.get_gates(repo) == []
    assert resolve_paths.get_command_gate(repo) is None


def test_only_invalid_stage_entry_dropped_no_command_gate(repo):
    """A lone illegal-stage gate yields no usable gate and no command gate."""
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "bad"\nkind = "command"\nstage = "bogus"\n',
        encoding="utf-8",
    )
    assert resolve_paths.get_gates(repo) == []
    assert resolve_paths.get_command_gate(repo) is None


@pytest.mark.parametrize("kind", ["command", "codex", "qoder_security", "qoder_judge"])
def test_valid_kind_enum_is_preserved(repo, kind):
    """All four legal kind values survive normalization verbatim."""
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "g"\nkind = "{kind}"\nstage = "merge"\n'.format(kind=kind),
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    assert [g["kind"] for g in gates] == [kind]


@pytest.mark.parametrize("stage", ["pre_review", "merge"])
def test_valid_stage_enum_is_preserved(repo, stage):
    """Both legal stage values survive normalization verbatim."""
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "g"\nkind = "command"\nstage = "{stage}"\n'.format(stage=stage),
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    assert [g["stage"] for g in gates] == [stage]


@pytest.mark.parametrize("apply", ["first_match", "overlay"])
def test_valid_apply_enum_is_preserved(repo, apply):
    """Both legal apply values survive normalization verbatim."""
    cfg = repo / ".agentic" / "config.toml"
    cfg.write_text(
        '[[gate]]\nname = "g"\nkind = "command"\nstage = "pre_review"\n'
        'apply = "{apply}"\n'.format(apply=apply),
        encoding="utf-8",
    )
    gates = resolve_paths.get_gates(repo)
    assert gates[0]["apply"] == apply


# --------------------------------------------------------------------------
# §10.1 ②: scope / forbidden-path check (quality-gate.sh).
# --------------------------------------------------------------------------

def test_forbidden_changed_path_fails(repo):
    _make_change(repo, "profiles/secret.toml")
    status = _status(repo, allowed=["profiles/"], forbidden=["profiles/"])
    res = _run_qg(repo, status)
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "forbidden changed path: profiles/secret.toml" in res.stderr, res.stderr


def test_changed_path_outside_allowed_scope_fails(repo):
    _make_change(repo, "docs/note.md")
    status = _status(repo, allowed=["packages/"], forbidden=[])
    res = _run_qg(repo, status)
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "changed path outside allowed scope: docs/note.md" in res.stderr, res.stderr


# --------------------------------------------------------------------------
# §10.1 ③: `git diff --check` three-way (base...HEAD / worktree / cached).
# --------------------------------------------------------------------------

def _commit_tracked(repo: Path, rel: str, content: str):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed {}".format(rel))


def test_diff_check_committed_whitespace_fails(repo):
    _git(repo, "checkout", "-q", "-b", "feat/x")
    p = repo / "packages" / "engine" / "w.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x = 1  \n")  # trailing whitespace
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "bad ws")
    status = _status(repo, allowed=["packages/", "docs/"])
    res = _run_qg(repo, status)
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "trailing whitespace" in res.stdout, res.stdout


def test_diff_check_worktree_whitespace_fails(repo):
    _commit_tracked(repo, "packages/engine/w.py", "x = 1\n")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    (repo / "packages" / "engine" / "w.py").write_text("x = 1  \n")
    status = _status(repo, allowed=["packages/", "docs/"])
    res = _run_qg(repo, status)
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "trailing whitespace" in res.stdout, res.stdout


def test_diff_check_staged_whitespace_fails(repo):
    _commit_tracked(repo, "packages/engine/w.py", "x = 1\n")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    (repo / "packages" / "engine" / "w.py").write_text("x = 1  \n")
    _git(repo, "add", "packages/engine/w.py")
    status = _status(repo, allowed=["packages/", "docs/"])
    res = _run_qg(repo, status)
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "trailing whitespace" in res.stdout, res.stdout


# --------------------------------------------------------------------------
# §10.1 ① (strengthened): a multi-path changed set expands in declaration order
# with global first-occurrence de-dup, and the frontend path is routed to the npm
# build rule (declared BEFORE the broader research rule) even though it lexically
# sits under research-app — the order-sensitive first-match case.
# --------------------------------------------------------------------------

def test_multipath_changed_command_sequence_parity(repo):
    rels = [
        "packages/engine/e.py",
        "packages/research-app/dashboard/frontend/a.tsx",
        "packages/research-app/svc.py",
        "tests/t.py",
    ]
    _git(repo, "checkout", "-q", "-b", "feat/x")
    for rel in rels:
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    status = _status(repo, allowed=["packages/", "tests/", "tools/", "docs/"])
    res = _run_qg(repo, status)
    plan = _plan(res.stdout)
    expected = [
        "uv run pytest packages/engine/tests -q",
        "uv run pytest tests/test_baseline_regression.py -q",
        "npm --prefix packages/research-app/dashboard/frontend run build",
        "uv run pytest packages/research-app/tests -q",
        "uv run pytest packages/research-app/dashboard/backend/tests -q",
    ]
    assert plan == expected, (plan, res.stdout, res.stderr)
