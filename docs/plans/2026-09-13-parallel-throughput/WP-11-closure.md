# WP-11 关闭记录（B1 残余过宽 + B4 归属转移）

> 关闭日期 2026-09-21 ｜ 编排者 claude ｜ lane lane-core（原）
> 权威：用户「按你的建议执行」(2026-09-21) + codex 架构复核 **VERDICT: REWORK**
> （`WP-11-13-consult-codex-rev2-verdict.json`，commit `6795c20`）Q3 / Q4，编排者逐条核验 CONFIRMED。
> 关闭前：`APPROVED`（rev1 冻结 2026-09-13；rev2 草稿 `5abcc41`，**未冻结、未派发**）。
> 关闭后：`DRAFT`（撤回冻结）+ 从 `PLAN-01.status.json` work_packages 移除。

## 1. WP-11 原是什么

| 版本 | 范围 | 状态 |
|------|------|------|
| rev1（`WP-11-brief.md`，冻结 2026-09-13） | **B1**（preflight tracked 检查区分「路径在仓外」vs「仓内未跟踪」）+ **B4**（`AGENTS.md §4.1` 派发范式加 `pipefail`） | APPROVED |
| rev2（`WP-11-brief-rev2.md`，`5abcc41`） | 收缩为**只剩 B1 残余**（`preflight.sh:111` 错误信息分辨）；**B4 移出挂起**（AGENTS.md 属 #3 禁区）；allowed_paths 去掉 AGENTS.md/模板 | DRAFT（未冻结） |

**关键实测**：WP-11 声明的 `git.branch=feature/wp11-preflight-tracked-pipefail`、
`git.worktree=../wp11-preflight-tracked` **均从未创建**（`git branch --list 'feature/wp11*'` 空；
`git worktree list` 无该树）。即 WP-11 **从未派发、无实现、无 diff**——关闭不涉及任何代码回退或工作树清理。

## 2. 为什么关闭（codex REWORK，编排者已核验）

### Q3 — B1 残余过宽，rev2 DoD 测试 (a) 是无检测力假绿（CONFIRMED，编排者原疏漏）

- rev2 DoD 测试 (a)：「status 路径指向主仓外（非 worktree）→ 断言错误信息不含 `must be tracked`、含路径/仓库语义、`rc==2`」。
- **该用例即使完全不改 `preflight.sh:111` 也已通过**：`path_is_in_worktree`（`gate/__init__.py:210-212`）
  文档明写 **fail-closed**——不可解析路径（非 git repo / git missing / 意外输出）`treated as inside a
  worktree, i.e. refused`。故普通「主仓外、且非任何 git repo」路径在 `preflight.sh:47-50` 即被拒
  （`PREFLIGHT_FAIL: resolves inside a worktree`，rc=2，信息不含 `must be tracked`），**根本到不了 `:111`**。
- **B1 真实残余只在更窄情形**：status 位于**另一个普通 primary Git repo** 且内容有效到通过
  schema/branch/worktree 前置检查（此时 `path_is_in_worktree=False`，到 `:111`，主仓 `ls-files`
  报 outside-repo 被 `2>&1 >/dev/null` 吞掉 → 误报 `must be tracked`）。
- **且此残余是「错误信息质量」而非「门被打开」**：该路径 `:111` 仍 `rc=2` **拒绝**（fail-closed 保持），
  只是错误信息把「外仓/未跟踪」误并成一句 `must be tracked`。安全语义未破，仅诊断信息不精确。

→ 结论：以 rev2 形态冻结 WP-11 会交付一个**假绿 DoD** + **纯信息措辞**的极窄残余，不值当独立 WP。

### Q4 — B4 移出 WP-11 正确，但归属应是 WP-12，不应无限期挂起（CONFIRMED）

- codex：AGENTS.md 属 #3 禁区期间，从 WP-11 移出 B4 正确（不能让 WP-11 叠写未裁决的人类改动）；
  但 B4 最合适的归属**不是长期悬空，而是 WP-12**——WP-12 已计划同时改 `AGENTS.md`/模板并明确要求
  流式 `| tee <log>`；若同一处不同时要求 `set -o pipefail` 或读 `${PIPESTATUS[0]}`，新契约会**主动推广
  一个已知会吞真实 rc 的范式**（即便 WP-12 把 rc 降为辅助信号，辅助记录也不应是伪造的 rc）。
- 处置：**#3 解决后**把 B4 并入 WP-12 的同一份协议修改，**不新增文件所有权**（见 §4）。

## 3. 关闭机制（validate_wp_status 无 ABANDONED 态）

WP 状态机（`validate_wp_status.py:13-24`）无 `ABANDONED`；`OPTIONAL_TOP_LEVEL={qoder_security,plan_id}`
（`:54`）不允许在 status.json 加自定义「关闭原因」字段。故关闭按如下可逆组合落地：

1. `WP-11.status.json`：`state` `APPROVED → DRAFT`（撤回冻结；DRAFT 是最接近的合法非活跃态）。
   —— 已验 `STATUS_VALID`（`PYTHONPATH=src python3.11 -m agentic_loop.validate_wp_status`，rc=0）。
2. `PLAN-01.status.json`：从 `work_packages` **移除 WP-11 条目**（22→21）。依据 §4.3「every listed WP
   must reach `MERGED`」——关闭的 WP 不应再被要求 MERGED，否则永久阻塞收敛。
3. `PLAN-01.status.json`：`WP-12.depends_on` `['WP-11'] → []`（否则 dangling depends_on → PLAN_INVALID；
   codex Q5 亦明示「若关闭 WP-11 须移除 WP-12 对它的依赖」）。`WP-13.depends_on=['WP-12']` 保持不变。
4. **本文件**（`WP-11-closure.md`）作为独立、Git 可见的关闭理由记录（§10 durable documentation）。

## 4. 遗留项去向

| 遗留项 | 去向 | 依赖 |
|--------|------|------|
| **B1 真实残余**（`preflight.sh:111` 对「另一 primary repo 的有效 status」误报 `must be tracked`；已 rc=2 拒绝，仅信息不精确） | 登记为**低危已知缺陷**（诊断信息质量，非 fail-open）。建议并入后续任何触碰 preflight 的 WP，或与 WP-13 rev3 quality-gate 侧 tracked 兜底（codex Q1）对称收口；**不单独立 WP**（避免假绿 DoD 重演）。若要修，DoD 须用「另一 primary repo + 通过全部前置检查的有效 status」构造真残余，并加删掉修复即变红的差分证明（codex Q3 修法要求）。 | 无（可随时排期；低优先） |
| **B4**（`AGENTS.md §4.1` 派发范式 `pipefail`/`${PIPESTATUS[0]}`） | **并入 WP-12** 的 AGENTS.md/模板协议修改（WP-12 已计划改 AGENTS.md + 要求 `\| tee <log>`），**不新增文件所有权**。 | **#3 先裁决**（AGENTS.md 归属）；WP-12 re-freeze 时纳入 |

## 5. 验证证据（2026-09-21，主仓，只读核验）

- `validate_wp_status WP-11.status.json` → `STATUS_VALID`，rc=0（DRAFT 合法）。
- `agentic plan check PLAN-01.status.json` → `state=ACTIVE`；work_packages 列 **21** 个（WP-11 不在列）；
  `WP-12 state=APPROVED`、`WP-13 state=APPROVED`；`not converged (11 WP(s) pending)`（在飞 plan 的正常态）；
  无 dangling depends_on、无 PLAN_INVALID。rc=3（=未收敛，非错误）。
- `agentic plan lint PLAN-01.status.json` → WP-11 **已不在 lint 范围**（移除成功）。lint 仍报 `dirty`，
  但全部为**既有历史 status-sync 提交**（WP-01…WP-29，早于 §4.3 提交纪律规则），**本次移除未新增任何
  lint 失败**，且关闭 WP-11 **不做历史重写**（不可逆操作，禁区）。
- `git worktree list` / `git branch --list 'feature/wp11*'` → 无 WP-11 分支/工作树（从未派发）。

## 6. 可逆性

WP-11 `APPROVED` 冻结态与 rev1/rev2 brief 均在 Git 历史留痕（rev1 冻结提交、rev2 草稿 `5abcc41`）。
本次关闭是**前向**改动（status→DRAFT + plan 移除 + 本记录），未删除任何 brief/历史；如需复活 WP-11，
从历史恢复 status 的 APPROVED 态并重新加回 work_packages 即可。B1 残余与 B4 的实质内容在 §4 完整登记，
不因关闭丢失。
