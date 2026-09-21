# WP-13 (rev3 草稿): quality-gate status 锚定主仓+tracked 校验 + 拒绝跑错目录/错分支（C3 完整移植 + B5 增强）

> **状态：DRAFT — 冻结前须先解 #3（AGENTS.md §5 上位契约冲突）+ 用户批准（CONVERGENCE-PLAN §2 #8）。**
> 冻结日期：待填 ｜ 编排者：claude ｜ 执行者：kimi（provider: deepseek）
> 所属 Plan：2026-09-13-parallel-throughput ｜ lane：`lane-core`（**待定**，见陷阱 1 + codex Q5：依赖 #3 与文件图重算）
> re-freeze 序号：rev3（第 2 次 re-freeze；**未**触发 WORK_PACKAGE.md.tmpl:9 的第 3 次停手复核门）
> 冻结后执行期间不得修改；需再修订走 re-freeze（新建 rev4）。

## rev3 相对 rev2 的变化（为什么再 re-freeze）

rev2（`WP-13-brief-rev2.md`，commit `5abcc41`）经 codex 架构复核
（`WP-11-13-consult-codex-rev2-verdict.json`，**VERDICT: REWORK**，5 项 findings 编排者逐条核验全部
CONFIRMED）。rev3 修正其中 4 项 wrapper 侧不足，第 5 项（AGENTS.md §5）依赖 #3：

1. **C3 移植不完整 → 补 tracked 校验**（codex Q1）：`path_is_in_worktree()` 判据是
   `--git-dir != --git-common-dir`（`gate/__init__.py:204-206`），对**另一个普通 primary repo**
   （非 linked worktree）返回 `False`（不拒）。rev2 只移植「锚定 main_repo + path_is_in_worktree 拒绝」
   会**接受来自另一普通 primary repo 的有效 status**；preflight 还有 `:111` 的 `git -C main_root ls-files`
   兜底，rev2 quality-gate 无对应检查 → 两门仍分叉。rev3 补等价 tracked 校验。
2. **B5 只比 worktree 路径 → 补 branch 校验**（codex Q1/Q2）：只比 `status.git.worktree` vs cwd，
   无法防止同一 worktree 被切到错误 branch 后仍对错误 `HEAD` 算 diff。rev3 在 `git.branch` 非空时同步校验当前 branch。
3. **`test_quality_gate_config.py:444` 纳入范围**（codex Q1）：现有
   `test_guard_reads_main_repo_config_from_linked_worktree`（`:444`）从 linked worktree 跑 quality-gate；
   新 C3（拒绝 worktree 内 status）会有意打破它。rev2 allowed_paths 漏了此文件 → DoD「现有 gate 测试全绿」
   不可达。rev3 纳入并迁移该 fixture 到主区 live status。
4. **冻结校验顺序**（codex Q2）：rev2 未明确 status 来源拒绝、worktree/branch 拒绝与 scope/diff 计算的先后。
   rev3 冻结 codex 给出的顺序（拒绝必须在 scope/diff 之前）。
5. **AGENTS.md §5 上位契约冲突 → 依赖 #3，rev3 为 wrapper-only**（codex Q2）：`AGENTS.md:278-282`
   字面「run gates from the main repo checkout」与 B5「从声明 worktree 运行」矛盾。AGENTS.md 是 #3 未裁决
   归属的禁区，rev3 **不碰 AGENTS.md**；**冻结前须 #3 先解**（见陷阱 1）。

## 前置事实（编排者 + codex 已实测，执行者不必重做，但**不得与之矛盾**）

| 面 | 结论 | 依据 |
|----|------|------|
| quality-gate status 读取 | **残余，rev3 完整移植 preflight 范式** | `quality-gate.sh:9` `status_file=$1`（bare，相对 cwd）；`:27` `validate_wp_status "$status_file"` 未锚定 |
| config 读取（现成范式） | **已锚定 main_repo** | `:112` `qg_config_root=$(resolve_paths --root main_repo)`；`:106-111` 注释「不要 open-code `${main_root:-$repo_root}`，否则静默读 worktree」——status 应与之**同根** |
| preflight 完整范式 | **锚定 + worktree 拒绝 + tracked 兜底** | `preflight.sh:31-35`（main_repo 锚定）、`:40-50`（path_is_in_worktree 拒绝）、`:111`（`git -C main_root ls-files --error-unmatch` tracked 兜底） |
| path_is_in_worktree 局限 | **对另一普通 primary repo 返回 False** | `gate/__init__.py:204-206`（判据 `--git-dir != --git-common-dir`）；`:210-212` 不可解析路径 fail-closed→True（refused） |
| B5 改动集目录 | **残余，rev3 加 worktree+branch 前置校验** | `:26` `repo_root=$(resolve_paths --root current_worktree)` 赋值后，`:39-46` 四条 git diff/ls-files **无 `-C`/`cd`**，改动集全由 cwd 决定 |
| 现有 linked-worktree 测试 | **会被新 C3 打破，须迁移** | `tests/test_quality_gate_config.py:444`（`:468-470` `git worktree add`） |
| AGENTS.md §5 冲突 | **上位契约字面矛盾，依赖 #3** | `AGENTS.md:278-282`「run gates from the main repo checkout」vs B5「从声明 worktree 运行」 |

## 范围

**allowed_paths**
- `src/agentic_loop/wrappers/quality-gate.sh`（C3 锚定+tracked 校验 + B5 worktree/branch 前置校验）
- `tests/test_quality_gate_wrong_worktree.py`（新建，B5）
- `tests/test_gate_status_source_label.py`（新建，C3 quality-gate 侧）
- `tests/test_quality_gate_config.py`（**rev3 新增**：迁移 `:444` linked-worktree fixture 到主区 live status）

**forbidden_paths**
- `.env`、`.context/`
- `src/agentic_loop/wrappers/preflight.sh`（C3 preflight 侧已由 WP-27 修完，**不得再碰**）
- `AGENTS.md`、`src/agentic_loop/templates/AGENTS.md.tmpl`（#3 禁区；契约表述随 #3 裁决，**不在 rev3 wrapper scope**）
- `src/agentic_loop/gate/`（判定逻辑；`path_is_in_worktree` **只调用不改**，WP-19 单一权威）
- `src/agentic_loop/wrappers/kimi-health.sh`（WP-12）、`src/agentic_loop/validate_wp_status.py`
- 其余一切未在 allowed 列出的路径

## 交付物清单

**C3 完整移植 —— quality-gate status 锚定主仓 + tracked 校验**

1. `quality-gate.sh:9` 的 status_file 解析照 `preflight.sh:31-50`：
   - `status_arg=$1`；相对路径锚定 `main_repo`（`resolve_paths --root main_repo`，与 `:112` config **同根**）；绝对路径不变
   - 用 `agentic_loop.gate.path_is_in_worktree` **拒绝**解析到 linked worktree 内的 status（主区副本是单一事实源）
2. **补 tracked 兜底校验**（codex Q1 核心）：照 `preflight.sh:111`，
   `git -C "$main_root" ls-files --error-unmatch "$status_file"` 拒绝「另一普通 primary repo 的有效 status」
   （path_is_in_worktree 对其返回 False，须靠 ls-files 兜底）；错误信息区分「外仓/未跟踪」，**把 git stderr 带进错误**（不整条丢 /dev/null）。
3. 输出行 emit `status=<resolved-path>`（声明来源）。
4. rc 契约不变（`0`/`2`/`64`）；worktree 拒绝、外仓/未跟踪拒绝均用 `rc=2`。

**B5 增强 —— 拒绝跑错目录 + 错分支**

5. 在收集改动集（`:39-46`）**之前**加 fail-closed 前置校验：
   - `status.git.worktree` 非空且解析绝对路径 ≠ 当前 worktree → `QUALITY_GATE_FAIL: must run inside <declared worktree>`，`rc=2`
   - `status.git.branch` 非空且 ≠ 当前 branch（`git branch --show-current`）→ `QUALITY_GATE_FAIL: branch mismatch`，`rc=2`
   - 任一失败**立即 rc=2，不做任何 scope/diff 计算**
6. 字段为空（`APPROVED` 宽松档）→ **不**据此放行到错误目录，也**不**报错；按现状继续，但输出说明「未声明 worktree/branch，改动集取自当前目录」。
7. **用上** `:26` 的死变量 `repo_root`（前置校验正好需要当前 worktree 绝对路径）。

**校验顺序（codex Q2，冻结）**

8. 顺序固定为：① 解析 `main_repo`、锚定并验证 status 来源（含 tracked 兜底）→ ② 校验 schema、读 `git.worktree`/`git.branch`/scope/base → ③ 解析 `current_worktree` → ④ `git.worktree`/`git.branch` 非空时比较，失败立即 `rc=2` → ⑤ 之后才收集当前 worktree 改动集。

**test:444 迁移**

9. `test_quality_gate_config.py:444` 的 linked-worktree fixture 改成主区 live status（新 C3 会拒绝 worktree 内 status）；保持该测试原意（guard 读 main_repo config）不变。

## 完成定义（DoD）

- [ ] **C3 来源**：相对路径解析到 `main_repo`、worktree 内副本被拒、输出含 `status=<resolved>`
- [ ] **C3 tracked（codex Q1）**：**另一个普通 primary repo 的有效 status 被拒**（path_is_in_worktree=False 但 ls-files 兜底拒绝）；错误信息区分外仓/未跟踪
- [ ] **B5 反向**：主区对着声明副 worktree 的 status 跑 → `rc=2`、含 `must run inside`、**输出不含任何 `outside allowed scope`**（证明算 scope 前就拒绝）
- [ ] **B5 branch（codex Q1/Q2）**：声明 worktree 内但 branch 错误 → `rc=2`、含 `branch mismatch`
- [ ] **B5 正向**：声明 worktree 内 + 正确 branch → 放行，scope 判定与改动前一致；字段空宽松档不被挡
- [ ] **一致性**：preflight 与 quality-gate 对同一 status 路径的解析/拒绝/tracked 行为**一致**
- [ ] **test:444 迁移后全绿**；现有 gate 测试全绿
- [ ] `python3.11 -m pytest tests -q` 除已知 4 个预存基线失败外全绿
- [ ] 无 forbidden_paths 写入；无生产 DB/网络/推送
- [ ] commit message 符合规范（gitmoji 前缀 + 中文说明）

## 风险声明

| 维度 | 取值 |
|------|------|
| production_writes | `FORBIDDEN` |
| network | `FORBIDDEN` |
| notifications | `FORBIDDEN` |
| data_access | `READ_ONLY` |

## 附注：已知陷阱

1. **AGENTS.md §5 上位契约冲突（依赖 #3，冻结前须解）**：`AGENTS.md:278-282`「run gates from the main
   repo checkout」与 B5「从声明 worktree 运行」字面矛盾。rev3 为 **wrapper-only**，不碰 AGENTS.md（#3 禁区）。
   **冻结前须 #3 裁决**：要么 #3 先把契约表述改为「从待审 worktree 调用 `agentic quality-gate`；CLI 选主区
   权威 wrapper，status/config 读主区 live 副本」，要么把 AGENTS.md/模板重新纳入 WP-13（与 #3 冲突）。
   **存在上位冲突时不得只冻结 wrapper**（codex Q2）。
2. **C3 tracked 校验不削弱 path_is_in_worktree**：两者**并列**（worktree 内副本拒绝 + 外仓/未跟踪拒绝），各自保留，不要用一个替换另一个。
3. **path_is_in_worktree 对另一普通 primary repo 返回 False**（`gate:204-206`）——所以**必须**有 ls-files tracked 兜底，否则外仓有效 status 漏过（codex Q1 核心，rev2 的漏洞）。
4. **校验顺序**：status 来源 + worktree/branch 拒绝**必须在 scope/diff 计算之前**（否则跑错目录会先算出一堆假越界，B5 的本意就是拒绝而非纠正）。
5. **B5 是拒绝不是纠正**：不要用 `cd` 把脚本挪进 worktree「顺便修好」（`cd` 在调用者不知情下改工作目录语义，比拒绝更危险）。
6. **两个根别混**：`current_worktree`（`:26`，改动集/B5）vs `main_repo`（`:112` config + rev3 status 锚定）——config/status 读 `main_repo`（INV-4），改动集看当前 worktree。
7. `path_is_in_worktree` **只调用**（WP-19 单一权威），不改 `gate/` 逻辑。
8. **后续缺陷登记（codex Q1，不在 rev3）**：主区 tracked symlink 指向另一普通仓库时，`path_is_in_worktree` + `ls-files` 组合仍可能放行；彻底关闭需按实际解析目标验证 repo identity，会牵涉 preflight，**登记为后续缺陷**，rev3 不悄忽略也不在此修。
9. 本仓 Python >= 3.9；测试用 `python3.11`；跑全量**不要设** `AGENTIC_PYTHON`（B3）。
10. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 4 个，勿修。
11. **行号以冻结时 HEAD 为准**：`:9`/`:26`/`:39-46`/`:112`、`preflight.sh:31-50`/`:111`、`gate:204-212`、`test_quality_gate_config.py:444` 为 2026-09-21 核验值，冻结前请复核。

## Allowed and forbidden paths / Completion definition / Acceptance tests

（`agentic dispatch-lint` 英文标题锚点，内容同上，以 `WP-13.status.json` 的
`scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。）
