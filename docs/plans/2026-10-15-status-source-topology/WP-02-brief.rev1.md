# WP-02 — 两处 status 来源判定改用加固判据，关闭当前已存在的 INV-5 违反

> rev1 冻结日期 2026-10-15 | 编排者 Kiro（DSH 会话）| 执行者 kimi。
> 状态：**DRAFT（待二签 ACCEPT 后派发）**。
> 本 WP 与 WP-01 的信任根问题**无关**，可独立完成；用户已决定先做本 WP。

## 1. 问题（编排者已实测复现，与任何本次改动无关）

「status 文件不得位于 worktree 内」这条判定在仓库里有**两套互不一致的实现**：

**加固判据（正确，WP-19 单一权威）** —— `gate.path_is_in_worktree()`，基于 git 事实
（`--git-dir != --git-common-dir`），经 A13/A19/A22/A27/A28 加固，17 个护栏用例守着。
三处引用它：

```text
src/agentic_loop/wrappers/preflight.sh:44
src/agentic_loop/wrappers/finalize_merge.sh:160
src/agentic_loop/gate/__init__.py:810
```

**路径字面量（错误，被废弃的旧做法）** —— 两处只比对路径里是否含 `"/.worktrees/"`：

```bash
# src/agentic_loop/wrappers/merge.sh:37
if [[ "$status_file" == *"/.worktrees/"* ]]; then
```

```python
# src/agentic_loop/gate/qoder_security.py:1012
if "/.worktrees/" in str(status_file):
```

该写法正是护栏用例 `test_verdict_does_not_depend_on_directory_name` 明确记为错误的做法
（其注释原文：*the old `"/.worktrees/" in path` literal would refuse it; the git-fact
predicate must not*）。

**实测后果（当前树，无需任何改动即可观察）**：本机 `main` 签出位于
`/Users/admin/vibe/agentic-loop-main-codex-merge`，是一个 **linked worktree**，但路径里
**不含** `/.worktrees/`。于是对同一个 status 路径：

| 调用点 | 判定 | 依据 |
| --- | --- | --- |
| `preflight.sh` / `finalize_merge.sh` / `gate/__init__.py` | **拒绝** | git 事实判据 |
| `merge.sh` / `qoder_security.py` | **接受** | 字面量未命中 |

即 **INV-5（单一权威）在当前树中已被违反**，两类调用点对同一输入给出相反结论。

字面量写法有两个方向的错：

- **漏判（fail-open，更危险）**：任何不含 `/.worktrees/` 的 linked worktree 路径都被放行，
  例如 `git worktree add ../sibling` 产生的同级目录 —— 这是本仓实际使用的布局
  （`test_sibling_worktree_path_is_worktree` 的注释明确指出：*The layout this repo actually
  uses: `git worktree add ../wpN-x` — a sibling directory whose name never contains
  ".worktrees/"*）。
- **误判（fail-closed）**：主仓内一个真名为 `.worktrees` 的普通目录会被错误拒绝，
  而它其实是主仓内容。

## 2. 方向

把这两处改为引用那条唯一的加固判据，使五个产生该拒绝语义的位置**全部**基于同一事实来源。
不新增判据、不改判据本体、不放宽任何既有语义。

`preflight.sh:40-50` 已给出 shell 侧的标准范式（内联 Python 探针 + `PROBE_FAIL` 兜底），
`merge.sh` 照搬即可。

## 3. 不变量

**INV-A（单一权威）**：全仓**不得再有**任何基于路径字面量的 worktree 判定。改造后，所有
产生「status file resolves inside a worktree」语义的位置都必须直接或间接调用
`gate.path_is_in_worktree()`。

**INV-B（fail-closed 不得退化）**：shell 侧探针必须保留 `preflight.sh` 的 fail-closed 形态
—— 探针异常、Python 不可用、import 失败、输出非预期一律**拒绝**，绝不因探针失败而放行。
`merge.sh` 的实现必须显式处理 `PROBE_FAIL`（范式见 `preflight.sh:40`：
`|| echo PROBE_FAIL`，随后 `!= "MAIN"` 即拒）。

**INV-C（语义只收紧、不放宽）**：改造后被拒绝的输入集合必须是改造前的**超集**：原先因
字面量命中而被拒的继续被拒；原先漏判放行的 linked worktree 路径转为拒绝。唯一允许的
「放宽」是主仓内名为 `.worktrees` 的真实目录 —— 它本就是主仓内容，由
`test_verdict_does_not_depend_on_directory_name` 的语义背书。

**INV-D（错误文案与退出码不变）**：两处对外可见的失败文案前缀（`MERGE_FAIL:` /
`GateError`）与退出码保持不变，避免破坏既有调用方与测试。

## 4. 验收测试

新建 `tests/test_worktree_literal_removal.py`，沿用 `tests/test_worktree_detection.py`
的真实 git fixture 风格（`git init` + 真实 `git worktree add`，不 mock git）。

- **F1 `[merge-refuses-sibling-worktree]`**：`git worktree add ../sibling` 造出路径**不含**
  `/.worktrees/` 的 linked worktree，其中放一个 status 文件，调用 `merge.sh` →
  必须**拒绝**。本用例必须自证攻击前提：断言该路径确实不含 `/.worktrees/`
  （否则字面量恰好命中，节点会因无关原因变绿）。
- **F2 `[qoder-refuses-sibling-worktree]`**：同样布局下调用
  `agentic_loop.gate.qoder_security.main([<status path>])` → 必须**拒绝**（抛 `GateError`），
  且断言路径不含 `/.worktrees/`。

  **构造注意（编排者实测）**：`qoder_security.main` 在第 1007 行先做 `status_file.is_file()`
  检查、第 1012 行才做 worktree 判定。因此 fixture 里的 status 文件**必须真实存在**，
  否则用例会以 `status file not found` 提前失败 —— 那是「因无关原因变红」，不构成本节点的
  证据。该顺序本身不在本 WP 范围内，不要调整。

  另：`main()` 会把相对路径按 `main_repo()` 解析（第 997 行），fixture 必须传**绝对路径**
  或正确设置主仓，否则解析目标与预期不符。
- **F3 `[merge-accepts-literal-dot-worktrees-dir-in-main-repo]`**：主仓内真实创建
  `.worktrees/fake/` 普通目录并放 status 文件 → 必须**接受**（不得因字面量而拒）。
  这是 INV-C 允许的那一处收紧反向。
- **F4 `[qoder-accepts-literal-dot-worktrees-dir-in-main-repo]`**：同 F3，对 qoder 入口。
  同样必须让 status 文件真实存在（见 F2 的构造注意），且该文件需能通过
  `run_validator` 之前的那段检查 —— 本节点只断言「未因 worktree 判定被拒」，
  若后续校验因别的原因失败，须在报告中说明断言是如何只锁定 worktree 判定这一步的。
- **F5 `[merge-probe-failure-fails-closed]`**：令探针失败（例如把 `AGENTIC_PYTHON` 指向一个
  必然失败的可执行文件）→ `merge.sh` 必须**拒绝**，不得放行。断言退出码与
  `MERGE_FAIL:` 文案前缀。
- **F6 `[no-literal-worktree-check-remains]`**：静态断言 —— 在 `src/agentic_loop/` 下
  grep `"/.worktrees/"`，**只允许**出现在测试文件与注释中，产品代码里的判定分支必须为 0 处。
  该用例守 INV-A，防止回归。

## 5. 承重变异（DoD 必做，逐条分别施加、分别验证、精确还原）

- **M-A**：把 `merge.sh` 的判定退回字面量 → **F1 必须转红**，且红的形态必须是
  「linked worktree 被错误接受」（而非别的报错）。
- **M-B**：把 `qoder_security.py` 的判定退回字面量 → **F2 必须转红**。
- **M-C**：去掉 `merge.sh` 探针的 `PROBE_FAIL` 兜底（探针失败时当作 MAIN 放行）→
  **F5 必须转红**。该变异证明 INV-B 承重。
- **M-D**：把新判定改成「只要在任何 git 仓库内就接受」→ **F1 与 F2 必须同时转红**。
  该变异证明新判定不是把门打开。

M-A/M-B 与 M-C 必须分别施加：前两者证明「换成 git 事实」承重，后者证明「fail-closed」承重。

## 6. 范围

**允许修改**：

- `src/agentic_loop/wrappers/merge.sh`
- `src/agentic_loop/gate/qoder_security.py`
- `tests/test_worktree_literal_removal.py`（新建）

**禁止修改**：

- `src/agentic_loop/gate/__init__.py` —— 判据本体，本 WP 只引用、不改动
- `tests/test_worktree_detection.py` —— 17 个护栏，只读
- `src/agentic_loop/wrappers/preflight.sh`、`finalize_merge.sh` —— 已正确，不动
- `src/agentic_loop/plan_cmd.py`、`validate_wp_status.py`、`autonomy.py`
- `.agentic/config.toml`、`uv.lock`、`docs/plans/**`、`docs/agentic/templates/**`

## 7. 完成定义（DoD）

- [ ] F1–F6 全绿。F1/F2 必须附「路径不含 `/.worktrees/`」的自证断言输出。
- [ ] M-A ~ M-D 逐条红证齐备（含还原回绿，还原后 `git diff` 为空），报告附逐条实际输出。
- [ ] 护栏只读：`tests/test_worktree_detection.py` 的 **17** 个用例全部仍绿，且该文件
      `git diff` 为空。
- [ ] 保护集全绿：`tests/test_preflight_status_source.py`、
      `tests/test_finalize_merge_first_call.py`、`tests/test_finalize_merge_toctou.py`、
      `tests/test_finalize_merge_sequential.py`。
- [ ] 全量不低于基线 **902 passed / 4 skipped**（新增用例会使总数上升）。
- [ ] **单一权威自检**：报告须 grep 证明 `src/agentic_loop/` 产品代码中基于
      `"/.worktrees/"` 的判定分支为 **0** 处，并列出五个位置现在共同引用的那一个函数。
- [ ] **语义收紧自检**：报告须说明改造前后被拒输入集合的差异，确认符合 INV-C
      （只增不减，唯一例外是主仓内的真实 `.worktrees` 目录）。
- [ ] 不得新增任何旁路开关或环境变量。

## 8. 残余风险

- 本 WP 使 `merge.sh` 与 `qoder_security.py` 开始拒绝此前被漏判放行的 linked worktree 路径。
  这是**刻意的收紧**，但可能让此前「碰巧能用」的调用方开始失败。对本仓当前布局而言，这正是
  WP-01 要处理的死锁的一部分 —— 本 WP 不解决该死锁，只统一判定来源；两者先后关系已在
  WP-01 的 `scope.decisions.wp02_split` 中记录。
- 判定与使用之间的 ref/worktree 竞态不在本 WP 范围内（与既有判据同类）。
