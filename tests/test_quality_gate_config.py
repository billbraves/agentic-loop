"""WP-23: quality-gate.sh reads its path->test rules from the project's
.agentic/config.toml [quality_gate] section instead of hard-coding baofu paths.

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

# baofu's full [quality_gate] rule set (mirrors .agentic/config.toml after WP-23).
BAOFU_QG_CONFIG = """\
[quality_gate]
[[quality_gate.rule]]
match = "packages/engine/**"
run = [
  "uv run pytest packages/engine/tests -q",
  "uv run pytest tests/test_baseline_regression.py -q",
]
[[quality_gate.rule]]
match = "packages/data-app/**"
run = [
  "uv run pytest packages/data-app/tests -q",
  "uv run pytest tests/test_baseline_regression.py -q",
]
[[quality_gate.rule]]
match = "packages/mcp-server/**"
run = ["uv run pytest packages/mcp-server/tests -q"]
[[quality_gate.rule]]
match = "packages/research-app/dashboard/frontend/**"
run = ["npm --prefix packages/research-app/dashboard/frontend run build"]
[[quality_gate.rule]]
match = "packages/research-app/**"
run = [
  "uv run pytest packages/research-app/tests -q",
  "uv run pytest packages/research-app/dashboard/backend/tests -q",
]
[[quality_gate.rule]]
match = "tests/**"
run = ["uv run pytest tests/test_baseline_regression.py -q"]
[[quality_gate.rule]]
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
    """Overwrite the repo's [quality_gate] config with a single catch-all rule
    whose `run` list is exactly `run_cmds`, so we can drive arbitrary exit codes
    through the execution loop and observe the skip/fatal decision."""
    lines = ["[quality_gate]", "[[quality_gate.rule]]", 'match = "src/**"', "run = ["]
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
# WP-23 rework ROUND 2, finding ②: the gate must FAIL-CLOSED when a project's
# .agentic/config.toml defines no usable [quality_gate] rule list, rather than
# silently reporting PASS on an empty plan. The prior comment falsely claimed the
# reader "fails closed to its built-in safe defaults" — it does not; it merges the
# built-in defaults into resolve_paths' output, hiding an absent section, so the
# script would announce QUALITY_GATE_RESULT=PASS with no project-defined rules.
#
# Discriminator (verified against resolve_paths behavior):
#   * config.toml present but [quality_gate] section / rule list absent -> FAIL
#     (non-zero exit, QUALITY_GATE_FAIL), NEVER pass on undefined rules.
#   * config.toml present, [quality_gate] rules defined, current changed set
#     matches none of them -> legitimate empty plan -> PASS.
#   * no config.toml at all (bare bootstrap) -> keep built-in default behavior,
#     no project config to betray -> PASS (this is the P0 test_quality_gate.py
#     in_scope case, preserved verbatim).
# --------------------------------------------------------------------------

def test_missing_quality_gate_section_fails_closed(repo):
    """finding ② core: a config.toml that OMITS [quality_gate] entirely makes the
    gate refuse (non-zero exit + QUALITY_GATE_FAIL), NOT pass with undefined
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


def test_empty_quality_gate_rule_list_fails_closed(repo):
    """finding ②: a [quality_gate] section present but with an empty rule list is
    still 'no rules defined' -> fail-closed, not pass."""
    (repo / ".agentic" / "config.toml").write_text(
        "[quality_gate]\nrule = []\n", encoding="utf-8"
    )
    _make_change(repo, "docs/a.md")
    status = _status(repo, allowed=["docs/", ".agentic/"])
    res = _run_qg(repo, status)
    assert res.returncode != 0, (res.returncode, res.stdout, res.stderr)
    assert "QUALITY_GATE_FAIL" in res.stderr, (res.stdout, res.stderr)
    assert not any(l.strip() == "QUALITY_GATE_RESULT=PASS"
                   for l in res.stdout.splitlines()), res.stdout


def test_section_present_but_unmatched_is_legitimate_pass(repo):
    """finding ② distinction: a [quality_gate] section WITH rules whose matches
    don't hit the current changed set is a legitimate empty plan -> PASS. The
    fail-closed refusal must NOT fire here (only absent section / empty rules do)."""
    _write_config(repo, ["uv run pytest packages/never/tests -q"])  # match src/**
    _make_change(repo, "docs/a.md")  # nothing under src/** changed
    status = _status(repo, allowed=["docs/", ".agentic/"])
    res = _run_qg(repo, status)
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert _plan(res.stdout) == [], (res.stdout, res.stderr)
    assert any(l.strip() == "QUALITY_GATE_RESULT=PASS"
               for l in res.stdout.splitlines()), res.stdout


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
    .agentic/config.toml has DIFFERENT [quality_gate] rules than main. The guard
    must resolve config the same way the plan does — main_repo() — not the
    worktree copy. Here main has a valid rule set and the worktree omits the
    section entirely; because the guard reads MAIN (which is valid), it must NOT
    fail-closed on the worktree's absent section."""
    main = tmp_path / "main"
    main.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main, check=True)
    _git(main, "config", "user.email", "t@e.com")
    _git(main, "config", "user.name", "T")
    sd = main / "scripts" / "agentic"
    sd.mkdir(parents=True)
    (sd / "quality-gate.sh").write_bytes(QG.read_bytes())
    (sd / "quality-gate.sh").chmod(0o755)
    # main carries a VALID [quality_gate] rule set.
    (main / ".agentic").mkdir()
    (main / ".agentic" / "config.toml").write_text(BAOFU_QG_CONFIG, encoding="utf-8")
    (main / "seed.txt").write_text("s\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "seed")
    _git(main, "branch", "-M", "main")

    # Create a linked worktree on a feature branch.
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat/x", str(wt), "main")
    # The worktree's own config OMITS [quality_gate] entirely. If the guard read
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
