"""WP-24 (B10 + B9): both WP brief templates must pass dispatch_lint.sh's
section check, and the oracle three-item rule must be written into the template.

Every test here invokes the REAL bundled ``src/agentic_loop/wrappers/dispatch_lint.sh``
inside a synthetic external git project (the same call shape an ``agentic
preflight`` uses). The predicate is never re-implemented: a copied checker
would test the copy and stay silent when the real one drifts — defect B9's
shape.

WP-28 (rev3) INV-N boundary — 本判据只保证冻结块的 文件字节 身份、唯一性与声明的
位置锚点不变。它不保证：

1. 块外编辑不改变其 Markdown 渲染上下文。编排者已实测三条现成逃逸：整份文档外包
   ``<!-- … -->``、文档开头留未闭合 ``<!--``、在 ``## 附注`` 内开一个未闭合代码围栏 ——
   三者两块 body 均逐字节完好，判据 GREEN。
2. 文档远处不存在去规范化或矛盾条款。已实测逃逸：在文档最开头加
   「下列所有流程规则均已废止，仅供历史参考。」→ 判据 GREEN。
3. 任意渲染器把它显示为活动文本；实际消费者一定采纳这份模板；
   所有「语义等价的削弱」都会被识别；规范一定被人或 agent 遵守。
"""

import json
import os
import re
import subprocess
import sys
import unicodedata
from contextlib import contextmanager
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
# WP-28 rev3 INV-N: the two orchestration norms must be mechanically
# pin-able in the WP brief template.  The criterion below is a set of
# independent hard invariants (T1/T2/T3/T4/T6/T7); any single failure
# turns the test red.  S2/S3/S4/S7 are downgraded to *diagnostic* codes
# that are only computed after a T4 BODY_MISMATCH, and they never decide
# pass/fail.  Frozen constants are literal text (not sha256) so any
# weakening stays visible in this file's diff (INV-N4).
# =====================================================================

SECTION_RE_FREEZE = "## Re-freeze 规则（编排者冻结前自检）"
SECTION_ACCEPTANCE = "## Acceptance tests"

# Frozen block bodies: byte-for-byte text from the heading's terminating
# newline up to (and excluding) the next ``## `` heading line.  These are
# literal so a change to a protected byte requires a visible diff here.
FROZEN_BODY_RE_FREEZE = (
    "\n"
    "- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。\n"
    "- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。\n"
    "\n"
)

FROZEN_BODY_ACCEPTANCE = (
    "\n"
    "本段与上文「交付物清单」「完成定义（DoD）」中的验收测试要求同义，非另一份口径。\n"
    "\n"
    "每一份 WP 的每条负面断言都必须提供 oracle 校验四项证据：\n"
    "\n"
    "1. **正向可达性对照**：在同一 fixture 上做一次不带注入/变异的正向运行，\n"
    "   必须到达终点，证明前置条件确实可达终点。\n"
    "2. **原因特异 witness**：负向运行必须给出原因特异的 witness（异常标记、\n"
    "   状态或精确事件），证明失败被正确归因。\n"
    "3. **代表性禁止变异转红**：至少一个代表性禁止变异（如改掉锚点标题、\n"
    "   删去关键守卫）必须使测试转红。\n"
    "4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，\n"
    "   不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。变异必须施加于判据\n"
    "   真实的输入面（文件字节 / 进程边界 / 外部状态），不得只改判据已持有的内存表示。\n"
    "   判别方式：把被修的缺陷还原成原状，该用例必须转红；仍绿则该用例不承重。\n"
    "\n"
    "注意：第 1 项证明「前置可达」，第 2 项证明「失败归因」，\n"
    "**两者不能互相替代**——「无注入时能到终点」并不排除「带注入时死在别处」。\n"
    "\n"
)

FROZEN_BODY = {
    SECTION_RE_FREEZE: FROZEN_BODY_RE_FREEZE,
    SECTION_ACCEPTANCE: FROZEN_BODY_ACCEPTANCE,
}

# Position anchors: the immediately preceding / following ``## `` heading
# line (full content).  The first H2 block's previous anchor is ``<BOF>``.
ANCHORS = {
    SECTION_RE_FREEZE: ("<BOF>", "## 目标（一句话）"),
    SECTION_ACCEPTANCE: ("## 附注", "## Allowed and forbidden paths"),
}

# --- Hard witness codes (decide red) ---------------------------------
SECTION_MISSING = "SECTION_MISSING"
SECTION_NOT_UNIQUE = "SECTION_NOT_UNIQUE"
SECTION_HOMOGLYPH_DUPLICATE = "SECTION_HOMOGLYPH_DUPLICATE"
BODY_MISMATCH = "BODY_MISMATCH"
SECTION_BODY_TRUNCATED = "SECTION_BODY_TRUNCATED"
SECTION_ANCHOR_MOVED = "SECTION_ANCHOR_MOVED"
REPLICA_MISMATCH = "REPLICA_MISMATCH"

HARD_CODES = {
    SECTION_MISSING,
    SECTION_NOT_UNIQUE,
    SECTION_HOMOGLYPH_DUPLICATE,
    BODY_MISMATCH,
    SECTION_BODY_TRUNCATED,
    SECTION_ANCHOR_MOVED,
    REPLICA_MISMATCH,
}

# --- Diagnostic codes (downgraded S2/S3/S4/S7; never decide pass/fail) --
BODY_CLAUSE_MISSING = "BODY_CLAUSE_MISSING"
BODY_POLARITY_CHANGED = "BODY_POLARITY_CHANGED"
BODY_INDENT_CODEBLOCK = "BODY_INDENT_CODEBLOCK"
BODY_LIST_SPLIT = "BODY_LIST_SPLIT"
BODY_QUANTITY_PHRASE_CHANGED = "BODY_QUANTITY_PHRASE_CHANGED"

DIAGNOSTIC_CODES = {
    BODY_CLAUSE_MISSING,
    BODY_POLARITY_CHANGED,
    BODY_INDENT_CODEBLOCK,
    BODY_LIST_SPLIT,
    BODY_QUANTITY_PHRASE_CHANGED,
}

# Byte-exact fragments used ONLY for post-BODY_MISMATCH attribution.
CLAUSE_FRAGMENTS = {
    SECTION_RE_FREEZE: [
        "第 3 次**及以后** re-freeze",
        "未经用户批准不得冻结",
        "验收标的必须写成**不变式**",
        "台账编号只作破口清单",
        "不得取代不变式成为标的。",
    ],
    SECTION_ACCEPTANCE: [
        "按判据自身的组成步骤生成",
        "某步骤不可攻击须在报告里写明理由",
    ],
}

POLARITY_CLAUSES = {
    SECTION_RE_FREEZE: ["冻结前必须停手"],
    SECTION_ACCEPTANCE: ["不得按已知缺陷清单枚举"],
}

STRUCTURAL_LINES = {
    SECTION_RE_FREEZE: [
        "- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。",
        "- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。",
    ],
    SECTION_ACCEPTANCE: [
        "1. **正向可达性对照**：在同一 fixture 上做一次不带注入/变异的正向运行，",
        "4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，",
    ],
}

QUANTITY_PHRASES = {
    SECTION_ACCEPTANCE: ["四项"],
}


def _heading_line_matches(text, title):
    """All byte-exact occurrences of ``title`` as a whole line (T1 surface)."""
    return list(re.finditer(r"(?m)^" + re.escape(title) + r"$", text))


def _h2_line_matches(text):
    """All ``## `` heading lines, full line content captured (T2/T3/T6 surface)."""
    return list(re.finditer(r"(?m)^## [^\n]*$", text))


def _extract_body(text, heading_end, h2_matches):
    """Body = text right after the heading's newline, up to the next ``## `` line."""
    body_start = heading_end + 1
    for match in h2_matches:
        if match.start() >= body_start:
            return text[body_start:match.start()]
    return text[body_start:]


def _anchors_for(heading_match, h2_matches):
    """Return (prev_anchor, next_anchor) for a heading match, using ``<BOF>``/``<EOF>``."""
    idx = next(
        i for i, m in enumerate(h2_matches) if m.start() == heading_match.start()
    )
    prev_anchor = h2_matches[idx - 1].group(0) if idx > 0 else "<BOF>"
    next_anchor = h2_matches[idx + 1].group(0) if idx + 1 < len(h2_matches) else "<EOF>"
    return prev_anchor, next_anchor


def _classify_body_diff(title, actual):
    """Downgraded S2/S3/S4/S7 attribution.  Never runs unless T4 already fired."""
    codes = set()
    for frag in CLAUSE_FRAGMENTS.get(title, []):
        if frag not in actual:
            codes.add(BODY_CLAUSE_MISSING)
    for clause in POLARITY_CLAUSES.get(title, []):
        if clause not in actual:
            codes.add(BODY_POLARITY_CHANGED)
    for phrase in QUANTITY_PHRASES.get(title, []):
        if phrase not in actual:
            codes.add(BODY_QUANTITY_PHRASE_CHANGED)

    structs = STRUCTURAL_LINES.get(title, [])
    body_lines = actual.splitlines()
    for ln in body_lines:
        stripped = ln.lstrip()
        if stripped in structs and len(ln) - len(stripped) >= 4:
            codes.add(BODY_INDENT_CODEBLOCK)
    positions = [i for i, ln in enumerate(body_lines) if ln.lstrip() in structs]
    for a, b in zip(positions, positions[1:]):
        if any(body_lines[j].strip() == "" for j in range(a + 1, b)):
            codes.add(BODY_LIST_SPLIT)
    return codes


def _inv_n_codes(text):
    """Run the independent hard invariants for one template's text.

    Returns a set of witness codes.  Hard codes decide red; diagnostic codes
    are computed only after a BODY_MISMATCH and never decide pass/fail.
    """
    codes = set()
    h2 = _h2_line_matches(text)
    for title in (SECTION_RE_FREEZE, SECTION_ACCEPTANCE):
        exact = _heading_line_matches(text, title)
        frozen_body = FROZEN_BODY[title]
        prev_frozen, next_frozen = ANCHORS[title]

        # T1 — unique byte-exact location.
        if not exact:
            codes.add(SECTION_MISSING)
        elif len(exact) > 1:
            codes.add(SECTION_NOT_UNIQUE)

        # T2 — NFKC-equal but byte-different ``## `` heading line.
        nfkc_title = unicodedata.normalize("NFKC", title)
        for m in h2:
            line = m.group(0)
            if line != title and unicodedata.normalize("NFKC", line) == nfkc_title:
                codes.add(SECTION_HOMOGLYPH_DUPLICATE)

        if exact:
            # T3/T4 — body sliced at the next ``## `` line, byte-exact.
            body = _extract_body(text, exact[0].end(), h2)
            if body != frozen_body:
                codes.add(BODY_MISMATCH)
                # T3 — the block boundary was moved INTO the body (e.g. a new
                # ``## `` line): the sliced body is a strict prefix of the
                # frozen body, distinguishable from a mid-body clause deletion.
                if frozen_body.startswith(body):
                    codes.add(SECTION_BODY_TRUNCATED)
                # T5 fallback attribution (diagnostic only).
                codes.update(_classify_body_diff(title, body))

            # T6 — position anchors.
            prev_anchor, next_anchor = _anchors_for(exact[0], h2)
            if prev_anchor != prev_frozen or next_anchor != next_frozen:
                codes.add(SECTION_ANCHOR_MOVED)

    return codes


def _check_both(packaged_text, docs_text):
    """Check both templates and add REPLICA_MISMATCH if they differ (T7)."""
    codes = _inv_n_codes(packaged_text) | _inv_n_codes(docs_text)
    if packaged_text != docs_text:
        codes.add(REPLICA_MISMATCH)
    return codes


def _read_text_preserving_newlines(path):
    """Read a template's text with newline translation DISABLED (B49).

    ``Path.read_text()`` runs universal-newline translation, folding ``CRLF``
    into ``LF`` before the frozen-byte comparison ever sees it.  A byte-level
    change to line endings therefore passes silently.  The criterion's input
    must be the file's actual bytes decoded without newline translation, so
    ``\\r\\n`` and ``\\n`` remain distinguishable.  ``open(..., newline="")``
    is the "decode but keep newline translation off" route (A.4 option 2); it
    keeps the frozen constants as ``str`` literals while making the bytes the
    source of truth.
    """
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _mutate_both(mutate):
    """Apply ``mutate`` to BOTH templates and return the combined witness codes.

    T1–T6 mutations must apply identically to both replicas (so T7 stays the
    only step that examines replica identity).  The no-op guard below is the
    uniform ``变异后 != 变异前`` assertion for every mutation function.
    """
    packaged = _read_text_preserving_newlines(TEMPLATE_PACKAGED)
    docs = _read_text_preserving_newlines(TEMPLATE_DOCS)
    assert packaged == docs, "both templates must be byte-identical before mutation"
    mutated_packaged = mutate(packaged)
    mutated_docs = mutate(docs)
    assert mutated_packaged != packaged, "mutation must change the text (no-op guard)"
    assert mutated_docs != docs, "mutation must change the text (no-op guard)"
    assert mutated_packaged == mutated_docs, (
        "T1–T6 mutations must apply identically to both templates"
    )
    return _check_both(mutated_packaged, mutated_docs)


@contextmanager
def _mutate_on_disk(paths, mutate_bytes):
    """Temporarily write mutated BYTES to real template files, then restore.

    This is the M-T0 / M-T0b carrier.  The mutation is applied to the file's
    bytes, so the criterion's read path (``_read_text_preserving_newlines``)
    is the ONLY thing between the mutated bytes and the witness codes.  A
    read-path regression (e.g. back to ``Path.read_text``) therefore flips
    the result — which is exactly what makes these cases kill their own fix.

    The no-op guard compares bytes (``mutated != original``), and ``finally``
    restores every touched file and asserts the restore is byte-exact, so a
    passing or failing test can never leave a dirty template behind.
    """
    originals = {p: p.read_bytes() for p in paths}
    mutated = {p: mutate_bytes(data) for p, data in originals.items()}
    for p, data in mutated.items():
        assert data != originals[p], f"mutation must change bytes (no-op guard): {p}"
        p.write_bytes(data)
    try:
        yield
    finally:
        for p, data in originals.items():
            p.write_bytes(data)
            assert p.read_bytes() == data, f"restore must be byte-exact: {p}"


def _crlf_rewrap_bytes(data):
    """Normalize then rewrap line endings so an already-CRLF file never becomes
    ``\\r\\r\\n``: ``b"\\r\\n" -> b"\\n"`` first, then ``b"\\n" -> b"\\r\\n"``."""
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


# ---------------------------------------------------------------------
# Positive control: the real templates carry exactly the frozen blocks.
# ---------------------------------------------------------------------
def test_invn_positive_control_clean_template():
    packaged = _read_text_preserving_newlines(TEMPLATE_PACKAGED)
    docs = _read_text_preserving_newlines(TEMPLATE_DOCS)
    assert packaged == docs, "both templates must be byte-identical"
    codes = _check_both(packaged, docs)
    assert codes == set(), f"clean template must produce no witness codes, got {codes}"


# ---------------------------------------------------------------------
# T0 — input fidelity: the criterion's input must be the file's bytes.
# ---------------------------------------------------------------------
def test_invn_t0_crlf_rewrap_both_red():
    """M-T0: re-encoding BOTH template FILES' bytes LF->CRLF (no character
    change, frozen constants untouched) must go red, with SECTION_MISSING as
    the specific witness and NO REPLICA_MISMATCH (both replicas stay
    identical).  The mutation is written to disk and the criterion reads the
    files itself, so a read-path regression flips this case red."""
    with _mutate_on_disk([TEMPLATE_PACKAGED, TEMPLATE_DOCS], _crlf_rewrap_bytes):
        packaged = _read_text_preserving_newlines(TEMPLATE_PACKAGED)
        docs = _read_text_preserving_newlines(TEMPLATE_DOCS)
        codes = _check_both(packaged, docs)
    assert SECTION_MISSING in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t0b_crlf_rewrap_one_side_red():
    """M-T0b: mutating only ONE replica FILE's line-ending bytes must surface
    as BOTH REPLICA_MISMATCH (T7) and SECTION_MISSING (T0/T1), proving M-T0's
    red comes from T0/T1 — not from replica identity."""
    with _mutate_on_disk([TEMPLATE_PACKAGED], _crlf_rewrap_bytes):
        packaged = _read_text_preserving_newlines(TEMPLATE_PACKAGED)
        docs = _read_text_preserving_newlines(TEMPLATE_DOCS)
        codes = _check_both(packaged, docs)
    assert REPLICA_MISMATCH in codes, codes
    assert SECTION_MISSING in codes, codes


# ---------------------------------------------------------------------
# T1 — unique location.
# ---------------------------------------------------------------------
def test_invn_t1_duplicate_heading_red():
    """An intact extra copy of the heading must break unique location."""

    def mutate(text):
        return text + "\n" + SECTION_RE_FREEZE + "\n"

    codes = _mutate_both(mutate)
    assert SECTION_NOT_UNIQUE in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t1_renamed_heading_red():
    """Renaming the heading must break location (section missing)."""

    def mutate(text):
        return text.replace(
            SECTION_RE_FREEZE, "## Re-freeze 规则（执行者自检）", 1
        )

    codes = _mutate_both(mutate)
    assert SECTION_MISSING in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


# ---------------------------------------------------------------------
# T2 — NFKC homoglyph duplicate.
# ---------------------------------------------------------------------
def test_invn_t2_homoglyph_duplicate_red():
    """A byte-different but NFKC-equal ``## `` line must be flagged."""

    def mutate(text):
        homoglyph = SECTION_RE_FREEZE.replace("（编排者冻结前自检）", "(编排者冻结前自检)")
        assert homoglyph != SECTION_RE_FREEZE
        return text + "\n" + homoglyph + "\n"

    codes = _mutate_both(mutate)
    assert SECTION_HOMOGLYPH_DUPLICATE in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


# ---------------------------------------------------------------------
# T3 — body slicing at the next ``## `` line.
# ---------------------------------------------------------------------
def test_invn_t3_body_slicing_truncated_red():
    """Inserting a ``## `` line inside the block truncates the sliced body."""

    def mutate(text):
        assert "未经用户批准不得冻结。\n" in text
        return text.replace(
            "未经用户批准不得冻结。\n",
            "未经用户批准不得冻结。\n## 截断线\n",
            1,
        )

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert SECTION_BODY_TRUNCATED in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t3_neg_clause_deleted_not_truncated():
    """Negative control for SECTION_BODY_TRUNCATED: a mid-body clause deletion
    is a T4 edit, not a boundary move, so it must NOT carry the T3 code."""

    def mutate(text):
        assert "台账编号只作破口清单，" in text
        return text.replace("台账编号只作破口清单，", "", 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert SECTION_BODY_TRUNCATED not in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


# ---------------------------------------------------------------------
# T4 — byte-exact body equality (no whitespace folding).
# ---------------------------------------------------------------------
def test_invn_t4_clause_deleted_red():
    def mutate(text):
        assert "不得取代不变式成为标的。" in text
        return text.replace("不得取代不变式成为标的。", "", 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert BODY_CLAUSE_MISSING in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t4_polarity_must_to_may_red():
    def mutate(text):
        assert "冻结前必须停手" in text
        return text.replace("冻结前必须停手", "冻结前可以停手", 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert BODY_POLARITY_CHANGED in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t4_polarity_must_not_to_advise_red():
    def mutate(text):
        assert "不得按已知缺陷清单枚举" in text
        return text.replace("不得按已知缺陷清单枚举", "建议不按已知缺陷清单枚举", 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert BODY_POLARITY_CHANGED in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t4_indent_codeblock_red():
    def mutate(text):
        line = "- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。"
        assert line in text
        return text.replace(line, "      " + line, 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert BODY_INDENT_CODEBLOCK in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t4_blank_line_split_red():
    def mutate(text):
        assert "未经用户批准不得冻结。\n" in text
        return text.replace(
            "未经用户批准不得冻结。\n",
            "未经用户批准不得冻结。\n\n",
            1,
        )

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert BODY_LIST_SPLIT in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t4_quantity_four_to_three_red():
    def mutate(text):
        assert "四项" in text
        return text.replace("四项", "三项", 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert BODY_QUANTITY_PHRASE_CHANGED in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t4_pure_rewrap_red():
    """Moving a line break without changing any character must still go red."""

    def mutate(text):
        old = (
            "4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，\n"
            "   不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。"
        )
        new = (
            "4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，不得按已知缺陷清单枚举；\n"
            "   某步骤不可攻击须在报告里写明理由。"
        )
        assert old in text
        return text.replace(old, new, 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert not (codes & DIAGNOSTIC_CODES), f"pure rewrap is unclassifiable, got {codes}"
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t4_hard_break_red():
    def mutate(text):
        line = "   不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。"
        assert line in text
        return text.replace(line, line + "  ", 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert not (codes & DIAGNOSTIC_CODES), f"hard break is unclassifiable, got {codes}"
    assert REPLICA_MISMATCH not in codes, codes


# ---------------------------------------------------------------------
# T5 — fallback: BODY_MISMATCH alone must be sufficient (no diagnostic).
# ---------------------------------------------------------------------
def test_invn_t5_append_prose_fallback_red():
    def mutate(text):
        assert "不得取代不变式成为标的。\n" in text
        return text.replace(
            "不得取代不变式成为标的。\n",
            "不得取代不变式成为标的。\n这是一段追加的散文。\n",
            1,
        )

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert not (codes & DIAGNOSTIC_CODES), f"append prose must fall back, got {codes}"
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t5_reorder_list_fallback_red():
    def mutate(text):
        first = "- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。"
        second = "- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。"
        assert first in text and second in text
        return text.replace(first + "\n" + second, second + "\n" + first, 1)

    codes = _mutate_both(mutate)
    assert BODY_MISMATCH in codes, codes
    assert not (codes & DIAGNOSTIC_CODES), f"reorder must fall back, got {codes}"
    assert REPLICA_MISMATCH not in codes, codes


# ---------------------------------------------------------------------
# T6 — position anchors.
# ---------------------------------------------------------------------
def test_invn_t6_block_moved_red():
    """Moving the whole block (body untouched) must break its anchors."""

    def mutate(text):
        section = SECTION_RE_FREEZE + "\n" + FROZEN_BODY_RE_FREEZE
        assert section in text
        without = text.replace(section, "", 1)
        return without + "\n" + section

    codes = _mutate_both(mutate)
    assert SECTION_ANCHOR_MOVED in codes, codes
    assert BODY_MISMATCH not in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


def test_invn_t6_insert_section_before_red():
    def mutate(text):
        assert "## Acceptance tests" in text
        return text.replace(
            "## Acceptance tests",
            "## 新的无关章节\n\n这是新章节正文。\n\n## Acceptance tests",
            1,
        )

    codes = _mutate_both(mutate)
    assert SECTION_ANCHOR_MOVED in codes, codes
    assert REPLICA_MISMATCH not in codes, codes


# ---------------------------------------------------------------------
# T7 — replica identity.
# ---------------------------------------------------------------------
def test_invn_t7_replica_mismatch_red():
    packaged = TEMPLATE_PACKAGED.read_text(encoding="utf-8")
    docs = TEMPLATE_DOCS.read_text(encoding="utf-8")
    assert packaged == docs
    mutated_packaged = packaged.replace(
        "<这个 WP 要交付什么>", "<这个 WP 要交付的内容>", 1
    )
    assert mutated_packaged != packaged
    codes = _check_both(mutated_packaged, docs)
    assert codes == {REPLICA_MISMATCH}, codes


# ---------------------------------------------------------------------
# Harmless probes — edits outside the protected blocks must stay green.
# ---------------------------------------------------------------------
def test_invn_harmless_placeholder_edit_green():
    def mutate(text):
        assert "<这个 WP 要交付什么>" in text
        return text.replace("<这个 WP 要交付什么>", "<这个 WP 交付一个用例>", 1)

    codes = _mutate_both(mutate)
    assert not (codes & HARD_CODES), codes


def test_invn_harmless_append_unrelated_section_green():
    def mutate(text):
        return text + "\n## 无关新章节\n\n这是无关内容。\n"

    codes = _mutate_both(mutate)
    assert not (codes & HARD_CODES), codes


def test_invn_harmless_scope_edit_green():
    def mutate(text):
        assert "- **allowed_paths**（白名单，只能改这些）：" in text
        return text.replace(
            "- **allowed_paths**（白名单，只能改这些）：",
            "- **allowed_paths**（白名单，只能改这些文件）：",
            1,
        )

    codes = _mutate_both(mutate)
    assert not (codes & HARD_CODES), codes


def test_invn_harmless_freeze_date_edit_green():
    def mutate(text):
        assert "> 冻结日期 <YYYY-MM-DD>" in text
        return text.replace(
            "> 冻结日期 <YYYY-MM-DD>", "> 冻结日期 2026-09-18", 1
        )

    codes = _mutate_both(mutate)
    assert not (codes & HARD_CODES), codes
