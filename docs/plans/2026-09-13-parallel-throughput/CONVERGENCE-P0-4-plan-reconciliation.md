# CONVERGENCE-P0-4：PLAN-01 对账草案（草案，本批次不改本体）

> 编排者 claude ｜ 落盘日期 2026-09-20 ｜ 依据 CONVERGENCE-PLAN.md §4 第 3 项
> **本文件是草案，本批次不修改 `PLAN-01.status.json` 本体**；修订须走用户批准流。
> 证据来源：`PLAN.md §5`、`PLAN-01.status.json`、各 WP brief/status、`git blame`、
> 源码实测（`gate/plan.py`、`preflight.sh`、`dispatch_lint.sh`、`validate_wp_status.py`、
> `plan_cmd.py`、`quality-gate.sh`、`.agentic/`）。

## §0 现状（`agentic plan check` 复现，2026-09-20 P0-1 重装后）

```
PLAN_CHECK plan_id=PLAN-01 state=DRAFT base_branch=plan/2026-09-13-parallel-throughput target_branch=main
PLAN_CHECK: wp WP-01 MERGED
PLAN_CHECK: wp WP-02 MISSING
PLAN_CHECK: wp WP-03 MERGED
PLAN_CHECK: wp WP-04 MISSING
PLAN_CHECK: wp WP-05 MISSING
PLAN_CHECK: wp WP-06 MISSING
PLAN_CHECK: wp WP-07 MISSING
PLAN_CHECK: wp WP-08 MERGED
PLAN_CHECK: wp WP-09..WP-14 state=APPROVED (not merged)
PLAN_CHECK: wp WP-28 MERGED
PLAN_CHECK: merge NOT detected
PLAN_CHECK: not converged (11 WP(s) pending or , merge not done)
```

**症状**：plan 声明 15 个 WP（01–14 + 28），其中 5 个 MISSING（02/04/05/06/07）、
6 个 APPROVED 未派发（09–14）、4 个 MERGED（01/03/08/28）。同时，本迭代实际推进的
WP-15/17/18/19/21/22/23/24/25/26/27/29 均**不在 plan 声明清单**内。plan 声明与实况脱节，
`state=DRAFT` 也从未升到 `ACTIVE`。

## §1 五个 MISSING WP 的逐个判定

判据：该 WP 原设计的交付物是否已在别的提交里落地（"已被后续 WP 交付"）；
若未落地，是否仍必要（"仍需"）；若已被架构演化超越或价值稀释（"废弃"）。

### WP-02（lane-gate，depends_on WP-01）——**废弃建议**

| 维度 | 事实 |
|---|---|
| 原目标（PLAN.md §4/§5） | 路径匹配逻辑去重：`gate/plan.py` + `wrappers/quality-gate.sh` 消除重复 |
| 原 allowed_paths | `src/agentic_loop/gate/plan.py`, `src/agentic_loop/wrappers/quality-gate.sh`, `tests/test_gate_plan*.py` |
| 交付证据 | ❌ `src/agentic_loop/gate/plan.py` **不存在**（gate/ 目录仅有 `__init__.py`/`__main__.py`/`qoder_security.py`/`report.py`） |
| 重复现状 | `quality-gate.sh:57` 注释仍写 `# Keep verbatim-aligned with agentic_loop.gate.scope_matches / scope_prefix`；`:72` 与 `:188` 两处 `startswith` 逻辑逐字重复；`gate/__init__.py` 是权威实现。**测试维持对齐**（`test_gate_scope_filter.py` 等）——这正是 §2 表格里描述的原状 |
| 是否仍需 | 弱。PLAN.md §5 已把该重复接受为"靠测试维持"的现状；WP-11/12/13 均未触碰该重复；本迭代后续 WP 也未依赖它被消除 |
| 建议 | **废弃**（从 work_packages 中移除）。若未来要消除重复，另立迭代级 WP，不阻塞本次收敛 |

### WP-04（lane-gate，depends_on WP-02）——**部分预交付，剩余废弃建议**

| 维度 | 事实 |
|---|---|
| 原目标（PLAN.md §4/§5） | 派发前 scope 交叉检查（含 C1 前缀/glob 陷阱）：`dispatch_lint.sh` 加交叉检查 + `validate_wp_status.py` 拒绝无效前缀 |
| 原 allowed_paths | `src/agentic_loop/wrappers/dispatch_lint.sh`, `src/agentic_loop/validate_wp_status.py`, `tests/test_dispatch_lint*.py` |
| C1 交付证据 | ✅ `validate_wp_status.py:146-190` 的 `_reject_unhonored_scope_entries()` 已实现 glob 拒绝；`git blame` 显示由 **`b4733058` (2026-09-10)** 落地，commit message "fix(gate): scope 匹配剥掉 /** 与 /* 尾缀，glob 条目不再形同虚设" —— **早于 plan 冻结日 2026-09-13**，属预交付 |
| 交叉检查交付证据 | ❌ `dispatch_lint.sh` 全文无 `cross`/`intersect`/`overlap`/`sibling` 相关逻辑；仅 `:73` 一处 `"Allowed and forbidden paths"` 是段名。WP-24 (MERGED) 仅补了一条 `test_wp_template_dispatch_lint.py` 断言，未触及交叉检查 |
| 是否仍需 | C1 部分：**已交付**，无剩余工作。交叉检查部分：本迭代实际演化方向是 WP-26 的 `evidence.brief.path` 单一权威 + P1 拟立 WP-30 的 B47/B63 修复，而非 WP-04 原设计的"派发前交叉检查"。原设计价值已被稀释 |
| 建议 | **废弃**（从 work_packages 中移除），并在废弃说明里点名 C1 由 `b4733058` 预交付、交叉检查由 WP-26/WP-30 路径承接 |

### WP-05（lane-plan，depends_on WP-03）——**废弃建议（架构演化超越）**

| 维度 | 事实 |
|---|---|
| 原目标（PLAN.md §4/§5） | plan 按 lane 分批收敛：`plan merge --lane`；"碰 git，风险最高" |
| 原 allowed_paths | `src/agentic_loop/plan_cmd.py`, `tests/test_plan*.py` |
| 交付证据 | ❌ `plan_cmd.py:910-926` 的 subparser 仅有 `check`/`lint`/`lanes`/`merge`/`finalize`；`merge` 是**整 plan 单次 no-ff 合并**，**无 `--lane` 标志**。`lanes` 是只读的就绪集计算（WP-03 交付），非分批合并 |
| 架构演化 | AGENTS.md §4.3 与 CONVERGENCE-PLAN.md §4.3 已确立**"一个 plan = 一个合并提交 + 一次 push"**模型：「Sequential WPs work on that one branch; only "parallel lanes" … get separate branches. The whole plan converges into a single merge commit on `main` and a single push.」 WP-05 原设计的"按 lane 分批收敛"与该模型直接冲突 |
| 是否仍需 | 否。当前模型下 lane 仅用于并行派发的文件所有权划分，不用于分批合并 |
| 建议 | **废弃**（从 work_packages 中移除），废弃说明引用 AGENTS.md §4.3 与 CONVERGENCE-PLAN.md §4.3 |

### WP-06（lane-plan，depends_on WP-03）——**废弃建议（已预交付 + WP-27 加固）**

| 维度 | 事实 |
|---|---|
| 原目标（PLAN.md §4/§5） | lane 独立 worktree 强制：`preflight.sh` worktree 校验升级 |
| 原 allowed_paths | `src/agentic_loop/wrappers/preflight.sh`, `tests/test_preflight*.py` |
| 交付证据 | ✅ `preflight.sh:67-70` "implementation must run in a secondary worktree" 与 `:86-93` "current worktree does not match status worktree" 均由 **`c555daf` (2026-08-13)** 落地——**早于 plan 冻结**，是 PLAN.md §1 自述"并行**能力**已完备（… `preflight.sh` 副 worktree 强制 …）"的实证 |
| 后续加固 | WP-19 (MERGED) 交付 `gate.path_is_in_worktree()` 单一权威；WP-27 (MERGED, `a3264c0b`) 用它拒绝 status 路径解析进 linked worktree（B17） |
| 是否仍需 | 否。原设计目标已被 `c555daf` 预交付，且被 WP-19/WP-27 进一步加固 |
| 建议 | **废弃**（从 work_packages 中移除），废弃说明引用 `c555daf` + WP-19 + WP-27 |

### WP-07（lane-docs，depends_on WP-04+05+06）——**废弃建议（依赖链断裂 + 价值已转移）**

| 维度 | 事实 |
|---|---|
| 原目标（PLAN.md §4/§5） | 经验活页 + 准入/退出规则：`.agentic/lessons.md` + `docs/` |
| 原 allowed_paths | `.agentic/lessons.md`, `docs/` |
| 交付证据 | ❌ `.agentic/` 目录仅有 `config.toml` 与 `locks/`；`lessons.md` **不存在** |
| 依赖链 | 依赖 WP-04+05+06 三者全部 MERGED；本草案建议三者均废弃，依赖链断裂 |
| 价值转移 | 经验沉淀的实际承载已是 AGENTS.md（持久规则）+ `docs/agentic/templates/WORK_PACKAGE.md.tmpl`（re-freeze 停手复核规则，WP-28 已机械化）+ `docs/plans/<iter>/` 的复核文档（如 WP-25/26 的 plan-review-before-revN）。"经验活页"这个形态在本迭代演化中**未成为权威载体** |
| 是否仍需 | 否。若未来需要 lessons 机制，应作为独立迭代级 WP 立项，而非本收敛 plan 的阻塞项 |
| 建议 | **废弃**（从 work_packages 中移除） |

## §2 六个 APPROVED 未派发 WP 的重估（WP-09~14）

依据 CONVERGENCE-PLAN.md §1 P3「#25 存量重估」：

| WP | 原缺陷 | 本迭代已修的相关缺陷 | 重估建议 |
|---|---|---|---|
| WP-09 | A1（init 吐错 gate 形式）+ A3（默认 min_independence 不自洽） | A29/A33/A34/A35/B13/B15 已修；A1/A3 未直接修 | **保留 APPROVED**，P3 阶段复核前提是否仍成立；若需 re-freeze 走 P1 基线规则 |
| WP-10 | A2（STATUS 模板默认 DRAFT 不可派发） | 同上 | **保留 APPROVED**，P3 复核 |
| WP-11 | B1（preflight 吞 git 错误）+ B4（`\| tee` 吞退出码） | 同上；preflight.sh 已被 WP-27 大幅改动 | **保留 APPROVED**，P3 复核——需检查 B1 是否已被 WP-27 顺带修掉 |
| WP-12 | B2（health UNKNOWN）+ B6（dispatched 语义）+ B3（AGENTIC_PYTHON 污染测试） | 同上 | **保留 APPROVED**，P3 复核 |
| WP-13 | B5（quality-gate 跑错目录）+ C3（输出层标注读取来源） | 同上；preflight/quality-gate 已被 WP-27 改动 | **保留 APPROVED**，P3 复核——需检查与 WP-27 的 scope 是否冲突 |
| WP-14 | C2（evidence.tests 结构写进模板） | 同上 | **保留 APPROVED**，P3 复核 |

**注**：本草案不对 WP-09~14 做去留判定，仅标注"保留 APPROVED 待 P3 重估"。
P3 重估须按 CONVERGENCE-PLAN.md §1 的口径："逐个判定前提是否已变 → 需 re-freeze 的
逐份重冻结（此时 P1 的基线规则与 #23 DoD 覆盖检查应已生效）→ 批量派发"。

## §3 不在 plan 声明清单内的实际推进 WP

本迭代实际产生 status 文件的 WP（按编号）：01/03/08/09/10/11/12/13/14/15/17/18/19/21/22/23/24/25/26/27/28/29。
其中 plan 声明清单仅含 01/02/03/04/05/06/07/08/09/10/11/12/13/14/28。

**未声明但实际推进的 WP**：

| WP | 当前 state | merged_commit | 处置建议 |
|---|---|---|---|
| WP-15 | DRAFT | — | 增补进 work_packages（lane 待定）；CONVERGENCE-PLAN §1 P3「立 brief 或关账」 |
| WP-17 | BLOCKED | — | 增补进 work_packages；CONVERGENCE-PLAN §0 N6 记录在案；P5 #34 前置 |
| WP-18 | CHANGES_REQUESTED | — | **增补进 work_packages**（用户任务明示）；P2 返工道 |
| WP-19 | MERGED | `f9e166469f15` | 增补进 work_packages（lane 待定，建议 lane-gate） |
| WP-21 | MERGED | `4a3e6f6ea912` | 增补进 work_packages |
| WP-22 | MERGED | `5afeb4fd9c34` | 增补进 work_packages |
| WP-23 | DRAFT | — | 增补进 work_packages；CONVERGENCE-PLAN §1 P3 #3（A26→WP-23） |
| WP-24 | MERGED | `46838b211de3` | 增补进 work_packages |
| WP-25 | CHANGES_REQUESTED | — | **增补进 work_packages**（用户任务明示）；P2 返工道 |
| WP-26 | CHANGES_REQUESTED | — | **增补进 work_packages**（用户任务明示）；P2 返工道 |
| WP-27 | MERGED | `d8bb090f1d29` | 增补进 work_packages |
| WP-29 | MERGED | `67791df3dce1` | 增补进 work_packages |

**WP-20**：`docs/plans/2026-09-13-parallel-throughput/WP-20.status.json` **不存在**；
CONVERGENCE-PLAN §0 N6 记录"WP-20 status 在 main 的 codex-verdict 目录下（编号跨迭代混用，
记录在案，不动）"。**不增补**进本 plan 的 work_packages。

## §4 work_packages 修订建议（草案，待用户批准后由 P3 落地）

### §4.1 移除（5 项）

```
WP-02  ← 废弃（重复未消除但已被接受为现状）
WP-04  ← 废弃（C1 由 b4733058 预交付；交叉检查由 WP-26/WP-30 路径承接）
WP-05  ← 废弃（被 AGENTS.md §4.3 一 plan 一合并模型超越）
WP-06  ← 废弃（c555daf 预交付 + WP-19/WP-27 加固）
WP-07  ← 废弃（依赖链断裂 + 价值已转移到 AGENTS.md/模板/复核文档）
```

### §4.2 增补（11 项）

```
WP-15  lane=?         depends_on=[]      （DRAFT，P3 立 brief 或关账）
WP-17  lane=?         depends_on=[]      （BLOCKED，P5 #34 前置）
WP-18  lane=?         depends_on=[]      （CHANGES_REQUESTED，P2 返工）
WP-19  lane=lane-gate depends_on=[]      （MERGED）
WP-21  lane=?         depends_on=[]      （MERGED）
WP-22  lane=?         depends_on=[]      （MERGED）
WP-23  lane=?         depends_on=[]      （DRAFT，P3 #3 A26 并入）
WP-24  lane=?         depends_on=[]      （MERGED）
WP-25  lane=?         depends_on=[]      （CHANGES_REQUESTED，P2 返工）
WP-26  lane=?         depends_on=[]      （CHANGES_REQUESTED，P2 返工）
WP-27  lane=?         depends_on=[]      （MERGED）
WP-29  lane=?         depends_on=[]      （MERGED）
```

**lane 归属待 P3 重估时按各 WP 实际 allowed_paths 与并行约束填写**；本草案不预设。
`depends_on` 一律置空——原 §5 依赖图（WP-01→02→04→11→12→13；WP-03→05/06；WP-04+05+06→07）
随 WP-02/04/05/06/07 废弃而失效；WP-11~13 的 depends_on 需相应清理（见 §4.3）。

### §4.3 既有 WP 的 depends_on 清理

| WP | 当前 depends_on | 建议 | 理由 |
|---|---|---|---|
| WP-11 | `["WP-04"]` | `[]` | WP-04 废弃 |
| WP-12 | `["WP-11"]` | 保留或置空，P3 定 | WP-11 仍 APPROVED |
| WP-13 | `["WP-12"]` | 保留或置空，P3 定 | WP-12 仍 APPROVED |
| WP-14 | `["WP-10"]` | 保留 | WP-10 仍 APPROVED |

### §4.4 修订后 work_packages 总数

- 移除 5（02/04/05/06/07）
- 保留 10（01/03/08/09/10/11/12/13/14/28）
- 增补 12（15/17/18/19/21/22/23/24/25/26/27/29）
- **合计 22 个 WP**

### §4.5 修订后 `agentic plan check` 预期输出

```
PLAN_CHECK plan_id=PLAN-01 state=ACTIVE base_branch=plan/2026-09-13-parallel-throughput target_branch=main
PLAN_CHECK: wp WP-01 MERGED
PLAN_CHECK: wp WP-03 MERGED
PLAN_CHECK: wp WP-08 MERGED
PLAN_CHECK: wp WP-09..WP-14 state=APPROVED (not merged)   ← 6 项
PLAN_CHECK: wp WP-15 state=DRAFT (not merged)
PLAN_CHECK: wp WP-17 state=BLOCKED (not merged)
PLAN_CHECK: wp WP-18 state=CHANGES_REQUESTED (not merged)
PLAN_CHECK: wp WP-19 MERGED
PLAN_CHECK: wp WP-21 MERGED
PLAN_CHECK: wp WP-22 MERGED
PLAN_CHECK: wp WP-23 state=DRAFT (not merged)
PLAN_CHECK: wp WP-24 MERGED
PLAN_CHECK: wp WP-25 state=CHANGES_REQUESTED (not merged)
PLAN_CHECK: wp WP-26 state=CHANGES_REQUESTED (not merged)
PLAN_CHECK: wp WP-27 MERGED
PLAN_CHECK: wp WP-28 MERGED
PLAN_CHECK: wp WP-29 MERGED
PLAN_CHECK: merge NOT detected
PLAN_CHECK: not converged (11 WP(s) pending or , merge not done)
```

收敛前置：11 个未 MERGED 的 WP（09~15/17/18/23/25/26）须全部到达 MERGED；
其中 WP-15/23 需先立 brief，WP-17 需解 BLOCKED，WP-18/25/26 需返工，WP-09~14 需 P3 重估后派发。

## §5 state DRAFT→ACTIVE 建议

### §5.1 当前 DRAFT 的语义

`agentic-plan-status/v1` schema 的状态机（AGENTS.md §4.3）：

```
DRAFT -> ACTIVE -> READY_TO_MERGE -> MERGED
DRAFT -> ABANDONED
ACTIVE -> BLOCKED -> ACTIVE
```

`DRAFT -> ACTIVE` 的语义："冻结 plan，从最新 `main` 切出集成分支，把每个 WP 的
`git.base_branch` 指向它"。

### §5.2 实况

- 集成分支 `plan/2026-09-13-parallel-throughput` **已存在**（当前 HEAD `4d6b8b6`）
- 各 WP 的 `git.base_branch` 实际已指向该集成分支（抽查 WP-19/21/22/24/27/28/29 均如此）
- plan 已实际承载了 22 个 WP 的推进（10 个 MERGED、其余在途）
- **plan 事实上已 ACTIVE**，只是 status 文件的 `state` 字段未升级

### §5.3 建议

**建议将 `state` 从 `DRAFT` 升到 `ACTIVE`**，但**须与 §4 的 work_packages 修订同批落地**：

1. 先按 §4 修订 work_packages（移除 5 + 增补 12 + 清理 depends_on）
2. 同一次提交里把 `state` 改为 `ACTIVE`
3. `timestamps.updated_at` 更新到落地时刻
4. 该提交属 plan 级修订，须用户批准（CONVERGENCE-PLAN §2 待裁定清单 #4）

**本批次不执行**（CONVERGENCE-PLAN §4 第 3 项明令"不得修改 PLAN-01.status.json 本体"）。

## §6 风险与未决项

1. **lane 归属未定**：§4.2 增补的 12 个 WP 的 lane 字段本草案不预设，须 P3 重估时
   按各 WP allowed_paths 与并行约束填写。若 lane 归属错误，`plan lanes` 的就绪集计算
   会失真。
2. **WP-09~14 的前提重估未做**：§2 仅标注"保留 APPROVED 待 P3 重估"，未逐个核验
   A1/A2/A3/B1~B6/C2/C3 是否已被本迭代其他 WP 顺带修掉。P3 重估须逐份核验。
3. **WP-11/12/13 的 depends_on 链**：§4.3 建议清理 WP-11 的 `["WP-04"]`，但 WP-12/13
   的链式依赖是否保留须 P3 定。若保留，WP-12 须等 WP-11 MERGED；若置空，三者可并行。
4. **WP-15/17/23 的归属**：WP-15（DRAFT，无 evidence.brief.path）与 WP-23（DRAFT）
   须先立 brief；WP-17（BLOCKED）须先解 BLOCKED（CONVERGENCE-PLAN §1 P5 #34 前置）。
   三者均可能成为收敛的长尾阻塞项。
5. **WP-20 编号跨迭代混用**：§0 N6 记录在案，本草案不动。若未来要规范化，须另立
   跨迭代对账 WP。
6. **`agentic plan check` 输出小瑕疵**：末行 `not converged (11 WP(s) pending or , merge not done)`
   中 `or` 后缺词（疑为 `or missing` 的拼接遗漏）。非本草案范围，记录备查。

## §7 落地路径（待用户批准后）

1. 用户批准本草案的 §4 修订建议与 §5 state 升级建议
2. 由 P3 阶段（或专门的 plan 修订 WP）执行：
   - 编辑 `PLAN-01.status.json`：移除 5 项、增补 12 项、清理 depends_on、state→ACTIVE、updated_at
   - 提交信息前缀 `📋 plan(2026-09-13-parallel-throughput): PLAN-01 对账修订（P0-4 草案落地）`
   - 显式路径提交：`git add docs/plans/2026-09-13-parallel-throughput/PLAN-01.status.json && git commit -- docs/plans/2026-09-13-parallel-throughput/PLAN-01.status.json`
3. 复测 `agentic plan check`，确认输出与 §4.5 预期一致
4. 复测 `agentic plan lint`，确认每 WP 的 freeze+finalize 提交纪律仍满足

## §8 证据索引

- `PLAN.md §4/§5`：WP-02/04/05/06/07 的原目标与 allowed_paths
- `PLAN-01.status.json`：当前 work_packages 声明（15 项）
- `git blame src/agentic_loop/validate_wp_status.py:146-190`：C1 由 `b4733058` (2026-09-10) 预交付
- `git blame src/agentic_loop/wrappers/preflight.sh:67-93`：worktree 隔离由 `c555daf` (2026-08-13) 预交付
- `src/agentic_loop/plan_cmd.py:910-926`：subparser 无 `merge --lane`
- `src/agentic_loop/gate/`：无 `plan.py`
- `src/agentic_loop/wrappers/quality-gate.sh:57,72,188`：重复逻辑仍在
- `src/agentic_loop/wrappers/dispatch_lint.sh`：无交叉检查逻辑
- `.agentic/`：无 `lessons.md`
- `git show --stat a3264c0b`：WP-27 (B17) 用 `path_is_in_worktree` 加固 preflight
- 各 WP status 文件：state 与 merged_commit 实测（见 §0 与 §3 表格）
- `agentic plan check` 实测输出（P0-1 重装后，2026-09-20）

---

**本文件是草案，不修改 PLAN-01.status.json 本体。修订须走用户批准流（CONVERGENCE-PLAN §2 #4）。**
