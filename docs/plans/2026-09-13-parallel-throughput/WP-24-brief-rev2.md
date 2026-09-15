# WP-24 rev2: 把 witness 用例的原因特异性从 fixture 移回断言本身（差分对）

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> rev2 取代 rev1（`WP-24-brief-rev1.md`，sha256 `1a36ca63…`）。
> rev1 交付 `c04bc6b` **保留不动**，在其之上继续提交；本轮只补一条断言。

## 目标（一句话）

`test_witness_empty_anchor_body_fails` 目前只断言 `stderr` 含 `"Acceptance tests"`，
无法区分 `dispatch_lint.sh:86`（标题缺失）与 `:98`（标题在、段体空）两条失败路径；
改用**差分对**，让「红只可能来自 `:98`」由用例自身证明，而不是靠 fixture 恰好不漂移。

## 为什么返工（codex 第二签名 REWORK，编排者已复核）

codex 的**观察成立**：该断言对两条路径都为真，故 oracle 第 2 项（原因特异见证）
实际由 fixture 承载（段体恰为 `''`、另两锚点各留非空），fixture 一旦漂移用例不会报警。

codex 给的**修法不可达**，不要照做：它建议 `assert "empty" in stderr` 且
`assert "missing" not in stderr`。真脚本两条路径打印**同一句** `brief missing section`，
`empty` 一词两条路径都不出现。编排者已实测：把 later 锚点 `Completion definition`
分别做「改标题」与「留标题清段体」两种变异，stderr **逐字节相同**。
（codex 是被 rev1 冻结 Brief 里我自己那条 `empty`/`missing` 错误要求误导的——已登记为 B11，
责任在编排者，不在执行者。rev1 交付在该约束下的处理是正解，不构成可返工缺陷。）

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

判据从 `dispatch_lint.sh` 原文按索引切片直接跑（B11 修法 1：判据只能来自真脚本，
不 retype、不跑副本），fixture 由**真 helper** `_clear_section_body` 生成
（`importlib` 导入受审用例模块后调用）：

| fixture | 构造 | 行数 | 真判据 stdout | rc |
|---|---|---|---|---|
| A | `_clear_section_body(tmpl, "Acceptance tests")` | 62 | `brief missing section 'Acceptance tests'` | 0 |
| B | 同一份 A，仅在该标题下插入一行 `x` | 63 | *(空)* | 1 |

`## Acceptance tests` 标题在 A、B 中**都存在**，故 `:86` 在两次运行都不可能触发；
A 的红只能来自 `:98`。这就是要落进用例的判据。

## 范围

- **allowed_paths**（白名单，只能改这一个）：
  - `tests/test_wp_template_dispatch_lint.py`
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/wrappers/dispatch_lint.sh` —— **零行 diff**。
    判据本身正确；不得为了让断言好写去改它的措辞（那会把 B11 的错误反向固化进 gate）
  - `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、
    `docs/agentic/templates/WORK_PACKAGE.md` —— rev1 已定稿，本轮**零行 diff**
  - `src/agentic_loop/init_cmd.py`、`src/agentic_loop/validate_wp_status.py`、
    `src/agentic_loop/gate/__init__.py`
  - `src/agentic_loop/wrappers/` 下其余全部 `.sh`
  - `docs/plans/`（brief 与 status 由编排者维护；**含本 brief 自身**）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

> ⚠️ **方向不可反**：修的是用例的断言，不是 gate 的措辞，也不是模板。

## 交付物清单

1. `tests/test_wp_template_dispatch_lint.py` 中 `test_witness_empty_anchor_body_fails`
   改为差分对：
   - **同一份 fixture**，`## Acceptance tests` 标题在两次运行中恒定存在（用例须显式断言这一点）；
   - 变体 A（段体清空）跑真脚本 → 非零退出；
   - 变体 B（同一份 A，段体仅多一行）跑真脚本 → 退出 0 / `DISPATCH_LINT_PASS`；
   - 用例注释写明推理：标题两次都在 ⇒ `:86` 不可能是原因 ⇒ 红只能来自 `:98`，
     并给出打印点 `src/agentic_loop/wrappers/dispatch_lint.sh:98`。
2. 不得新增对 stderr 措辞的原因特异断言（`empty` / `not in "missing"` 一律不可达）。
   断言 `stderr` 含 `"Acceptance tests"` 可以保留作为**弱**辅助，但不得作为原因特异见证。

## Allowed and forbidden paths

**allowed_paths**

- `tests/test_wp_template_dispatch_lint.py` — the only writable file this round

**forbidden_paths**

- `src/agentic_loop/wrappers/dispatch_lint.sh` — the checker is correct;
  **zero-line diff**. Never reword the gate to make an assertion easier to write
- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` and
  `docs/agentic/templates/WORK_PACKAGE.md` — settled in rev1; zero-line diff
- `src/agentic_loop/init_cmd.py`, `src/agentic_loop/validate_wp_status.py`,
  `src/agentic_loop/gate/__init__.py`
- every other `.sh` under `src/agentic_loop/wrappers/`
- `docs/plans/` — briefs and status files are orchestrator-maintained
  (including this brief)
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

- The reworked witness test runs the **real** `dispatch_lint.sh` (not a copy,
  not a retyped predicate) on both halves of the differential pair.
- The test asserts the heading `## Acceptance tests` is present in **both**
  fixtures, so `:86` is excluded by construction rather than by assumption.
- Variant A (body cleared) exits non-zero; variant B (same fixture plus exactly
  one body line) exits zero. The only difference between the two runs is that
  one line.
- The oracle three items hold for the reworked test:
  1. positive reachability control on the same fixture — variant B passing IS
     that control (same file, same script, green);
  2. cause-specific witness — the differential pair itself, reasoned in a
     comment naming `dispatch_lint.sh:98`;
  3. a representative forbidden mutation still turns it red — the existing
     `test_forbidden_mutation_renamed_anchor_fails` covers the `:86` half and
     must stay green.
- All 7 rev1 tests still pass (nothing regresses).
- Green on 3.11, 3.13 and 3.14.
- Zero regression against the recorded baseline.

## Completion definition

- [ ] `test_witness_empty_anchor_body_fails` 改为差分对，原因特异性由用例承载
- [ ] 用例显式断言标题在两个变体中都存在
- [ ] 变体 A 非零退出、变体 B 退出 0；两次只差一行段体
- [ ] 注释写明推理链并给出打印点 `dispatch_lint.sh:98`
- [ ] 未新增任何对 stderr 措辞的原因特异断言
- [ ] `dispatch_lint.sh` diff **零行**
- [ ] 两份模板 diff **零行**（rev1 已定稿）
- [ ] rev1 的 7 条用例照旧全绿
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归。基线在 `dispatch_commit`（`b1ab985`）实测为
      `4 failed, 581 passed, 4 skipped`；那 4 条是既有失败
      （`tests/test_finalize_merge_triple_sign.py`）——**不要修**
- [ ] 无 forbidden_paths 写入、无跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 无 merge、无 push、不切生产分支
- [ ] commit message 符合仓库规范

## 风险声明

| 维度 | 取值 |
|---|---|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **不要去改 gate 的措辞让断言好写**。`:86`/`:98` 打印同一句是 gate 的现状；
   本轮的解法是绕过措辞（差分对），不是修改措辞。改 `dispatch_lint.sh` 即越界。
2. **差分对的「其余全部恒定」是硬要求**。两个变体必须来自同一份 fixture，
   除那一行段体外逐字节相同；否则红的原因重新变得不唯一，白做。
3. **不要用 `agentic <sub>` 自证**。那个 CLI 是指向另一棵工作树的 editable 安装，
   会跑别人的代码（缺陷 B14）。用 `PYTHONPATH=src python3.11 -m pytest …` 形态，
   直接跑你工作树里的代码。
4. **冻结输入在主仓**：Brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下。
   你工作树里 `docs/plans/` 那几份是历史快照，**一律不可作为判据**
   （缺陷 B16/B17 已登记：门禁自己也踩过这个坑）。
5. **负面断言须能转红**。`rc != 0` 可以空过；每条负面断言都要有一个变异
   能把它转红，且该变异要在报告里写出来。

### 口径权威源引用

- 判据唯一权威：`src/agentic_loop/wrappers/dispatch_lint.sh`（§5.3，本轮零改动）
- 段体判据打印点：`dispatch_lint.sh:98`；标题判据打印点：`dispatch_lint.sh:86`
- oracle 三项规则：本仓 `WORK_PACKAGE.md` 模板（rev1 已写入）+ 缺陷 B9
- 本轮返工由来：缺陷 B11（编排者用判据副本自造措辞）+ codex 第二签名裁决
  `WP-24-consult-codex-verdict.json`
