# WP-11 / WP-13 re-freeze rev2 — codex 架构复核记录

> 触发 2026-09-20 ｜ 提问者 claude（编排者）｜ 咨询者 codex（provider: kirogpt, gpt-5.6-sol, read-only sandbox, effort high）
> 性质：**冻结前 brief 审核**（非 diff 审核）。rev2 草稿无实现、无 diff、未冻结。
> 请求材料：`WP-11-13-consult-codex-rev2-request.md` ｜ 机器裁决（含逐字全文）：`WP-11-13-consult-codex-rev2-verdict.json`

## 触发理由

WP-11/13 re-freeze rev2 草稿（commit `5abcc41`）含一处**架构性方向反转**——WP-13 C3：
rev1 陷阱 4「不得改读取来源」被 WP-27/B17（`a3264c0`）推翻，改为移植 main-repo live status
范式。用户要求「先走 codex 做一次审核再冻结」。codex 是 AGENTS.md §2 的独立架构顾问，C3 反转
正属其复核范围（架构 / 数据语义）。本次为**冻结前**审核，故走手动 `codex exec`（非 `agentic gate`：
gate 按固定命名读 `{wp_id}-brief.md` 会喂 rev1 契约，B47；且草稿无 diff 可审）。

## 派发历程

| 项 | 值 |
|----|----|
| 命令形态 | `codex exec --sandbox read-only --skip-git-repo-check --disable apps -c model_provider=kirogpt（+ base_url/env_key/wire_api=responses）-c model_reasoning_effort=high -m gpt-5.6-sol -o <last> "<request.md>"` |
| provider | kirogpt（litellm bridge :18090），model `gpt-5.6-sol`，effort high，sandbox read-only |
| `--disable apps` | 沿用 WP-19 rev5 先例（避 Kiro API 64 字符工具名 HTTP 400） |
| `-o <last>` | 最后消息单独落文件（避 B9：从 8417 行日志里抓 verdict） |
| 自行读仓 | codex 在 read-only sandbox 内 grep `path_is_in_worktree`、`test_quality_gate_config.py:444`、`AGENTS.md:278`、PLAN-01 依赖链——独立性强于纯内联复核 |
| 异常 | 日志尾部 `failed to refresh available models: stream disconnected`（与 WP-19 rev4/rev5、WP-21 第一轮同因），但 **CODEX_EXIT=0** 且 `-o` 取得完整 verdict，推理未受影响 |
| 结果 | **VERDICT: REWORK**（5 项 findings，逐条见下） |

## codex 裁决（核心结论；逐字全文见 verdict.json `raw_verbatim`）

- **总裁定 `VERDICT: REWORK`**——整批 re-freeze **不可直接冻结**。
- **Q1（C3 反转）REWORK**：「C3 的方向反转是**正确的**。rev1 陷阱 4 与 WP-27 已形成根本冲突……
  『status 只提交两次』约束的是 Git 提交纪律，不是运行期读取纪律……门读取这些未提交内容正是
  单一事实源设计的结果，不会打穿 commit discipline。rev1 对『读未提交内容』的担忧已经过时。」
  **但移植范围不够**：`path_is_in_worktree()` 对另一普通 primary repo 返回 False → quality-gate 会
  接受外仓有效 status，preflight 有 `ls-files` 兜底而 rev2 quality-gate 无 → 两门仍分叉；B5 还应在
  `git.branch` 非空时校验 branch；`test_quality_gate_config.py:444` 的 linked-worktree fixture 会被
  新 C3 有意打破，须纳入 allowed_paths。
- **Q2（双根自洽）REWORK**：「两个根并存本身**完全自洽**：main_repo 是 control plane，current_worktree
  是 data plane……status 来源拒绝与 B5 拒绝没有冲突。」**真正阻断来自 AGENTS.md:278**——上位契约
  「run gates from the main repo checkout」与 B5「从声明 worktree 运行」字面矛盾，须先由 #3 归属方改契约。
- **Q3（B1 残余）REWORK**：「普通『主仓外、且不属于任何 Git repo』的路径**不会到达** preflight.sh:111……
  rev2 DoD 中构造普通仓外文件的测试，即使完全不改第 111 行也已满足……属于**无检测力的假绿测试**。
  ……我的建议是**关闭 WP-11 的 B1**，而不是为这一条已 fail-closed、极窄的诊断差异保留独立 WP。」
- **Q4（B4 挂起）ACCEPT**：「从 WP-11 移出 B4 是正确的……但 B4 最合适的归属不是长期悬空，而是
  **WP-12**……如果同一处不同时要求 `set -o pipefail` 或读取 `${PIPESTATUS[0]}`，新契约会主动推广
  一个已知会吞真实 rc 的范式。」
- **Q5（范围/lane）REWORK**：源码收缩方向对，但 lane 收益是**条件性**的；PLAN-01 仍有
  `WP-12→WP-11→WP-13` 依赖链，「即使文件不再交叠，不更新 depends_on 与 lane 元数据也不会获得并行收益」。

## 编排者逐条核验（WP-22 范式：不照单全收，独立验事实依据）

| codex finding | 编排者独立核验 | 结论 |
|---|---|---|
| Q3 B1 假绿测试 | `gate/__init__.py:210-212` 明写 path_is_in_worktree **fail-closed**（不可解析路径→refused）；普通仓外路径在 `preflight.sh:47-50` 被拒，到不了 `:111`；DoD 测试(a)不改 `:111` 也过 | **CONFIRMED（编排者错）** |
| Q1 C3 移植不完整 | `gate:204-206` 判据 `--git-dir != --git-common-dir`；另一普通 primary repo→False（不拒）；quality-gate 无 `:111` 兜底→两门分叉 | CONFIRMED |
| Q1 test:444 fixture | `test_guard_reads_main_repo_config_from_linked_worktree`（:444）从 linked worktree（:468-470）跑 quality-gate；rev2 allowed_paths 无此文件 | CONFIRMED |
| Q1/Q2 B5 绑 branch | 只比 worktree 路径不防同一 worktree 切到错误 branch 后对错误 HEAD 算 diff | CONFIRMED |
| Q2 AGENTS.md:278 冲突 | `:278-282`「run gates from the main repo checkout」vs B5「从声明 worktree 运行」字面矛盾 | CONFIRMED |
| Q5 PLAN-01 依赖链 | 实测 WP-11 `depends_on=[]` / WP-12 `['WP-11']` / WP-13 `['WP-12']`，均 lane-core；文件不交叠但链强制串行 | CONFIRMED |

**5 项 findings 全部 CONFIRMED。** 编排者自我纠错：Q3 疏漏最严重——P3-b 核验 B1 残余时确认了
`:111` 的 `2>&1` 吞错误，却漏了上游 `:47-50` worktree guard 对不可解析路径 fail-closed，使普通仓外
路径根本到不了 `:111`，据此设计的 DoD 测试(a)是无检测力假绿。与 WP-22 编排者 ACCEPT 错误同族：
核验了「改动点本身」却漏了「上游 guard 已拦截该输入」。

## 采纳决定（编排者）

| codex 条目 | 处置 |
|-----------|------|
| C3 方向反转正确 / 双根自洽 / B4 移出 WP-11 正确 | **采信**——re-freeze 核心方向成立，rev2 反转无需回退 |
| Q3 B1 假绿 | **采纳（自我纠错）**——关闭 WP-11 B1，或按「第二 primary repo + 有效 status + 非假绿 oracle + mutation 证明」重写 |
| Q1 C3 移植不完整 | **采纳**——rev3 WP-13 C3 须补「status 属于当前 main_repo 且 tracked」等价校验（防另一 primary repo） |
| Q1/Q2 B5 绑 branch | **采纳**——rev3 WP-13 B5 须校验非空 `git.branch` |
| Q1 test:444 | **采纳**——rev3 WP-13 allowed_paths 纳入 `test_quality_gate_config.py` 并迁移 linked-worktree fixture |
| Q4 B4 归属 | **采纳**——B4 转 WP-12（非无限期挂起），依赖 #3 |
| Q2 AGENTS.md §5 冲突 | **采纳，但依赖 #3**——上位契约冲突须 #3 归属方先改，或 WP-13 纳入 AGENTS.md/模板 |
| Q5 depends_on/lane | **采纳**——按最终文件图重算 depends_on/lane（P3-a 后续） |

## 对 re-freeze 的影响

**rev2 不可冻结**（VERDICT: REWORK，5 项 findings 全部 CONFIRMED）。codex 列「冻结前必须完成」6 项：

1. 关闭 WP-11，或按「第二个 primary repo + 有效 status + 非假绿 oracle」重写 B1
2. B4 明确转交 WP-12，等待 #3 的 AGENTS.md 归属裁决
3. WP-13 补 main-repo/tracked 来源校验、非空 branch 绑定、明确校验顺序
4. 解决 AGENTS.md §5 与 B5 cwd 的上位契约冲突（依赖 #3）
5. `test_quality_gate_config.py` 纳入 WP-13 范围并迁移已有 linked-worktree fixture
6. 按最终文件图重算 depends_on 和 lane；不能仅凭 Brief 缩小就宣称已脱离 lane-core

**多项依赖用户裁定**（超出编排者职权）：①关闭 WP-11 B1 还是重写 oracle（范围决策）②B4 转 WP-12
（依赖 #3）③AGENTS.md §5 上位契约冲突（依赖 #3 归属裁决）④重算 depends_on/lane。故 rev2 草稿
**保持 DRAFT，不冻结、不派发**，上报用户裁定。

## 形式备注

- codex 以 prose「VERDICT: REWORK」作答（非 `--output-schema` 的 schema 形状）——与 WP-21/22/24 记录的
  同一软约束（该 provider 下 `--output-schema` 仅建议）。编排者逐字转录，原文见 verdict.json `raw_verbatim`。
- codex 声明「本次为纯只读复核，未修改仓库，也未运行实现测试」——符合 read-only sandbox + 冻结前
  brief 审核性质（无 diff 可审，审的是方向与范围）。
