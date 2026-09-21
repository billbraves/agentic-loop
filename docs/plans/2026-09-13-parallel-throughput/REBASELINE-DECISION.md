# 重新基线化决策：收敛已完成成果 + 加固长尾另立迭代

> 编排者 claude ｜ 决策日期 2026-09-21 ｜ 用户已批准（Plan「重新基线化收敛计划」+ 两个分叉裁定）
> 本文件是 `2026-09-13-parallel-throughput` 迭代收敛策略的**权威重新基线化决策**，
> 取代 `CONVERGENCE-PLAN.md` 的 P1-P6（P0 已完成部分仍有效）。
> 执行门控：A1（PLAN-01 收缩）、A4（手动合并进 main）、A6（push）逐个用户批准。

## §1 重新基线化理由

1. **目标漂移**：迭代原目标「加并行」（PLAN.md §4 的 7 个 WP）经 P0-4 对账确认**已实质达成**
   ——WP-01/03 MERGED；WP-02/04/05/06/07 判废弃且各有据（C1 由 `b4733058` 预交付、worktree 隔离由
   `c555daf` 预交付＋WP-19/27 加固、WP-05 分批合并被「一 plan 一合并」模型超越、WP-07 价值转移到
   AGENTS.md/模板）。随后迭代漂移成「修 ~99 个框架自身缺陷」（A 类 36 + B 类 63）的**无界长尾**。
2. **收敛机制自相矛盾**：`agentic plan merge` 在 lint dirty 时硬失败（`plan_cmd.py:746-756`）；
   实测 `plan lint` = dirty 且 **21 个 WP 无一干净**（连 10 个已 MERGED 的都带 7-26 个 status-sync
   提交，如 WP-29=26、WP-28=21＋finalize×3）。lint 规则（AGENTS.md §4.3，约 2026-09-17 采纳）
   **晚于**这些 sync 提交，追溯强制需重写 100+ 历史提交——被 §5 与 §4 禁区禁止。故原 P6
   「plan lint 干净 → plan merge」要求一个**永不可能满足**的前置。
3. **顺序颠倒**：原计划把「修门」（P1 #38 段落门）排在 10 个 WP 已 MERGED 之后，把「信任根重设计」
   （P5 #34）排在收敛之后——即先收敛坏门验证的成果，再修门。

## §2 用户决策（两个分叉，2026-09-21）

- **分叉 1（收敛集边界）= 最小集**：仅收敛 10 个已 MERGED 的 WP；全部 11 个 pending + 缺陷长尾
  迁入全新加固迭代。
- **分叉 2（#38 坏门风险）= 带文档化残余风险收敛**：10 个 WP 的代码已过 pytest 全量 + review/consult
  双签；#38 是 brief **段落门**（dispatch 期 lint）缺口，非代码正确性缺口。据实记录残余风险后收敛，
  段落门修复（#38）与已合并 WP 的 brief 复验放目标 B。

## §3 收敛集划分

**保留集（10，MERGED，随目标 A 进 main）**：
WP-01, WP-03, WP-08, WP-19, WP-21, WP-22, WP-24, WP-27, WP-28, WP-29

**下云集（11 → 目标 B 新加固迭代）**：

| WP | 当前 state | 去向（目标 B） |
|---|---|---|
| WP-09 | APPROVED | 重估前提（A1/A3 是否已被顺带修）→ re-freeze 或关账 |
| WP-10 | APPROVED | 重估（A2 模板默认值）→ re-freeze 或关账 |
| WP-12 | APPROVED | 重估（B2/B6/B3 health 语义）→ re-freeze 或关账 |
| WP-13 | APPROVED | rev3 草稿已存在（`5edac94`）；重估 + §5 契约表述修正后 re-freeze |
| WP-14 | APPROVED | 重估（C2 evidence.tests 文档）→ re-freeze 或关账 |
| WP-15 | DRAFT | 立 brief 或关账（无 evidence.brief.path） |
| WP-23 | DRAFT | 立 brief（#3 A26 并入 resolve_paths 环境净化） |
| WP-17 | BLOCKED | 解 BLOCKED，绑定 #34 独立性判据重设计 |
| WP-18 | CHANGES_REQUESTED | 返工（#53 DispatchProof 信任根） |
| WP-25 | CHANGES_REQUESTED | 返工 rev5（#12 B38/B39），re-freeze=3 须停手复核＋批准 |
| WP-26 | CHANGES_REQUESTED | 返工 rev5（#18 B35/B36），re-freeze=3 须停手复核＋批准 |

下云 WP 的 status 文件、分支、工作树**原样留档**（§4 禁区「不清理工作树」仍生效），由目标 B 接管。

## §4 结构性阻断的显式决策（目标 C）

- **C1 lint 阻断 = 「手动 `--no-ff` + `plan finalize`」治理例外**：
  机制依据——`cmd_finalize`（`plan_cmd.py:805-903`）**不跑 lint**，只校验「所有声明 WP=MERGED」
  （`_require_converged`）+「集成分支确已并入 main」（base_tip 是 target_tip 祖先）+「合并提交唯一可解析」。
  故把 PLAN-01 收缩到 10 个 MERGED 后，走用户批准的手动 `git merge --no-ff` + `agentic plan finalize`
  即可收敛，**无需改 plan_cmd 代码、无需重写历史**。手动合并步替代 `plan merge` 的
  `local_merge_no_ff` autonomy 门，由用户批准承担治理授权。
- **C2 #38 坏门风险 = 带文档化残余风险收敛**（见 §2 分叉 2）。

## §5 目标 B 新加固迭代章程概要

- **入口**：从收敛后 main 切新 base_branch，新建迭代目录（如 `docs/plans/2026-09-22-framework-hardening/`）。
- **信任根优先排序**：头两个 WP = **#34 独立性判据重设计**（A5/A8/A11 链，须 codex consult）
  + **#38 brief 段落门修复**（B47+B63，dispatch_lint 改读 evidence.brief.path）。
  其后按依赖排：P1 门禁批（#11/#32、#39、#27、#42、#23）、11 个下云 WP 重估、
  P4 补钉（#41/#31/#14、#46/#33/#2）、P5 流程改造（#22、A4/A9/A10）。
- **终止判据（反芝诺）**：「所有 convergence-blocking + safety-critical 缺陷已修；hardening 缺陷
  triage 进 backlog 且有 owner；连续 2 次派发未发现新缺陷」即达可收敛。
- **#34 派 owner + 排期**（终结「无任务条目」）；补一条修正 §4.3 sync-commit 违规根因的 WP
  （+ 可选 legacy-dirty 豁免），使未来收敛不再需手动例外。

## §6 收敛执行序（目标 A，详见 Plan「重新基线化收敛计划」）

A0（本文件）→ A1（收缩 PLAN-01，用户批准）→ A2（merge-tree 干run 复核零冲突）→
A3（回并 main→集成分支 + P0-5 §4.1-4.6 全量验证）→ A4（state→READY_TO_MERGE + 手动合并→main，
用户批准）→ A5（plan finalize 盖章）→ A6（单次 push，用户批准）。

## §7 风险与前提

- **N3 已被 P0-5 证伪**：`git merge-tree --write-tree` 实测 main→集成分支零文本冲突；唯一双边文件
  `gate/__init__.py` 区域不重叠、clean 合并。残余仅语义风险 R1（main +1305 codex 重写 vs 集成分支
  gate/wrappers），靠 A3 全量重测（含 `tests/test_codex_*.py`）兜底。
- **main 未移动**：2026-09-21 实测 main 尖端仍 `2c29725`（与 P0-5 一致），merge-base `0ef592e`；
  集成分支尖端 `7e40881`（领先 main 220）。A2 重跑干run 复核（集成分支尖端已自 P0-5 的 `4d6b8b6` 前移）。
- **A2 若干run 出现冲突** → 暂停并按 P0-5 §3 次序上报用户，不擅自解语义冲突。

## §8 证据索引

- `plan_cmd.py:746-756`（cmd_merge dirty-lint 硬失败）、`:805-903`（cmd_finalize 不跑 lint）
- `agentic plan lint`（2026-09-21 实测：21 WP 全 dirty）
- `CONVERGENCE-P0-4-plan-reconciliation.md`（WP-02/04/05/06/07 废弃判定 + 证据）
- `CONVERGENCE-P0-5-backmerge-runbook.md`（merge-tree 零冲突 + N3 证伪 + §4 验证步骤）
- `PLAN.md §4/§5`（原始 7-WP 目标）
- git 实测（2026-09-21）：main=2c29725、integration=7e40881、merge-base=0ef592e、45/220 分叉
