# 顺序型计划的收敛闸门 — 迭代设计

迭代 id：`2026-10-12-sequential-plan-gates`
基线：`main` `5a469f2`（probe-no-degrade 单次收敛 + push 后的尖端）
来源：`2026-10-09-developer-probe-no-degrade/DESIGN.md` §5 记录的 G1/G2

## 1. 问题

两处缺口都在 probe-no-degrade 的 WP-01 **双签通过之后**、执行 plan 收敛时被
编排者实测发现。二者都不是那个计划的纪律违规，而是 `agentic` 自身对
**顺序型计划**这一形态支持不全。两处都已用「手工 stamp + 人工合并」绕过，
绕过方式记录在 `8e3a7fe` 的提交信息里 —— 本迭代要让工具自己支持这一形态，
消掉下一次绕过的必要。

### G1 `agentic finalize` 无法 stamp 顺序型 WP

`wrappers/finalize_merge.sh:380` 用

```bash
candidates=$(git ... rev-list --merges --parents "$base_tip" | awk -v t="$wp_tip" '$3==t{print $1}')
```

找「第二父 == WP 分支尖端」的合并提交。`$3` 是第二父，即它只认
**WP 分支被合并进集成分支**所产生的那个合并提交。

但 AGENTS.md §4.3 明确许可顺序型 WP **直接在集成分支上工作**
（「Sequential WPs work on that one branch; only 'parallel lanes' get separate
branches」）。此时 `git.branch == git.base_branch`，`wp_tip == base_tip`，
这样的合并提交**根本不存在** —— 实测候选数 0，脚本报
`cannot uniquely resolve merge commit ... (found 0)` 退出 2。

而 `plan merge` 又要求每个 WP 先为 `MERGED`（`plan_cmd.py:744`
`_require_converged`），于是形成死锁：顺序型 WP 永远无法通过工具 finalize，
计划永远无法收敛。

注意 `:371` 的完整性前置条件（`wp_tip` 必须是 `base_tip` 的祖先）在同分支
情形下**自动成立**（同一提交是自己的祖先），所以它不是阻塞点，阻塞点只在
`:380` 的候选解析。

**plan 层不受影响。** `plan_cmd.py:380` 的 `_resolve_plan_merge_commit` 找的是
「目标分支历史里第二父 == 集成分支尖端」，这个合并提交在 plan 层真实存在
（probe-no-degrade 实测：`agentic plan finalize` 自行解出 `8e3a7fe`，无需手填）。
故 G1 只影响 WP 层。

### G2 `plan lint` 的 freeze+finalize 纪律对多轮计划不可达

`plan_cmd.py:553-556` 要求每个 WP 的状态文件在集成分支上恰好有
1 个 freeze 提交（`--diff-filter=A` 的那次新增）和 1 个 finalize 提交
（blob 内 `state == "MERGED"`），其余一律计为 `sync` 并判 DIRTY；
`cmd_merge`（`:747`）对 DIRTY fail-closed。

纪律本身是对的 —— 它要消灭的「review 同步 / codex 同步」中间提交确实是噪音。
但它与**多轮 re-freeze** 结构性冲突：probe-no-degrade 走了 rev1→rev15 共 15 轮
brief 重冻结，每轮的二签裁决都要落盘到状态文件，累计 27 次 sync 提交。
编排者实测：**已合入的 kqff 计划**跑同一 lint 同样判 DIRTY
（`freeze commit x0; finalize commit x0`），说明这不是某个计划的个例，而是该
纪律对历史与多轮计划普遍不可达。

两条出路在 probe-no-degrade 收敛时被提给用户裁决，用户选择**豁免**
（保留 15 轮收敛记录，不 squash 重写历史）。本迭代把那次一次性人工豁免
变成工具内的、**显式且可审计**的能力。

## 2. 取向

**R1 G1 按分支形态分流，不放宽证据要求。** finalize 检测
`branch == base_branch` 时走顺序型分支：此时 WP 的最终实现提交**就是**它的
集成点，接受 `wp_tip` 自身为 `merged_commit`。并行道形态（`branch != base_branch`）
的解析逻辑**一字不改**，仍必须唯一解析出真实合并提交。

关键不变式：顺序型分支**不得**成为「解析不出合并提交时的兜底」。判别依据必须
是分支身份（两个字段相等），而非「候选数为 0」—— 后者会把并行道的真实故障
（分支未合并、合并提交被 rebase 掉）误判为顺序型并伪造一个 `merged_commit`。
这是本 WP 最重要的一条负面断言。

**R2 G2 做成显式豁免记录，不做开关。** 不加 `--skip-lint` 之类的旁路参数
（那等于把纪律变成可选项，且无审计痕迹）。改为在 plan 状态文件里引入一个
**完整四字段豁免块**，复用仓库已有的 override 形态
（`validate_wp_status.py:191` `_override_dict_is_legal`：`approved == true` +
非空 `approver` + 非空 `justification` + 非空 `reviewed_at`），缺一不可、
fail-closed。`plan lint` 仍然如实报告 DIRTY 与每一条 sync 提交（**不静音**），
但 `plan merge` 在存在合法豁免时放行，并把豁免的 approver/justification
打印到输出里。

plan schema 目前只允许 `title` 一个可选顶层字段（`plan_cmd.py:86`
`OPTIONAL_TOP_LEVEL`），这正是 probe-no-degrade 当时无法把豁免写成结构化字段、
只能写进提交信息的原因。本迭代扩这一个字段，补上那个缺口。

**R3 两个 WP 顺序执行，自身即 dogfood。** WP-02（G1）先落地，WP-03（G2）后落地。
本迭代**自己是顺序型单 WP 形态的计划**（WP 直接在集成分支上工作），所以
WP-02 完成后，本迭代自己的收敛就应当能用 `agentic finalize` 正常 stamp ——
这是对 R1 的真实端到端验证，而非只靠单元测试。若 WP-02 落地后本迭代仍需手工
stamp，说明 R1 没真正修好。

## 3. 范围外

- **不改 freeze+finalize 纪律本身的判据**（仍是 1 + 1 + 0 sync）。豁免只在
  `merge` 放行层生效，lint 的报告口径不变。想从根上支持多轮 re-freeze
  （例如允许 N 次 freeze 提交），属另一目的，另立 WP。
- **不回填历史计划的状态文件**。kqff 与 probe-no-degrade 已合入，不追溯改写。
- **不动 `push`**。它仍是硬 `always_stop`，与本迭代无关。
- **WP 层 `git.branch == git.base_branch` 之外的其他 finalize 失败分支**
  （0 候选但分支确实不同、多候选）保持现有 fail-closed 行为。
