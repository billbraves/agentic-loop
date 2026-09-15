# WP-24: 让 WP Brief 模板过自己的 gate，并把 oracle 校验三项写进通用 DoD（B10 + B9）

> 冻结日期 2026-09-15 | 编排者 claude（claude-code） | 执行者 kimi。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev2 并重派）。

## 目标（一句话）

两份 WP Brief 模板母本缺 `dispatch_lint.sh` 自己要求的三个英文锚点，照模板写的
brief 必然在 `agentic preflight` 挂掉；补齐锚点，并把 B9 的「oracle 校验三项」
写进模板的 `Acceptance tests` 段成为通用要求。

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

`dispatch_lint.sh:66-104` 要求每份 brief 含三个 `## ` **精确匹配**锚点，且每段
**至少一行非空非注释内容**，否则 `fail "brief missing section '<X>'"`：

```
Acceptance tests / Allowed and forbidden paths / Completion definition
```

用该脚本同一段判据（原样抄出的 Python）实测：

| 文件 | 角色 | 结果 |
|------|------|------|
| `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` | 打包母本（`init_cmd.py:109` 铺开来源） | `FAIL missing 'Acceptance tests'` |
| `docs/agentic/templates/WORK_PACKAGE.md` | 项目内骨架（与母本 `diff` 为空） | `FAIL missing 'Acceptance tests'` |
| `WP-22-brief.md` | **正面对照**（真实派发过） | `OK` |
| `WP-21-brief-rev2.md` | **正面对照** | `OK` |
| 模板 + 三个空锚点 | **witness** | `FAIL empty 'Acceptance tests'`（非 `missing`） |

> 后两行是刻意加的：只有负面结果的判据可能是空验证（缺陷 B9/A35 同族）。
> 正面对照证明 checker 在合规文件上会说 `OK`；witness 证明第二段「段内非空」
> 判据也活着，报的不是同一个 `missing`。

**两份模板 `diff` 为空**，且 `init_cmd.py:109` 从 `.tmpl` 铺开 →
**只改 `docs/` 那份会在下次 `agentic init` 被覆盖回不合规状态**，必须同改。

**历史残留可证后果**：`WP-20-brief.md`（三个锚点全缺）、`WP-19-brief-rev2.md`
（缺两个）留在仓里——锚点历来靠「挨一次 lint 再手工补」，而记性会失效。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`（打包母本）
  - `docs/agentic/templates/WORK_PACKAGE.md`（项目内骨架，须与母本保持 `diff` 为空）
  - `tests/test_wp_template_dispatch_lint.py`（新建）
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/wrappers/dispatch_lint.sh`（**判据本身正确，零改动**；
    模板去适配 gate，不是让 gate 放宽去适配模板）
  - `src/agentic_loop/init_cmd.py`（铺开映射已正确，零改动）
  - `src/agentic_loop/templates/` 下**其余全部** `.tmpl`
  - `src/agentic_loop/validate_wp_status.py`、`src/agentic_loop/gate/__init__.py`
  - `src/agentic_loop/wrappers/` 下其余全部 `.sh`
  - `docs/plans/`（brief 与 status 由编排者维护；**含本 brief 自身**）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

> ⚠️ **方向不可反**：修的是模板，不是 gate。把 `dispatch_lint.sh` 的三个锚点
> 要求删掉或放宽以「让模板通过」是错解，会被直接驳回。

## 交付物清单

- [ ] 两份模板各补三个英文锚点段（`## Acceptance tests` /
      `## Allowed and forbidden paths` / `## Completion definition`），每段非空。
- [ ] 锚点段须**显式标注为中文段的同义锚点**，不得造出第二份可执行口径（§5.3）。
      沿用 `WP-19-brief.md:147-149` 已确立的写法作为参照：
      > 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
      > 内容与上文中文章节同义，非另一份口径。
- [ ] `Acceptance tests` 段写入 **B9 的 oracle 校验三项**，作为模板级通用要求
      （措辞可优化，语义三项不得少）：
      1. 同 fixture 的**正向可达性对照**——证明前置条件确实能到达终点
      2. 负向运行的**原因特异 witness**——异常标记、状态或精确事件，证明失败归因
      3. 至少一个**代表性禁止变异必须使测试转红**
      并注明：第 1 项证明「前置可达」，第 2 项证明「失败归因」，
      **两者不能互相替代**（「无注入时能到终点」不排除「带注入时死在别处」）。
- [ ] 两份模板改完 `diff` 仍为空（同一份内容，两处落地）。
- [ ] `tests/test_wp_template_dispatch_lint.py`：
      - **两份**模板各自喂 `dispatch_lint.sh` 的 section 检查得 `OK`
      - **两份模板 `diff` 为空**的断言（防日后单边漂移）
      - **正面对照**：一份已知合规的真实 brief 同样得 `OK`
        （证明 checker 在本测试的调用形态下确实会说 OK，而非恒真）
      - **witness**：把模板副本的某个锚点内容清空 → 断言报的是 `empty`
        而**不是** `missing`（证明两段判据分别活着）
      - **禁止变异**：把模板副本的一个锚点标题改掉（如 `## Acceptance tests` →
        `## 验收测试`）→ 断言变红且报 `missing`
- [ ] **不要**把 checker 的 Python 逻辑抄进测试。测试须**实际调用**
      `dispatch_lint.sh` 或从该脚本读取判据，否则测的是副本、模板漂移时不会报警
      （这正是 B9「观测通道选错」的形态）。若技术上必须复制，须在报告
      `[CONCERNS]` 里说明为何无法直接调用，并说明漂移风险。

## 完成定义（DoD）

- [ ] 交付物逐项就绪；B10 有一个失败→通过的测试
- [ ] `dispatch_lint.sh` diff **必须为 0 行**
- [ ] `init_cmd.py` diff **必须为 0 行**
- [ ] 两份模板 `diff` 为空（有断言锁住）
- [ ] **跨版本**：新测试在 **python3.11、3.13、3.14** 三个解释器全绿
      （缺 pytest 的用 `uv run --python <ver> --with pytest --no-project python -m pytest <file> -q`）
- [ ] `tests/test_init_contract.py::test_init_scaffolds_reference_templates`
      **照旧通过**（铺开路径未被破坏的证据）
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线**零回归**
      （基线由编排者在派发时写入 status；那 4 个
      `tests/test_finalize_merge_triple_sign.py` 预存失败**不要修**）
- [ ] 按缺陷 B7：直接跑工作树代码，**不要**用 `agentic quality-gate` 自证
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 不 merge、不 push、不切生产分支
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **两份必须同改**。`init_cmd.py:109` 从 `.tmpl` 铺开，单改 `docs/` 那份会被
   下次 `agentic init` 覆盖回不合规状态。
2. **不要改 gate**。方向是模板适配 gate。删/放宽 `dispatch_lint.sh` 的锚点要求
   是错解。
3. **不要造第二份口径**。英文锚点段必须显式声明与中文段同义（§5.3）。
   把中文段删掉、只留英文，也是错解——那会改变模板的既有语言规范（全局 §0）。
4. **测试不要抄判据**。抄一份 checker 进测试 = 测副本，模板漂移时不报警。
   直接调 `dispatch_lint.sh`（可造最小 fixture 让它走到 section 检查那一步），
   或从脚本原文提取判据。
5. **不要顺手补 `WP-20-brief.md` / `WP-19-brief-rev2.md`**。它们在
   `docs/plans/`，是 forbidden path，且属编排者维护面。看到了在
   `[CONCERNS]` 申报，不要动手。
6. **oracle 三项是写进模板文本，不是写进代码**。本 WP 不实现任何 oracle 检查器，
   只让模板要求执行者提供这三项证据。
7. **`set -euo pipefail` 下的读取一律要守卫**（缺陷 A12 的来历）。

### 口径权威源引用

- brief 锚点判据：`src/agentic_loop/wrappers/dispatch_lint.sh:66-104`（唯一权威，本轮只读）
- 模板铺开映射：`src/agentic_loop/init_cmd.py:103-112`（唯一权威，本轮只读）
- 主仓根解析：`resolve_paths --root main_repo`（既有唯一权威，不另造）
- 范围校验：`quality-gate.sh` 的 `_path_in_scope`（既有唯一权威，不另造）
- oracle 校验三项出处：`WP-08-candidate.md` §B9（codex 2026-09-15 第二轮咨询 P2-3）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` — packaged master template
- `docs/agentic/templates/WORK_PACKAGE.md` — scaffolded skeleton; must stay
  byte-identical to the packaged master
- `tests/test_wp_template_dispatch_lint.py` (new)

**forbidden_paths**

- `src/agentic_loop/wrappers/dispatch_lint.sh` — the checker is correct;
  **zero-line diff**. The template adapts to the gate, never the reverse
- `src/agentic_loop/init_cmd.py` — scaffolding map already correct; zero-line diff
- every other `.tmpl` under `src/agentic_loop/templates/`
- `src/agentic_loop/validate_wp_status.py`, `src/agentic_loop/gate/__init__.py`
- every other `.sh` under `src/agentic_loop/wrappers/`
- `docs/plans/` — briefs and status files are orchestrator-maintained
  (including this brief)
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7: it runs another
repository's snapshot).

- `tests/test_wp_template_dispatch_lint.py` — B10:
  - both templates pass `dispatch_lint.sh`'s section check with `OK`
  - the two templates are byte-identical (guards against one-sided drift)
  - **positive control**: a known-compliant real brief also yields `OK`, proving
    the checker is not vacuously true in this call shape
  - **witness**: emptying one anchor's body in a template copy must report
    `empty`, not `missing` — the two halves of the predicate are separately alive
  - **forbidden mutation**: renaming an anchor heading (e.g.
    `## Acceptance tests` → `## 验收测试`) must go red with `missing`
- The test must **invoke `dispatch_lint.sh`** (or read the predicate from that
  script), never re-implement its Python. A copied predicate tests the copy and
  stays silent when the real one drifts — that is defect B9's shape.
- `tests/test_init_contract.py::test_init_scaffolds_reference_templates` still
  passes (evidence the scaffolding path is intact).
- **Cross-version**: the new test is green under python3.11, 3.13 and 3.14.
- Whole suite: `PYTHONPATH=src python3.11 -m pytest tests -q`, zero regression
  against the baseline recorded in the status JSON at dispatch time. The 4
  pre-existing `tests/test_finalize_merge_triple_sign.py` failures stay exactly
  as they are — **do not fix them**.

### Oracle checks required of every negative assertion (new template-level rule)

This WP writes the following three requirements into the template's own
`Acceptance tests` section, so future work packages inherit them:

1. A **positive reachability control** on the same fixture, proving the
   precondition can in fact reach the end state.
2. A **cause-specific witness** on the negative run — an exception marker,
   state, or precise event proving the failure was attributed correctly.
3. At least one **representative forbidden mutation that turns the test red**.

Items 1 and 2 are not interchangeable: "reaches the end state without the
injection" does not rule out "dies somewhere else with the injection."

## Completion definition

- [ ] Every deliverable in place; B10 has one failing-to-passing test
- [ ] `dispatch_lint.sh` diff is **zero lines**
- [ ] `init_cmd.py` diff is **zero lines**
- [ ] The two templates are byte-identical, asserted by a test
- [ ] The English anchor sections are explicitly declared synonymous with the
      Chinese sections — no second executable definition (rule §5.3)
- [ ] All three interpreters (3.11, 3.13, 3.14) green on the new test
- [ ] Zero regression relative to the recorded baseline
- [ ] No writes to forbidden_paths, no cross-owner writes
- [ ] No production writes, no network, no notifications, no pushes
- [ ] No merge, no push, no switching to a production branch
- [ ] Commit message follows the repository convention
