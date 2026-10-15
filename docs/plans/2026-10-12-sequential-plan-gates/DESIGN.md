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

**R3 两个 WP 顺序执行；dogfood 只能在合入之后做（rev2 修正）。**
WP-02（G1）先落地，WP-03（G2）后落地。本迭代自己是顺序型形态的计划，
所以它**本身**就是 R1 的端到端标的。

但 rev1 在这里写错了，说「WP-02 完成后本迭代自己的收敛就应当能用
`agentic finalize` 正常 stamp」。实测否证（详见 §2b 第 3 条）：
`agentic` 执行的是**主仓 checkout** 工作区里的 wrapper，不是 WP worktree
里的改动版。所以在 WP-02 合入主仓之前，dogfood 跑的仍是旧脚本，
**验证不了**本 WP 的修复 —— 用它当验收证据是循环论证。

修正后的口径：WP-02 的 DoD **不含**自验证；端到端验证由编排者在 WP-02
合入 `main` 之后单独执行，作为本计划收敛的一部分而非 WP 的交付物。

## 2b. r1 二签指认并经编排者实测核实的缺陷（rev2 已闭合）

二签 r1 作废（裁决留到最后、预算先耗尽，无 `CODEX_DECISION` 标记，收据判
`INVALID`；产物归档于 `.agentic/seq-gates-brief-consult-r1-attempt1-void/`），
但它在 555 秒里给出四条实质发现。编排者逐条实测：三条成立、一条不成立，
并追查了它提出但未查完的第五条。

| # | 顾问指认 | 编排者实测结论 | rev2 闭合方式 |
|---|---|---|---|
| 1 | WP-02 的 S1 可能让 `merged_commit = base_tip` 假绿 | **成立**。顺序型下两 tip 解析自同名分支，两种实现产出相同；原 M-2 要求「改成 `base_tip` 之外的值」恰好绕开了最自然的错误写法 | 新增 INV-1b + S1b + M-2b |
| 2 | WP-03 的 E3 只对 `approver` 做空白攻击 | **成立**。`justification` / `reviewed_at` 的非空约束无承重测试 | E3 扩到 10 形态 + M-2b 三条逐字段 |
| 3 | 自验证（dogfood）可能走不通 | **成立，且比指认更确切**。`cli.resolve_wrapper` 优先主仓 `scripts/agentic/`（本仓库无该目录）故用包内副本；而 `agentic` 的 `agentic_loop` 包解析到主仓 checkout 的 `src/agentic_loop`（editable），与主仓内那份 wrapper sha256 一致 | R3 改写（见上）+ WP-02 附注明令不得把自验证写进交付证据 |
| 4 | WP-02 范围自相矛盾（要求 `wrapper_sync` 绿却只许改 bundled） | **不成立**。该测试要求 canonical 与 bundled 逐字节相同，但本仓库无 `scripts/agentic/`，故 `pytest.skip` | WP-02 附注记录实测事实 + 若未 skip 则判 BLOCKED |

**第 5 条（顾问提出但未查完；编排者追查确认，最严重）**：豁免来源无约束。
`plan_cmd.py:471-472` 的 `_resolve_plan_path` 对绝对路径**无条件返回**，
不做主仓归属判断；`plan_cmd.py` 对 `path_is_in_worktree` 的引用数为 **0**。
对比 WP 层 `finalize_merge.sh:160` 明确拒绝 worktree 本地副本
（§36 注释称其为「branch-local working-tree state, not the shared source of
truth」）。即若 WP-03 只校验四字段，**任意路径上一份合法 JSON 就能放行合并**。
**自证**：编排者在上一迭代收敛时，正是用绝对路径对 worktree 副本跑
`agentic plan finalize` 并被接受 —— 当时写入的是合法状态，但同一条路径
同样能送进一份伪造的豁免。rev2 以 INV-3b + E9 三子形态 + M-2c 闭合。

> 方法论记录：r1 虽因预算耗尽而作废，产出的四条发现**仍然有效且已被独立
> 核实**。这说明「作废」是对裁决有效性的判断，不是对内容价值的判断 ——
> 丢掉这些发现去重跑一轮才是浪费。但反过来，**不得**把作废轮的意见当作
> 二签通过：rev2 仍须走 attempt2 取得真正的 `CODEX_DECISION`。

## 2c. r2 二签（有效，REWORK）及 rev3 的闭合

r2 取得有效裁决 `CODEX_DECISION: REWORK`（form=marker，收据
`.agentic/seq-gates-brief-consult-r2.receipt.json`）。prompt 从 6 问压到 3 问
并明确限制探查范围，这一轮没有再被预算耗尽。顾问自述验证范围：
核对了 HEAD、工作区干净状态与四个 SHA-256，查了三处源码现场，**未执行 pytest**
（如实声明，未伪造）。

两条必改，编排者均已实测核实后在 rev3 闭合：

**C1 symlink 旁路（Q1）**。INV-3b 的 rev2 写法不完整：主仓内一个**受跟踪的
symlink** 可指向主仓内**未跟踪**的 JSON；只检查逻辑路径前缀与 `ls-files`
会把 symlink 自身视为已跟踪，却实际读取未审计目标。
**实测确认**：`git add` 一个 symlink 后，`ls-files --error-unmatch` 对 symlink
报「已跟踪」、对其目标报「未跟踪」，而读取 symlink 得到的是那份未跟踪内容。
rev3 把判定顺序**冻结为三步**（先 `resolve(strict=True)` → 再归属 +
`path_is_in_worktree` → 最后用解析后相对路径跑精确 `ls-files`），
E9 增加子形态 4，并新增 M-2d 专打判定顺序。

**C2 S1b 的退化出口过宽且其运行时构造不可实现（Q2）**。rev2 给了「运行时
fixture 或静态断言二选一」的出口，并提议用大小写 / `refs/heads/` 前缀等价
写法构造 tip 差异。**r2 指出该构造不存在，编排者实测确认**：两字段字面相等时
`rev-parse refs/heads/<name>` 必然返回同一提交；且 macOS 文件系统大小写不敏感，
`git branch Main` 直接报「已存在」。rev3 删除该出口，S1b 固定为**强制静态
数据流断言**（须排除注释与 dead code、须定位赋值语句本身、不得退化为全文搜索），
M-2b 改为必须修改实际赋值语句并附红/绿双证，执行者不得跳过或仅以文字理由代替。

三条残余风险（顾问指认，rev3 已写入 WP-03「残余风险」一节）：
tracked ≠ committed、校验与读取之间的 TOCTOU 窗口、`main_repo()` 自身对
repository-selection 环境变量的信任边界。顾问同时澄清 submodule 情形
无需额外用例。

裁决要点：**当前不可冻结、不可派发 WP-02**，须先修订、生成新 rev 与 SHA-256。
rev3 即为此而生，冻结前须再走一轮二签。

## 3. 范围外

- **不改 freeze+finalize 纪律本身的判据**（仍是 1 + 1 + 0 sync）。豁免只在
  `merge` 放行层生效，lint 的报告口径不变。想从根上支持多轮 re-freeze
  （例如允许 N 次 freeze 提交），属另一目的，另立 WP。
- **不回填历史计划的状态文件**。kqff 与 probe-no-degrade 已合入，不追溯改写。
- **不动 `push`**。它仍是硬 `always_stop`，与本迭代无关。
- **WP 层 `git.branch == git.base_branch` 之外的其他 finalize 失败分支**
  （0 候选但分支确实不同、多候选）保持现有 fail-closed 行为。
