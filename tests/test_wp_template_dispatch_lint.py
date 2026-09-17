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
import unicodedata
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
    """Cause-specific witness for the section-body predicate at
    ``src/agentic_loop/wrappers/dispatch_lint.sh:98``, via a DIFFERENTIAL PAIR.

    The script's two failure paths — heading missing (:86) and heading present
    but body empty (:98) — print the SAME ``brief missing section`` line, so
    stderr wording cannot identify which path fired (defect B11; codex's
    ``empty``/``missing`` suggestion is unreachable).  We therefore hold
    EVERYTHING constant and vary only the one thing the predicate checks: the
    body of ``## Acceptance tests``.

    Variant A = ``_clear_section_body(tmpl, "Acceptance tests")``: heading
    kept, body cleared.  Variant B = the SAME bytes with exactly one line
    ``x`` inserted under that heading.  Both fixtures contain the heading —
    asserted explicitly below — so the heading check at ``dispatch_lint.sh:86``
    cannot fire in EITHER run, by construction rather than by assumption.
    Variant B passes (oracle item 1: positive reachability control on the
    same fixture) and variant A goes red; the only difference between the two
    runs is that one body line, so A's red can only come from the body-
    emptiness check at ``dispatch_lint.sh:98`` (oracle item 2).  The ``:86``
    half is covered separately by ``test_forbidden_mutation_renamed_anchor_fails``
    (oracle item 3).
    """
    proj, iterdir = lint_project
    heading = "## Acceptance tests"
    cleared = _clear_section_body(TEMPLATE_DOCS.read_text(encoding="utf-8"),
                                  "Acceptance tests")

    # Heading check (dispatch_lint.sh:86) excluded BY CONSTRUCTION in both
    # variants — this must hold no matter how the fixture evolves.
    assert heading in cleared
    variant_a = cleared
    variant_b = cleared.replace(f"{heading}\n", f"{heading}\nx\n", 1)
    assert variant_b != variant_a, "fixture must gain exactly one body line"
    assert heading in variant_b

    # Variant B (body non-empty): positive control — same fixture, same
    # script, must pass.  Proves the check is reachable and not vacuous.
    _write_brief(iterdir, variant_b)
    rb = _run_dispatch_lint(proj)
    assert rb.returncode == 0, (rb.returncode, rb.stdout, rb.stderr)
    assert "DISPATCH_LINT_PASS" in rb.stdout, (rb.stdout, rb.stderr)

    # Variant A (body empty): same fixture minus that one line must go red.
    # Weak aux only — NOT a cause-specific witness (both paths print the
    # same line; B11).  The cause specificity lives in the differential pair.
    _write_brief(iterdir, variant_a)
    ra = _run_dispatch_lint(proj)
    assert ra.returncode != 0, (ra.returncode, ra.stdout, ra.stderr)
    assert "Acceptance tests" in ra.stderr, ra.stderr


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


# =====================================================================
# WP-28 INV-N: the two orchestration norms must be mechanically pin-able
# in the WP brief template.  The predicate below checks six surfaces
# (S1..S6); the mutation set is generated from those composition steps
# (oracle item 4), NOT from a defect-number checklist.  Frozen constants
# are literal text so any weakening stays visible in this file's diff.
# =====================================================================

SECTION_RE_FREEZE = "## Re-freeze 规则（编排者冻结前自检）"
SECTION_ACCEPTANCE = "## Acceptance tests"

# S5 处境: the exact non-empty line that must sit immediately before each block.
PRE_LINE_RE_FREEZE = (
    "> 冻结后执行期间不得修改；需修订走 re-freeze（规则见「Re-freeze 规则」一节）。"
)
PRE_LINE_ACCEPTANCE = "> 内容与上文中文章节同义，非另一份口径。"

# S2 内容: frozen content fragments (whitespace-normalized) that must appear in
# each block.
RE_FREEZE_FRAGMENTS = [
    "第 3 次**及以后** re-freeze",
    "冻结前必须停手复核计划",
    "未经用户批准不得冻结",
    "验收标的必须写成**不变式**",
    "台账编号只作破口清单",
    "不得取代不变式成为标的。",
]
ACCEPTANCE_FRAGMENTS = [
    "按判据自身的组成步骤生成",
    "不得按已知缺陷清单枚举",
    "某步骤不可攻击须在报告里写明理由",
]

# S3 极性: the exact polarity-bearing clauses whose weakening (必须→可以 /
# 不得→建议不) must go red.
POLARITY_CLAUSES = {
    SECTION_RE_FREEZE: ["冻结前必须停手"],
    SECTION_ACCEPTANCE: ["不得按已知缺陷清单枚举"],
}

# S4 结构: list-item lines that must not be indented >=4 spaces and must stay
# contiguous (not split by a blank line).
STRUCTURAL_LINES = {
    SECTION_RE_FREEZE: [
        "- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。",
        "- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。",
    ],
    SECTION_ACCEPTANCE: [
        "4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，",
        "不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。",
    ],
}


def _normalize_ws(text):
    return " ".join(text.split())


def _section_block(text, title):
    """Return the full section (heading + body through the blank line before
    the next ``## `` heading) as a string ending with a newline."""
    start = text.index(title)
    nxt = text.index("\n## ", start + len(title))
    return text[start:nxt] + "\n"


def _inv_n_violations(text):
    """Return a list of INV-N violations; empty list means the template is clean.

    S1 定位 — each title exactly once; S2 内容 — frozen fragments present in
    the block; S3 极性 — polarity clauses verbatim; S4 结构 — list lines not
    indented >=4 nor blank-split; S5 处境 — frozen preceding line; S6 同形 —
    no homoglyph/HTML-comment decoy copy before the block.
    """
    violations = []
    lines = text.splitlines()

    # S1 定位：两个标题各须恰好出现 1 次。
    for title in (SECTION_RE_FREEZE, SECTION_ACCEPTANCE):
        count = sum(1 for ln in lines if ln.rstrip() == title)
        if count != 1:
            violations.append(
                f"边界不唯一：'{title}' 应恰好出现 1 次，实际 {count} 次"
            )

    # Build block bodies (canonical = first exact heading occurrence).
    blocks = {}
    for title in (SECTION_RE_FREEZE, SECTION_ACCEPTANCE):
        idx = next((i for i, ln in enumerate(lines) if ln.rstrip() == title), None)
        if idx is None:
            blocks[title] = (None, "")
            continue
        body_lines = []
        for ln in lines[idx + 1:]:
            if ln.startswith("## "):
                break
            body_lines.append(ln)
        blocks[title] = (idx, "\n".join(body_lines))

    # S2 内容：冻结常量逐字出现在对应块内（归一化空白）。
    for title, fragments in (
        (SECTION_RE_FREEZE, RE_FREEZE_FRAGMENTS),
        (SECTION_ACCEPTANCE, ACCEPTANCE_FRAGMENTS),
    ):
        norm_body = _normalize_ws(blocks[title][1])
        for frag in fragments:
            if _normalize_ws(frag) not in norm_body:
                violations.append(f"内容缺失：'{frag}' 不在 {title} 块内")

    # S3 极性：承载极性的分句必须原样出现。
    for title, clauses in POLARITY_CLAUSES.items():
        norm_body = _normalize_ws(blocks[title][1])
        for clause in clauses:
            if _normalize_ws(clause) not in norm_body:
                violations.append(f"极性改写：'{clause}' 未按原样出现于 {title} 块")

    # S4 结构：冻结分句所在行不得缩进 >=4，不得被空行断开所属列表。
    for title, structs in STRUCTURAL_LINES.items():
        for struct in structs:
            for ln in lines:
                if ln.lstrip() == struct and len(ln) - len(ln.lstrip()) >= 4:
                    violations.append(f"结构破坏：'{struct}' 被缩进≥4 空格")
                    break
        body_lines = blocks[title][1].splitlines()
        positions = [
            j for j, ln in enumerate(body_lines)
            if ln.lstrip() in {s.lstrip() for s in structs}
        ]
        for a, b in zip(positions, positions[1:]):
            if any(x.strip() == "" for x in body_lines[a + 1:b]):
                violations.append(f"结构破坏：{title} 块内列表被空行断开")
                break

    # S5 处境：每块紧邻前一非空行必须等于冻结文本。
    prev_line = {
        SECTION_RE_FREEZE: PRE_LINE_RE_FREEZE,
        SECTION_ACCEPTANCE: PRE_LINE_ACCEPTANCE,
    }
    for title, expected in prev_line.items():
        idx = blocks[title][0]
        if idx is None:
            continue
        prev = None
        for j in range(idx - 1, -1, -1):
            if lines[j].strip() != "":
                prev = lines[j].rstrip()
                break
        if prev != expected:
            violations.append(f"处境污染：'{title}' 前紧邻行不是冻结文本")

    # S6 同形：块前不得存在同形完好副本（Unicode 同形字 / HTML 注释包裹）。
    for title in (SECTION_RE_FREEZE, SECTION_ACCEPTANCE):
        idx = blocks[title][0]
        if idx is None:
            continue
        target = unicodedata.normalize("NFKC", title)
        for j in range(idx):
            norm = unicodedata.normalize("NFKC", lines[j].strip())
            if norm == target:
                violations.append(f"同形副本：'{title}' 块前存在同形副本")
                break
            if norm.startswith("<!--") and norm.endswith("-->"):
                inner = norm[len("<!--"):-len("-->")].strip()
                if inner == target:
                    violations.append(
                        f"同形副本：'{title}' 块前存在同形副本（HTML 注释包裹）"
                    )
                    break

    return violations


def _clean_template_text():
    return TEMPLATE_PACKAGED.read_text(encoding="utf-8")


# --- oracle item 1: positive reachability control on the real template ---


def test_invn_positive_control_clean_template():
    """The un-mutated real template must produce zero INV-N violations."""
    assert _inv_n_violations(_clean_template_text()) == []


# --- oracle item 3: one representative forbidden mutation per surface (S1..S6),
# each asserting a cause-specific witness whose wording is distinct per surface.


def test_invn_s1_position_duplicate_block_red():
    """S1 定位：insert an intact copy of the Re-freeze block before the
    canonical one -> the title no longer occurs exactly once."""
    text = _clean_template_text()
    block = _section_block(text, SECTION_RE_FREEZE)
    mutated = text.replace(SECTION_RE_FREEZE, block + SECTION_RE_FREEZE, 1)
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any("边界不唯一" in v for v in violations), violations


def test_invn_s2_content_deleted_red():
    """S2 内容：delete one frozen fragment -> the block no longer carries it."""
    text = _clean_template_text()
    fragment = "不得取代不变式成为标的。"
    mutated = text.replace(fragment, "", 1)
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any(
        "内容缺失" in v and "不得取代不变式成为标的。" in v for v in violations
    ), violations


def test_invn_s3_polarity_weakened_refreeze_red():
    """S3 极性：必须→可以 on the re-freeze stop clause must go red."""
    text = _clean_template_text()
    mutated = text.replace("冻结前必须停手", "冻结前可以停手", 1)
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any(
        "极性改写" in v and "冻结前必须停手" in v for v in violations
    ), violations


def test_invn_s3_polarity_weakened_acceptance_red():
    """S3 极性：不得→建议不 on the mutation-generation clause must go red."""
    text = _clean_template_text()
    mutated = text.replace("不得按已知缺陷清单枚举", "建议不按已知缺陷清单枚举", 1)
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any(
        "极性改写" in v and "不得按已知缺陷清单枚举" in v for v in violations
    ), violations


def test_invn_s4_indent_code_block_red():
    """S4 结构：indenting a frozen list line >=4 spaces turns it into a code
    block and must go red."""
    text = _clean_template_text()
    line = "- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。"
    mutated = text.replace(line, "      " + line, 1)
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any("结构破坏" in v for v in violations), violations


def test_invn_s4_blank_line_split_red():
    """S4 结构：a blank line inserted inside the re-freeze list must go red."""
    text = _clean_template_text()
    line = "- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。"
    mutated = text.replace(line, "\n" + line, 1)
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any("结构破坏" in v for v in violations), violations


def test_invn_s5_denorm_sentence_refreeze_red():
    """S5 处境：inserting a de-norming sentence right before the Re-freeze
    block must go red."""
    text = _clean_template_text()
    mutated = text.replace(
        SECTION_RE_FREEZE,
        "以下仅为历史示例，不具规范约束力：\n" + SECTION_RE_FREEZE,
        1,
    )
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any(
        "处境污染" in v and "Re-freeze" in v for v in violations
    ), violations


def test_invn_s5_denorm_sentence_acceptance_red():
    """S5 处境：the same-shaped context attack on the Acceptance tests block
    must go red."""
    text = _clean_template_text()
    mutated = text.replace(
        SECTION_ACCEPTANCE,
        "以下仅为历史示例，不具规范约束力：\n" + SECTION_ACCEPTANCE,
        1,
    )
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any(
        "处境污染" in v and "Acceptance tests" in v for v in violations
    ), violations


def test_invn_s6_homoglyph_decoy_red():
    """S6 同形：a Unicode full-width homoglyph decoy title before the block
    (invisible to the S1 exact-match count) must go red."""
    text = _clean_template_text()
    homoglyph_title = SECTION_RE_FREEZE.replace("Re-freeze", "Ｒｅ-freeze")
    mutated = text.replace(
        SECTION_RE_FREEZE,
        homoglyph_title + "\n\n" + SECTION_RE_FREEZE,
        1,
    )
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any("同形副本" in v for v in violations), violations


def test_invn_s6_html_comment_wrap_red():
    """S6 同形：an HTML-comment-wrapped copy of the title before the block
    must go red (escape pin, not enumerated in the brief's floor)."""
    text = _clean_template_text()
    wrapped = "<!-- " + SECTION_RE_FREEZE + " -->"
    mutated = text.replace(
        SECTION_RE_FREEZE,
        wrapped + "\n\n" + SECTION_RE_FREEZE,
        1,
    )
    assert mutated != text
    violations = _inv_n_violations(mutated)
    assert any("同形副本" in v for v in violations), violations


# --- oracle item 1 (harmless probes): two non-weakening edits must stay green.


def test_invn_harmless_probe_rewrap_green():
    """H1：moving item 4's line break (no character change) must stay green."""
    text = _clean_template_text()
    old = (
        "4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，\n"
        "   不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。"
    )
    new = (
        "4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成\n"
        "   ，不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。"
    )
    assert old in text
    mutated = text.replace(old, new, 1)
    assert mutated != text
    assert _inv_n_violations(mutated) == []


def test_invn_harmless_probe_unrelated_edit_green():
    """H2：editing an unrelated placeholder outside the two blocks must stay
    green."""
    text = _clean_template_text()
    mutated = text.replace("<这个 WP 要交付什么>", "<这个 WP 交付一个用例>", 1)
    assert mutated != text
    assert _inv_n_violations(mutated) == []
