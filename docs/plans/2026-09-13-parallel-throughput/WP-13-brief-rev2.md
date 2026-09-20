# WP-13 (rev2 草稿): quality-gate 拒绝跑错目录 + status 来源锚定主仓（B5 + C3 移植）

> **状态：DRAFT — 待用户批准冻结（CONVERGENCE-PLAN §2 #8）。批准前不得派发、不得写 freeze 提交。**
> 冻结日期：待填 ｜ 编排者：claude ｜ 执行者：kimi（provider: deepseek）
> 所属 Plan：2026-09-13-parallel-throughput ｜ lane：`lane-core`（见 CONVERGENCE-P3-a）
> re-freeze 序号：rev2（第 1 次 re-freeze；**未**触发 WORK_PACKAGE.md.tmpl:9 的第 3 次停手复核门）
> 冻结后执行期间不得修改；需再修订走 re-freeze（新建 rev3）。

## rev2 相对 rev1 的变化（为什么 re-freeze）

rev1（`WP-13-brief.md`，冻结 2026-09-13）含 **B5+C3**。P3-b 存量重估
（`CONVERGENCE-P3-b-stock-reassessment.md`）核验发现 **C3 前提被 WP-27 从根本上反转**：

1. **C3 修法方向被 WP-27 推翻**：rev1 C3 立场是「门读副 worktree 冻结副本是设计使然
   （状态文件只提交两次），只需**标注来源**、**不得改读取来源**」（rev1 陷阱 4 明文）。
   但 commit `a3264c0`（WP-27/B17，已 MERGED）判定「读 worktree 快照而非主区 live status
   **本身就是 bug**」，并把 preflight 改成锚定 `main_repo` live status + 拒绝 worktree 副本 +
   emit `status=`。WP-27 已成权威范式（全局规范 §4.1：status 是主区 live 状态）。
   → rev1 C3 的「只标注、不改来源」立场**已过时且有害**：若 quality-gate 仍读 worktree
   快照而 preflight 读 main-repo live，两个门读不同份 status，判定必然分叉。
   **rev2 C3 = 把 WP-27 的 preflight 范式移植到 quality-gate**（`quality-gate.sh:9` 仍 bare `status_file=$1`）。
2. **C3 preflight 侧已完成**（WP-27）：rev2 **去掉 `preflight.sh`**（allowed_paths），只做
   quality-gate 侧。→ 消除 WP-13 与 WP-11 在 `preflight.sh` 的交叠（P3-b §4）。
3. **B5 保留**（与 WP-27 正交）：B5 = quality-gate 改动集在**进程 cwd** 算 diff（跑错目录产假
   越界）；WP-27 改的是 **status 读取来源**（读哪份 status）。两者不同面，B5 未被触及、完全有效。

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

| 面 | 结论 | 依据 |
|----|------|------|
| preflight status 来源 | **已由 WP-27 修好，不要动** | `preflight.sh` 的 `a3264c0` 段 + `:143` emit `status=` + `test_preflight_status_source.py`（468 行） |
| quality-gate status 读取 | **残余，rev2 移植 WP-27 范式** | `quality-gate.sh:9` `status_file=$1`（bare，相对 cwd）；`:27` `validate_wp_status "$status_file"` 未锚定 |
| quality-gate config 读取 | **已锚定 main_repo（现成范式）** | `:112` `qg_config_root=$(resolve_paths --root main_repo)`；`:106-111` 注释明确「config 读 main_repo，不要 open-code `${main_root:-$repo_root}` 以免静默读 worktree」——status 应与之**一致** |
| B5 改动集目录 | **残余，rev2 加前置校验** | `:26` `repo_root=$(resolve_paths --root current_worktree)` 赋值后，`:42-46` 四条 git diff/ls-files **无 `-C`/`cd`**，改动集全由 cwd 决定 |

→ 故本 WP **只改 `quality-gate.sh`**：① status 来源锚定 `main_repo`（照 `:112` config 范式 +
preflight `a3264c0`）；② B5 改动集前置校验。**不碰 `preflight.sh`**（WP-27 已修）。

## 范围

**allowed_paths**
- `src/agentic_loop/wrappers/quality-gate.sh`（status 来源锚定 + B5 前置校验）
- `tests/test_quality_gate_wrong_worktree.py`（新建，B5）
- `tests/test_gate_status_source_label.py`（新建，C3 quality-gate 侧）

**forbidden_paths**
- `.env`、`.context/`
- `src/agentic_loop/wrappers/preflight.sh`（C3 preflight 侧已由 WP-27 修完，**不得再碰**）
- `src/agentic_loop/wrappers/kimi-health.sh`（WP-12）
- `src/agentic_loop/gate/`（判定逻辑；`path_is_in_worktree` **只调用不改**，WP-19 单一权威）
- `src/agentic_loop/validate_wp_status.py`
- 其余一切未在 allowed 列出的路径

## 交付物清单

**C3 移植 —— quality-gate status 来源锚定主仓**

1. `quality-gate.sh:9` 的 status_file 解析照 preflight `a3264c0`：
   - `status_arg=$1`；相对路径锚定 `main_repo`（`resolve_paths --root main_repo`，与 `:112` config **同根**）；绝对路径不变
   - 用 `agentic_loop.gate.path_is_in_worktree` **拒绝**解析到 linked worktree 内的 status（主区副本是单一事实源）
   - 输出行 emit `status=<resolved-path>`（声明来源）
2. rc 契约不变（`0`/`2`/`64`）；worktree 拒绝用 `rc=2`（照 preflight）。

**B5 —— 拒绝跑错目录**

3. `quality-gate.sh` 在收集改动集（`:42-46`）**之前**加 fail-closed 前置校验：
   `status.git.worktree` 非空且解析绝对路径 ≠ 当前 worktree → `QUALITY_GATE_FAIL: must run inside <declared worktree>`，`rc=2`，**不做任何 scope 计算**。
4. `status.git.worktree` 为空（`APPROVED` 宽松档）→ **不**据此放行到错误目录，也**不**报错；
   按现状继续，但输出说明「未声明 worktree，改动集取自当前目录」。
5. **用上** `:26` 的死变量 `repo_root`（前置校验正好需要当前 worktree 绝对路径）。

## 完成定义（DoD）

- [ ] **反向测试（B5 硬要求）**：主区对着声明副 worktree 的 status 跑 quality-gate → `rc=2`、含 `must run inside`、**输出不含任何 `outside allowed scope`**（证明算 scope 前就拒绝）
- [ ] 正向测试（B5）：在声明的 worktree 内跑同一 status → 放行，scope 判定与改动前一致
- [ ] 正向测试（B5）：`status.git.worktree` 为空 → 不因新校验失败（宽松档不被挡）
- [ ] 测试（C3）：quality-gate status 来源锚定——相对路径解析到 `main_repo`、worktree 内副本被拒、输出含 `status=<resolved>`
- [ ] **一致性**：preflight 与 quality-gate 对同一 status 路径的解析/拒绝行为**一致**（都读 main-repo live、都拒 worktree）
- [ ] quality-gate 其余检查行为与 rc 不变（现有 gate 测试全绿）
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

1. **明确废弃 rev1 陷阱 4**：rev1 说「C3 不得改读取来源」——那是基于 C3 旧理解（读冻结副本是
   设计使然）。WP-27/B17 已证明读 worktree 快照是 **bug**，正确修法是锚定 main-repo live status。
   rev2 遵循 WP-27 范式，**不再受 rev1 陷阱 4 约束**；反而**必须**改 quality-gate 的读取来源以与
   preflight 一致（否则两门分叉）。
2. **B5 给质量门加新拒绝路径，最大风险是挡住合法调用**：`status.git.worktree` 为空的宽松档必须
   继续可用（交付物 4 + 正向测试钉这个）。
3. **不要用 `cd` 把脚本挪进 worktree「顺便修好」**：B5 的决定是**拒绝**，不是**纠正**（`cd` 会在
   调用者不知情下改工作目录语义，比拒绝更危险）。
4. `resolve_paths --root current_worktree`（`:26`，改动集/B5 用）与 `--root main_repo`（`:112` config
   + rev2 status 锚定用）是**两个不同的根**，别弄混：config/status 读 `main_repo`（INV-4），改动集看当前 worktree。
5. `path_is_in_worktree` **只调用**（WP-19 单一权威），不改 `gate/` 逻辑。
6. 本仓 Python >= 3.9；测试用 `python3.11`；跑全量**不要设** `AGENTIC_PYTHON`（B3）。
7. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 4 个，勿修。
8. **行号以冻结时 HEAD 为准**：`:9`/`:26`/`:42-46`/`:112` 为 2026-09-20 核验值，冻结前请复核。

## Allowed and forbidden paths / Completion definition / Acceptance tests

（`agentic dispatch-lint` 英文标题锚点，内容同上，以 `WP-13.status.json` 的
`scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。）
