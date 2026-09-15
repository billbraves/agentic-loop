"""WP-24 (B10 + B9): both WP brief templates must pass dispatch_lint.sh's
section check, and the oracle three-item rule must be written into the template.

Every test here invokes the REAL bundled ``src/agentic_loop/wrappers/dispatch_lint.sh``
inside a synthetic external git project (the same call shape an ``agentic
preflight`` uses). The predicate is never re-implemented: a copied checker
would test the copy and stay silent when the real one drifts — defect B9's
shape.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
DISPATCH_LINT = SRC / "agentic_loop" / "wrappers" / "dispatch_lint.sh"
TEMPLATE_PACKAGED = SRC / "agentic_loop" / "templates" / "WORK_PACKAGE.md.tmpl"
TEMPLATE_DOCS = REPO_ROOT / "docs" / "agentic" / "templates" / "WORK_PACKAGE.md"
REAL_BRIEF = (
    REPO_ROOT / "docs" / "plans" / "2026-09-13-parallel-throughput" / "WP-22-brief.md"
)

# Status JSON shape reused from tests/test_cli.py's external-consumer fixture;
# dispatch_lint.sh runs validate_wp_status on it before the section check.
STATUS = {
    "schema_version": "agentic-wp-status/v1",
    "work_package_id": "WP-01",
    "iteration_id": "it-1",
    "phase": "P0",
    "state": "APPROVED",
    "role": "Developer",
    "executor": {"tool": "kimi-cli"},
    "orchestrator": {"tool": "claude-code"},
    "reviewer": {"tool": "claude-code"},
    "git": {
        "base_branch": "main",
        "base_commit": "0" * 7,
        "branch": "feat/x",
        "worktree": "wt",
    },
    "scope": {"allowed_paths": ["docs/"], "forbidden_paths": []},
    "risk": {
        "production_writes_authorized": False,
        "network_authorized": False,
        "real_notifications_authorized": False,
        "irreversible_actions_authorized": False,
    },
    "evidence": {"tests": []},
    "review": {"decision": None},
    "timestamps": {},
}


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def lint_project(tmp_path):
    """A synthetic external git project with docs/plans/it-1/ seeded.

    No scripts/agentic/ and no .agentic/config.toml: iterations_dir falls back
    to the built-in default (docs/plans), so the real dispatch_lint.sh resolves
    the brief at docs/plans/it-1/WP-01-brief.md exactly as in production.
    """
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    _git(proj, "config", "user.email", "t@t")
    _git(proj, "config", "user.name", "t")
    iterdir = proj / "docs" / "plans" / "it-1"
    iterdir.mkdir(parents=True)
    (iterdir / "WP-01.status.json").write_text(
        json.dumps(STATUS, ensure_ascii=False), encoding="utf-8"
    )
    _git(proj, "add", "-A")
    _git(proj, "commit", "-qm", "seed")
    return proj, iterdir


def _run_dispatch_lint(proj, iteration_id="it-1", work_package_id="WP-01"):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["AGENTIC_PYTHON"] = sys.executable
    rel = f"docs/plans/{iteration_id}/{work_package_id}.status.json"
    return subprocess.run(
        ["bash", str(DISPATCH_LINT), rel],
        cwd=str(proj),
        env=env,
        capture_output=True,
        text=True,
    )


def _write_brief(iterdir, text, work_package_id="WP-01"):
    (iterdir / f"{work_package_id}-brief.md").write_text(text, encoding="utf-8")


def _clear_section_body(text, heading):
    """Keep the ``## <heading>`` line, drop every line until the next ``## ``."""
    lines = text.splitlines(keepends=True)
    out = []
    skipping = False
    for line in lines:
        if skipping:
            if line.startswith("## "):
                skipping = False
            else:
                continue
        out.append(line)
        if line.rstrip("\n") == f"## {heading}":
            skipping = True
    return "".join(out)


@pytest.mark.parametrize(
    "template",
    [TEMPLATE_PACKAGED, TEMPLATE_DOCS],
    ids=["packaged-tmpl", "docs-template"],
)
def test_templates_pass_dispatch_lint_section_check(lint_project, template):
    """B10 failing-to-passing: both templates yield DISPATCH_LINT_PASS."""
    proj, iterdir = lint_project
    _write_brief(iterdir, template.read_text(encoding="utf-8"))
    r = _run_dispatch_lint(proj)
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "DISPATCH_LINT_PASS" in r.stdout, (r.stdout, r.stderr)


def test_templates_byte_identical():
    """The two templates must stay byte-identical (guards one-sided drift:
    init_cmd.py re-scaffolds the docs/ copy from the .tmpl master)."""
    assert TEMPLATE_PACKAGED.read_bytes() == TEMPLATE_DOCS.read_bytes()


def test_positive_control_real_brief_ok(lint_project):
    """Positive reachability control: a known-compliant real brief (WP-22,
    actually dispatched) must also yield PASS in this exact call shape —
    proving the checker is not vacuously true here."""
    assert REAL_BRIEF.is_file(), REAL_BRIEF
    proj, _iterdir = lint_project
    real_iter = REAL_BRIEF.parent.name
    real_wp = REAL_BRIEF.name[: -len("-brief.md")]
    real_dir = proj / "docs" / "plans" / real_iter
    real_dir.mkdir(parents=True, exist_ok=True)
    _write_brief(real_dir, REAL_BRIEF.read_text(encoding="utf-8"), real_wp)
    (real_dir / f"{real_wp}.status.json").write_text(
        json.dumps({**STATUS, "iteration_id": real_iter,
                    "work_package_id": real_wp}, ensure_ascii=False),
        encoding="utf-8",
    )
    r = _run_dispatch_lint(proj, iteration_id=real_iter, work_package_id=real_wp)
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "DISPATCH_LINT_PASS" in r.stdout, (r.stdout, r.stderr)


def test_witness_empty_anchor_body_fails(lint_project):
    """Cause-specific witness for the section-body predicate: clearing the
    body of ``## Acceptance tests`` (heading kept) must still go red through
    the real script — the non-empty half of the predicate is separately alive,
    independent of the heading half."""
    proj, iterdir = lint_project
    _write_brief(
        iterdir, _clear_section_body(TEMPLATE_DOCS.read_text(encoding="utf-8"),
                                     "Acceptance tests")
    )
    r = _run_dispatch_lint(proj)
    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)
    assert "Acceptance tests" in r.stderr, r.stderr


def test_forbidden_mutation_renamed_anchor_fails(lint_project):
    """Representative forbidden mutation: renaming the anchor heading
    (``## Acceptance tests`` -> ``## 验收测试``) must go red with the
    checker reporting the section as missing."""
    proj, iterdir = lint_project
    mutated = TEMPLATE_DOCS.read_text(encoding="utf-8").replace(
        "## Acceptance tests", "## 验收测试", 1
    )
    assert "## 验收测试" in mutated
    _write_brief(iterdir, mutated)
    r = _run_dispatch_lint(proj)
    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)
    assert "missing section 'Acceptance tests'" in r.stderr, r.stderr


def test_template_carries_oracle_three_items():
    """The oracle three-item rule is written into the template's own
    Acceptance tests section (template-level inheritance, B9 fix)."""
    text = TEMPLATE_PACKAGED.read_text(encoding="utf-8")
    anchor = re.search(r"^## Acceptance tests\s*$", text, re.MULTILINE)
    assert anchor, "template lost the ## Acceptance tests anchor"
    rest = text[anchor.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[: nxt.start()] if nxt else rest
    assert "正向可达性对照" in section
    assert "原因特异 witness" in section
    assert "禁止变异" in section and "转红" in section
    assert "不能互相替代" in section
