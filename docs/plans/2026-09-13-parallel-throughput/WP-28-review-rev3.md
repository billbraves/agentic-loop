# WP-28 rev3 独立复核

> 复核者 claude-code（编排者兼独立复核者）| 复核日期 2026-09-18
> 被复核对象：`feature/wp28-norms-into-template` @ `2ba5ef5`
> 判据冻结输入：`WP-28-brief-rev3.md`（sha256 `c14782edaea217d8fbbaa5617a414c9f32a0740dab10ff144a1f6e58e48b69df`，复核时重算一致）

## 裁定

**ACCEPT。**

理由概述：rev3 的收缩把承诺从开放世界的「任何削弱规范力」降到三条可机械兑现的闭合不变式
（INV-N1 受保护块身份 / INV-N3 副本同一 / INV-N4 变更可见性），判据实现与该承诺严格对齐；
我自撰的 9 条探针（执行者未见过）全部落在预期一侧，0 意外逃逸；三条已声明的不保证在模块
docstring 里逐条写明，绿是承诺边界外的绿，不是漏防。

## 1. 范围核验（不信报告，逐条复跑）

```text
$ git diff --name-only 7a30f50..2ba5ef5
docs/agentic/templates/WORK_PACKAGE.md
src/agentic_loop/templates/WORK_PACKAGE.md.tmpl
tests/test_wp_template_dispatch_lint.py
```

三个文件全部落在 rev3 brief 的 `allowed_paths` 内，无 forbidden_paths 命中。

```text
$ git diff --exit-code b34deb9..2ba5ef5 -- src/agentic_loop/templates/ docs/agentic/templates/
（零 diff）TEMPLATES_UNCHANGED_SINCE_b34deb9
$ grep -n 'CONTRACT_TEMPLATE_VERSION' src/agentic_loop/contract_render.py
25:CONTRACT_TEMPLATE_VERSION = "6"     ← 未 bump，符合硬约束
$ git diff --exit-code 7a30f50..2ba5ef5 -- pyproject.toml
（零 diff）DEPS_UNCHANGED               ← 未引入 Markdown parser
$ git status --porcelain
（空）
```

本轮 diff 只含 `tests/test_wp_template_dispatch_lint.py`（+517/−301）。

## 2. 测试证据（编排者复跑）

| 命令 | 结果 | exit | 出处 |
|---|---|---|---|
| `PYTHONPATH=src python3.11 -m pytest tests/test_wp_template_dispatch_lint.py -q` | 29 passed | 0 | 编排者复跑 |
| `PYTHONPATH=src python3.11 -m pytest tests -q` | 4 failed, 628 passed, 4 skipped | 1 | 编排者复跑 |
| 3.13 / 3.14 targeted | 各 29 passed | 0 | 执行者报告，未复跑 |

4 条 failed 逐条核对，全在 `tests/test_finalize_merge_triple_sign.py`（`test_v3_triple_sign_pass_finalizes`、
`test_v3_qoder_override_approved_finalizes_record_preserved`、`test_v3_missing_qoder_block_rejected`、
`test_v2_without_qoder_finalizes_double_sign`），是本机 `git checkout -q main` 的既有环境失败，
该文件本轮未触碰，按 brief 指令不修。

**基线差 9 的算术**：`628 − 619 = 9 = 29 − 20`（rev3 判据 29 条 − rev1 的 20 条）。
失败集与跳过集与基线完全一致，故零回归成立。这与 WP-29 侧的 606-vs-619（B48，我自己的
brief 缺陷）是两件互不相关的事：此处是同 lane 内新增用例的正常抬升。

## 3. 判据形状核验（对齐 codex 咨询结论）

- **无空白折叠**：`grep '_normalize_ws\|\.split())\|" ".join('` 零命中。T4 用真逐字节相等，
  符合咨询意见「不能把所有 whitespace 无条件折叠后称为等值冻结」。
- **硬/诊断分离**：`_inv_n_codes()` 里四条硬不变式独立运行，任一失败即红；
  `_classify_body_diff()` 只在 `BODY_MISMATCH` 之后跑，且诊断 code 从不参与放行。
- **结构化 witness**：`SECTION_MISSING` / `SECTION_NOT_UNIQUE` / `SECTION_HOMOGLYPH_DUPLICATE` /
  `SECTION_ANCHOR_MOVED` / `BODY_MISMATCH` / `REPLICA_MISMATCH` + 4 个诊断 code，
  不依赖 `violations[0]` 的执行顺序。
- **兜底真承重**：4 条变异（`pure_rewrap`、`hard_break`、`append_prose`、`reorder_list`）
  同时断言 `BODY_MISMATCH in codes` 且 `not (codes & DIAGNOSTIC_CODES)`——分类缺失时兜底扛住。
  DoD 只要求 ≥2 条，实到 4 条。
- **空操作守卫**：21 条变异全部经 `_mutate_both()`，其中含
  `assert mutated != original`（两份各一次）与「两份模板同步施加」的断言；
  T7 走内联 guard，是唯一考察副本同一的步骤。逐函数核过，无一绕过。
- **极性反转已入变异集**：rev2 把「纯折行」当无害探针，rev3 已按 §B 移入变异集并转红
  （`test_invn_t4_pure_rewrap_red`），符合 brief 的极性反转要求。

## 4. 编排者自撰探针（执行者未见过的 9 条）

直接调判据的 `_check_both()`，不经用例：

| 探针 | 结果 | 预期 | 判定 |
|---|---|---|---|
| P1 整份文档外包 `<!-- … -->` | GREEN codes=[] | GREEN（承诺边界外） | ✅ |
| P2 文档顶部远距离去规范化句 | GREEN codes=[] | GREEN（承诺边界外） | ✅ |
| P3 `## 附注` 内未闭合围栏 | GREEN codes=[] | GREEN（承诺边界外） | ✅ |
| P4 块内插零宽空格 U+200B | RED `BODY_MISMATCH` | RED | ✅ |
| P5 块内行尾加空格 | RED `BODY_MISMATCH` | RED | ✅ |
| P6 块体换成语义等价改写 | RED 4 codes | RED | ✅ |
| P7 只攻击 re-freeze 一块 | RED `BODY_MISMATCH`+`BODY_POLARITY_CHANGED` | RED | ✅ |
| P8 文末追加受保护块副本 | RED `SECTION_NOT_UNIQUE` | RED | ✅ |
| P9 块内空格换 NBSP | RED `BODY_MISMATCH` | RED | ✅ |

9/9 与预期一致。**P1–P3 的绿不是缺陷**：它们正是模块 docstring 已逐条声明的三条不保证，
落在 rev3 承诺边界之外——这也是 WP-29 存在的理由。

## 5. INV-N4（变更可见性）

`FROZEN_BODY` 是测试内的冻结常量。任何受保护字节的改动若不同步改这个常量，判据即红；
要让判据变绿，必须在 `tests/` 里留下可审查 diff。这就是 INV-N4 承诺的全部——
测试能强迫变更「可见」，不能证明变更「已获批准」，此点 docstring 未越界宣称。

## 6. 遗留（不阻断本 WP）

- **B48**（我自己的缺陷，非本 WP）：WP-29 brief 的零回归基线写成 619，那是 WP-28 lane 的数，
  WP-29 的 base `2e5f2c0` 实测 606。已在 WP-29 复核中单列。
- **B47**（既有）：`dispatch_lint.sh` 按固定命名读 brief，忽略 `evidence.brief.path`，
  revN brief 从未真正过段落门禁。本 WP 的 brief 是 rev3，因此它「过了 dispatch_lint」这件事
  在机制上并不成立——但这不影响本轮判据实现的正确性，另 WP 处理（任务 #38）。

---

## 附录：本判定已被撤回（2026-09-18，第二签名后）

上文的 `ACCEPT` **不再有效**。codex 第二签名判 `REWORK`，报两个阻断项，编排者已逐条独立复现：

| ID | 阻断项 | 复现结果 |
|----|--------|----------|
| B49 | 判据用 `read_text()` 取输入，Python universal-newline 把 `CRLF` 归一化为 `LF`。两份模板同步 `LF`→`CRLF`：受保护字节已变、冻结常量未改、判据返回 `[]`（GREEN）；保留换行字节则返回 `['SECTION_MISSING']`。 | REPRODUCED |
| B50 | T3（块体切分）无步骤特异 witness。实测 `T3=[BODY_CLAUSE_MISSING, BODY_MISMATCH, SECTION_ANCHOR_MOVED]`、`T4=[BODY_CLAUSE_MISSING, BODY_MISMATCH]`、`T5=[BODY_MISMATCH]` —— 三个 code 分属诊断分类、T4/T5 兜底、T6，无一特异表示「块体被新 `## ` 截断」。 | REPRODUCED |

B49 直接击穿本 WP 的核心承诺：INV-N1 的「完整 body 与冻结常量逐字节相等」与 INV-N4 的
「任何受保护字节变化必须在测试 oracle 留下可审查 diff」。一次跨平台的行尾转换（Windows
检出、编辑器改 EOL、`.gitattributes` 调整）就能让整段冻结文字失效而判据全绿。

B50 违反 rev3 brief:180-181 与 DoD:238「§B 七类步骤各有至少一条转红变异，结构化 code
互不相同」。

### 为什么我自己的复核没抓到

两项都落在我未覆盖的维度，且都不是「测得不够多」而是「测的方向有系统性盲区」：

1. **我的 9 条探针全部在 LF 下构造**。我把「逐字节」当成已由 `body != frozen_body`
   保证的性质，没有回头问一句：**判据读进来的字节，是不是文件里的字节**。
   `read_text()` 与「逐字节」之间有一层我没打开的转换。
2. **我核对了「诊断兜底 load-bearing」，漏核了「每步骤 code 互不相同」**。前者是我自己
   关心的问题（B44/B45 的教训），后者是 brief 自己的 DoD 条目 —— 我按自己的关注点复核，
   而不是按冻结的 DoD 逐条核。这正是 CLAUDE.md「不得因为是我自己写的计划就采信」要防的偏差。

双签名规则在此实弹生效：单签名会放行一个可被一次无害 diff 废掉的冻结判据。
