# WP-03: plan merge 的显式豁免记录（多轮 re-freeze 计划）

> rev7 re-freeze 日期 2026-10-14 | 编排者 Kiro（DSH 会话）| 执行者 kimi。
> rev6 的 literal-pathspec 修复已获有效实现二签 ACCEPT；随后端到端 dogfood 发现首次引入计划文件时的 bootstrap deadlock。rev7 只修正来源信任与实际 merge checkout 的部署模型，不改变 lint 判据或豁免形态。
> 所属 Plan：PLAN-01（集成到 `plan/2026-10-12-sequential-plan-gates`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（规则见「Re-freeze 规则」一节）。

## Re-freeze 规则（编排者冻结前自检）

- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。
- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。

## 目标（一句话）

让多轮 re-freeze 的计划能通过一个**完整四字段、fail-closed、可审计**的豁免块
通过 `plan merge`，同时 `plan lint` 的报告口径与纪律判据一字不改。

## 背景（为何存在这个缺口）

`plan_cmd.py:553-556` 要求每个 WP 的状态文件在集成分支上恰好 1 次 freeze
（`--diff-filter=A`）+ 1 次 finalize（blob 内 `state == "MERGED"`），其余计为
`sync` 并判 DIRTY；`cmd_merge`（`:747`）对 DIRTY fail-closed。

纪律要消灭的「review 同步 / codex 同步」中间提交确实是噪音，**判据本身是对的**。
但它与多轮 re-freeze 结构性冲突：probe-no-degrade 走了 rev1→rev15 共 15 轮
brief 重冻结，每轮二签裁决都要落盘状态文件，累计 **27 次** sync 提交。

编排者实测的关键事实：**已合入的 kqff 计划**跑同一 lint 同样判 DIRTY
（`freeze commit x0; finalize commit x0`）。即这不是某个计划的个例，而是该纪律
对历史与多轮计划**普遍不可达**。

probe-no-degrade 收敛时用户裁决**豁免**（保留 15 轮收敛记录，不 squash 重写
历史）。当时无法把豁免写成结构化字段 —— plan schema 只允许 `title` 一个可选
顶层字段（`plan_cmd.py:86` `OPTIONAL_TOP_LEVEL`），加字段会直接
`unknown top-level fields` 校验失败 —— 只能写进 `8e3a7fe` 的提交信息。
本 WP 补上那个缺口。

## 取向（冻结）

**F1 豁免是记录，不是开关。** 不得引入 `--skip-lint` / `--force` 之类命令行
旁路参数，也不得读环境变量来放行（那等于把纪律变成可选项且无审计痕迹）。
豁免必须落在**计划状态文件**里，随 Git 可见、可追溯。

**F2 复用仓库既有的四字段 override 形态。** 字段语义与
`validate_wp_status.py:191` `_override_dict_is_legal` 完全一致：
`approved === true`（严格布尔真，不接受 `"true"` 字符串或 `1`）、
非空 `approver`、非空 `justification`、非空 `reviewed_at`。缺一不可，
**fail-closed**。不得新造一套更松的形态。

**F3 lint 口径一字不改。** `plan lint` 仍如实报 DIRTY 并逐条列出 sync 提交，
**不得**因存在豁免而静音、降级为 warning 或隐藏条目。豁免只在 `merge` 的
放行层生效。

**F4 放行必须留痕。** `plan merge` 凭豁免放行时，必须把豁免的 `approver` 与
`justification` 打印到输出（供人工复核与日志留存），不得静默通过。

**F5 其余 fail-closed 条件全部保留。** `state == READY_TO_MERGE`、
`_require_converged`（每个 WP 必须 `MERGED`）、autonomy 闸门、
必须在目标分支上、已合并则拒绝重复合并 —— 一律不受豁免影响。
**豁免只豁免 lint 这一项。**

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/plan_cmd.py`
  - `docs/agentic/templates/PLAN.json`
  - `tests/test_plan_lint_exemption.py`（新增）
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/wrappers/finalize_merge.sh`（WP-02 的地盘）
  - `src/agentic_loop/validate_wp_status.py`（只读其形态，不改它）
  - `src/agentic_loop/gate/__init__.py`（不修改；rev7 不再以
    `path_is_in_worktree` 拒绝所有 linked worktree，而是验证注册 worktree、branch、
    canonical path 与 committed blob）
  - `src/agentic_loop/wrappers/codex_merge_gate.sh`
  - `src/agentic_loop/autonomy.py`
  - `.agentic/config.toml`
  - `uv.lock`
  - 任何 `docs/plans/2026-10-09-developer-probe-no-degrade/**`（历史计划不回填）
  - 任何 `docs/plans/2026-09-22-kimi-quota-flash-fallback/**`（同上）
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

## 输入

- 依赖的上游 WP 产出：WP-02 已完成实现、独立 review ACCEPT、实现二签 ACCEPT，
  当前为 `APPROVED_FOR_MERGE`；其实现提交 `70a5990` 已在同一集成分支上。
  **不再要求 WP-02 先达到 `MERGED`**：实测闭环证明 WP-02 的标准 finalize 要求
  主 checkout 的状态副本，而 PLAN-01 的 commit-discipline lint 又会因多轮状态同步
  判 DIRTY；解决该 DIRTY 正是本 WP 的目标。若仍要求 WP-02 先 MERGED，WP-02 与
  WP-03 将互相等待。执行顺序冻结为：先实现并双签 WP-03 → 对 WP-02/WP-03 依次
  finalize → 用本 WP 的结构化豁免通过 plan merge。
- 参考文档：本迭代 `DESIGN.md` §1 G2 / §2 R2；AGENTS.md §4.3
- 现场：`src/agentic_loop/plan_cmd.py:76-86`（schema 字段集）、
  `:518-570`（commit-discipline lint）、`:719-802`（`cmd_merge`）
- 形态权威源：`src/agentic_loop/validate_wp_status.py:191-213`
  （`_override_dict_is_legal`，四字段严格判定）
- 既有 lint 测试范式：`tests/test_plan.py:256`（`test_lint_clean`）、
  `:264`（`test_lint_detects_sync_commit`）

## 交付物清单

- [ ] `src/agentic_loop/plan_cmd.py` — 扩 `OPTIONAL_TOP_LEVEL` + 豁免判定 + merge 放行与留痕
- [ ] `docs/agentic/templates/PLAN.json` — 模板补注释说明该可选块（不预置生效值）
- [ ] `tests/test_plan_lint_exemption.py` — E0–E15（编号允许跳号），含首次引入与 dirty physical-primary 的真实 linked-worktree 形态

## 验收不变式（标的）

以下是本 WP 的验收**标的**；E 编号只是破口清单，不得取代不变式。

**INV-1（合法豁免放行）**：计划状态含**完整四字段**豁免块且其余条件均满足时，
`plan merge` 在 lint DIRTY 的情况下仍执行 `--no-ff` 合并并退出 0。

**INV-2（lint 不被静音）**：无论豁免是否存在，`plan lint` 的 stdout 逐字节一致 ——
仍报 DIRTY、仍逐条列出全部 sync 提交。豁免不改变 lint 的任何输出。

**INV-3（残缺豁免 fail-closed）**：四字段缺任意一项、`approved` 不是严格布尔
`true`（含 `"true"` / `1` / `"yes"`）、或任一字符串字段为空/纯空白时，
`plan merge` **必须**仍然拒绝（DIRTY 不放行）。
**三个字符串字段的非空约束必须各自承重** —— 即 `approver`、`justification`、
`reviewed_at` 每一个都要有自己的空白攻击用例。r1 二签指认：rev1 的 E3 只对
`approver` 做空白攻击，于是「删掉 `justification` 与 `reviewed_at` 的非空校验」
不会让任何用例转红，那两条约束不承重。

**INV-3b（豁免来源必须可审计且可首次引入）**：合法四字段只证明“形状完整”。`plan merge` 凭豁免放行时，实际解析到内存的计划文件字节必须同时满足：

1. 文件所在根目录必须出现在 `git worktree list --porcelain`，且与主仓共享同一 resolved `git-common-dir`；
2. 该 worktree 当前分支严格等于计划声明的 `git.base_branch`；
3. 文件路径严格等于配置的 iterations 目录下 `<iteration_id>/<plan_id>.status.json`，不得是 symlink、别名、仓库外路径或 target worktree 副本；
4. **本次解析使用的原始字节**与 `git show <base_branch>:<canonical-path>` 的 committed blob 逐字节一致。

该模型把审计权威绑定到 integration branch 的 committed blob，而不是 physical-primary checkout 的 index。它既拒绝 untracked、tracked-but-dirty、symlink、outside 与错误 worktree，又允许计划文件第一次随 integration branch 引入：target 分支在 merge 前无需预先提交同一文件。

**INV-3c（读取与判定同一份字节）**：来源判断必须比较 `_load_and_validate` 实际解析的那份原始字节，不得在解析后重新读取路径来代替；否则“先读恶意字节、再换回 committed 字节”会让来源校验通过但内存仍持有恶意豁免。

**INV-3d（refs 仓库与 mutation checkout 分离）**：只读 refs/lint/WP blob 查询可继续使用 `main_repo()` 所代表的 shared common repo；但 current-branch 检查、冲突检测和真实 `git merge --no-ff` 必须在调用者的 `current_worktree()` 执行。该 current worktree 必须与 main repo 共享同一 `git-common-dir`，且当前分支严格等于 `target_branch`。不得要求 physical-primary checkout 自身位于 target branch，也不得修改其 index/工作区。

**端到端实证（rev7 触发原因）**：rev6 的 E1 在 `main` 上先单独提交 PLAN 状态，才执行 merge；真实 PLAN-01 的计划文件只存在于 integration branch。编排者在临时仓复现：把同内容文件预置到 target index 后，`ls-files --error-unmatch` 虽返回 0，但 `git merge --no-ff` 以“本地修改将被覆盖”/“Entry not uptodate”退出 2/128；普通 add、intent-to-add、skip-worktree 均不能闭环。physical-primary 同时处于另一分支且有大量用户改动，因此把 mutation repo 固定为它也不可部署。

**INV-4（豁免范围最小）**：豁免只作用于 commit-discipline lint。
`state != READY_TO_MERGE`、任一 WP 未 `MERGED`、不在目标分支、已合并、
autonomy STOP —— 这些条件在**有**合法豁免时仍然各自 fail-closed。

**INV-5（放行留痕）**：凭豁免放行时，输出必须包含该豁免的 `approver` 与
`justification` 文本。

**INV-6（无旁路）**：不存在任何命令行参数或环境变量能跳过 lint。
源码中不得出现 `--skip-lint` / `--force-merge` 之类旁路，也不得读
`AGENTIC_SKIP_LINT` 之类环境变量来放行。

**INV-7（干净计划零回归）**：lint 本就 clean 的计划，有无豁免块行为完全一致。

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」中的验收测试要求同义，非另一份口径。

每一份 WP 的每条负面断言都必须提供 oracle 校验四项证据：

1. **正向可达性对照**：在同一 fixture 上做一次不带注入/变异的正向运行，
   必须到达终点，证明前置条件确实可达终点。
2. **原因特异 witness**：负向运行必须给出原因特异的 witness（异常标记、
   状态或精确事件），证明失败被正确归因。
3. **代表性禁止变异转红**：至少一个代表性禁止变异（如改掉锚点标题、
   删去关键守卫）必须使测试转红。
4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，
   不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。变异必须施加于判据
   真实的输入面（文件字节 / 进程边界 / 外部状态），不得只改判据已持有的内存表示。
   判别方式：把被修的缺陷还原成原状，该用例必须转红；仍绿则该用例不承重。
   同类输入面的等价载体（如临时副本）满足本项；若变异会写到被判据保护的制品
   本身，须优先选用不写该制品的等价载体。

注意：第 1 项证明「前置可达」，第 2 项证明「失败归因」，
**两者不能互相替代**——「无注入时能到终点」并不排除「带注入时死在别处」。

### 具名用例（破口清单）

每条都在临时 git 仓库里构造真实提交图与真实 sync 提交。

- **E0 `[dirty-no-exemption-must-fail]`**（正向可达性对照的反面基准，
  oracle 第 2 项）→ 现状基准。DIRTY 且**无**豁免块，断言 `plan merge` 退出非 0
  且 stderr 含 `status-sync commits present`（原因特异 witness），
  且目标分支 **tip 未变**（没有发生合并）。
- **E1 `[dirty-with-valid-exemption]`** → INV-1。同一 fixture 加完整四字段豁免，
  断言退出 0、目标分支产生一个 `--no-ff` 合并提交。
- **E2 `[lint-output-unchanged]`** → INV-2。对同一计划分别在有/无豁免下跑
  `plan lint`，断言两次 stdout **完全相同**且都含 DIRTY 与全部 sync 条目。
- **E3 `[partial-exemption-matrix]`** → INV-3，**本 WP 的决定性用例**。
  参数化至少 **10** 种残缺形态，逐一独立参数化（不得合并成一条）：
  缺 `approved`、缺 `approver`、缺 `justification`、缺 `reviewed_at`、
  `approved=false`、`approved="true"`（字符串）、`approved=1`（整数）、
  **`approver="   "`（纯空白）、`justification="   "`（纯空白）、
  `reviewed_at="   "`（纯空白）**。每种都断言退出非 0 且目标分支 tip 未变。
  后三条缺一不可 —— 它们各自钉住一个字符串字段的非空约束（r1 二签指认 rev1
  只测了 `approver` 一个，另两条不承重）。
- **E9 `[exemption-source-must-be-base-committed]`** → INV-3b/3c，参数化至少五个拒绝形态，每种都断言原因特异的 untrusted failure 且 target tip 不变：target worktree 副本、仓库外路径、integration worktree 内未跟踪文件、canonical path 的 symlink、以及 committed 后被工作区修改的文件。正向对照必须从 integration worktree 的 canonical committed 文件读取并放行。
- **E13 `[first-introduction-bootstrap]`** → INV-1/3b。真实 common repo + 两个 linked worktree：PLAN 文件在 target branch/history/index 中完全不存在，只在 integration branch committed；从 target worktree 调用 `cmd_merge(integration_plan_path)` 必须成功产生唯一 `--no-ff` merge。不得先在 target 提交或 stage PLAN 文件。
- **E14 `[physical-primary-may-be-dirty-and-off-target]`** → INV-3d。physical-primary 停在非 target 分支并带无关 dirty 文件；另一个 linked worktree 检出 target。从 target worktree调用 merge 必须成功，physical-primary 的 HEAD/index/dirty bytes 前后完全不变。
- **E15 `[loaded-bytes-are-bound]`** → INV-3c。测试双读攻击：若来源 helper 尝试重新读路径，则第二次提供 committed 字节，而首次解析的是带伪造豁免的不同字节；必须拒绝或确保 helper 只接收首次加载的 raw bytes，绝不能合并。

- **E4 `[exemption-does-not-waive-convergence]`** → INV-4。有合法豁免但某个
  WP 仍是 `APPROVED_FOR_MERGE`（非 `MERGED`），断言退出非 0 且 witness 指向
  convergence 而非 lint。
- **E5 `[exemption-does-not-waive-state]`** → INV-4。有合法豁免但计划
  `state == ACTIVE`，断言退出非 0 且 witness 指向 state。
- **E6 `[exemption-logged]`** → INV-5。E1 的输出必须含豁免的 `approver` 与
  `justification` 原文。
- **E7 `[no-bypass-flag]`** → INV-6。源码静态断言：`plan_cmd.py` 不含
  `skip-lint` / `skip_lint` / `force-merge` / `force_merge` 等旁路标识，
  且不读任何 `*SKIP*LINT*` 环境变量。
- **E8 `[clean-plan-unaffected]`** → INV-7。lint 本就 clean 的计划，
  有/无豁免两种情况都退出 0 且行为一致。
- **E10 `[exemption-does-not-waive-autonomy]`** → INV-4。DIRTY + 合法且可信来源的
  豁免，但 `local_merge_no_ff` autonomy 返回 STOP 且没有单步人工批准。断言退出
  `RC_STOP`、witness 指向 autonomy、目标分支 tip 未变。不得因豁免提前返回成功。
- **E11 `[exemption-does-not-waive-target-branch]`** → INV-4。DIRTY + 合法且可信来源
  的豁免，所有 WP 已 `MERGED`，但当前分支不是 `git.target_branch`。断言退出
  `RC_FAIL`、witness 精确包含 `must run on target branch`、目标分支 tip 未变。
  该闸门位于现有 lint 拒绝层之后，是最容易被“豁免即 return 0”跳过的一面。
- **E12 `[exemption-does-not-waive-already-merged]`** → INV-4。DIRTY + 合法且可信来源
  的豁免，当前分支正确，但 integration branch 已是 target 的祖先。断言退出
  `RC_FAIL`、witness 精确包含 `already merged`，且不得产生第二个合并提交。
  该闸门同样位于现有 lint 拒绝层之后，必须单独承重。

### 必须保持绿的集合（零回归）

```
pytest tests/test_plan.py tests/test_plan_lanes.py -q
```

WP-02 新增的 `tests/test_finalize_merge_sequential.py` 也必须保持绿。

### 承重自检（DoD 必做，报告须附逐条结果）

按 oracle 第 4 项，变异须按判据自身组成步骤生成。至少包含：

- **M-1**：把豁免判定由「四字段齐全」改成「只要 `exemption` 键存在」
  → **E3 必须转红**（至少 `approved=false` 与纯空白两种形态）。
- **M-2**：把 `approved is True` 改成真值判断（如 Python 的 `if approved:`）
  → **E3 的 `approved="true"` 与 `approved=1` 两例必须转红**。
- **M-2b**：**逐字段**去掉非空校验，三条分别施加、分别验证：
  去掉 `approver` 非空 → E3`[approver-blank]` 转红；
  去掉 `justification` 非空 → E3`[justification-blank]` 转红；
  去掉 `reviewed_at` 非空 → E3`[reviewed_at-blank]` 转红。
  三条必须**各自**转红。若某条去掉后全绿，说明该字段的约束不承重，
  **判 BLOCKED** 并在报告中说明，不得以「另两个字段已覆盖」作为通过理由。
- **M-2c**：去掉 committed-blob 来源校验 → E9 的 untracked/dirty/symlink 形态必须转红。
- **M-2d**：只比较重新读取的路径字节，不比较 loader 实际解析的 raw bytes → E15 必须转红。
- **M-2e**（保留 rev6 历史证据）：rev6 删除 `--literal-pathspecs` 时 E9 pathspec 形态真实转红；rev7 不再调用 `ls-files`，该变异标记为 SUPERSEDED_BY_EXACT_BLOB，不伪称继续承重。
- **M-2f**：把 current-branch/merge repo 从 `current_worktree()` 退回 `main_repo()` → E14 必须转红，且 physical-primary 不得发生任何变化。
- **M-2g**：在 E13 fixture 中先把 PLAN 文件提交或 stage 到 target → fixture 自证失败（测试必须拒绝这种前置），防止再次用错误形态获得假绿。
- **M-3**：让豁免同时抑制 lint 的 stdout → **E2 必须转红**。
- **M-4**：让豁免顺带跳过 `_require_converged` → **E4 必须转红**。
- **M-4b**：让合法豁免在 autonomy 检查前直接返回成功 → **E10 必须转红**。
- **M-4c**：让合法豁免在 lint DIRTY 分支内直接返回成功、从而不执行后续目标分支
  检查 → **E11 必须转红**。
- **M-4d**：让合法豁免在 lint DIRTY 分支内直接返回成功、从而不执行后续
  already-merged 检查 → **E12 必须转红**。M-4c/M-4d 可共享同一错误变异，
  但两条用例必须分别转红并提供各自 witness；不得以一条覆盖另一条。
- **M-5**：去掉放行时的 approver/justification 打印 → **E6 必须转红**。
- **M-6**：把豁免块加进 `REQUIRED_TOP_LEVEL` 而非 `OPTIONAL_TOP_LEVEL`
  → 既有 `tests/test_plan.py` 必须转红（证明未破坏既有计划的 schema 兼容）。

变异施加于**文件字节**，不得只改内存表示。锚点须在文件内唯一；
不唯一时须声明 `occurrence` 序号。

## 完成定义（DoD）

- [ ] 交付物逐项就绪
- [ ] E0-E15 全绿（编号允许跳号；E3 的 **10** 种形态、E9 的 **5** 个拒绝形态均逐一参数化，
      不得合并成一条）
- [ ] M-1 ~ M-6 + M-2f/M-2g + M-4b/M-4c/M-4d 逐条红证齐备（含 M-2b 的三条逐字段、
      M-2c committed-blob、M-2d loaded-bytes、M-2f current-worktree、M-2g bootstrap fixture，以及 autonomy/target/already-merged
      三个独立闸门；含还原回绿），报告附逐条结果
- [ ] 「必须保持绿的集合」全绿
- [ ] 全量 `python3.11 -m pytest tests -q` 不低于基线（基线须在报告中实测记录）
- [ ] `agentic quality-gate <status.json>` 全绿
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] commit message 符合规范

## 残余风险

rev6 声明的 `tracked-but-dirty` 与“解析后重新读取”的 TOCTOU 风险在 rev7 通过 loaded raw bytes == base committed blob 一并闭合。仍保留两项：

1. **判定后 refs/worktree 并发变化**：来源字节通过后，其他进程仍可能移动 branch ref 或切换 worktree。真实 merge 会基于执行时 Git 状态继续 fail-closed，但本 WP 不引入跨整个命令的全局事务锁。
2. **`main_repo()`/`current_worktree()` 仓库选择信任边界**：rev7 要求两者 resolved common-dir 相同，但 repository-selection 环境变量的更上层净化仍由既有 resolver/gate 边界负责，不在本 WP 重写。

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

> 若需偏离默认（如生产写入），须编排者 + 独立顾问双重审核并在此记录授权原因。

## 附注

- **已知陷阱 1（最危险）**：这个 WP 的本质是**给一条 fail-closed 闸门开口子**。
  最容易写出的错误实现是「`exemption` 键存在即放行」，它能让 E1 通过、
  看起来修好了，但等于彻底废掉纪律。INV-3 + E3 十形态 + M-1/M-2 专钉这一点。
  实现时请直接复用 `_override_dict_is_legal` 的判定强度，不要自己写宽松版本。
- **已知陷阱 2**：`approved` 必须是**严格布尔真**。Python 里
  `if override.get("approved"):` 会让字符串 `"false"` 也为真 —— 这是真实事故形态，
  M-2 专测它。`validate_wp_status.py:202` 用的是 `is not True` 判定，照抄这个强度。
- **已知陷阱 3**：豁免放行**不得**写进 `plan finalize`。finalize 本就不跑 lint
  （`cmd_finalize` 无 `_lint_report` 调用），在那里加豁免逻辑是无效代码且会误导
  后来者以为 finalize 也受 lint 管。
- **已知陷阱 4（rev7 bootstrap）**：不得再用 physical-primary index 的 `ls-files` 作为豁免权威。权威是 integration branch 的 canonical committed blob，且比较对象必须是 loader 首次解析的 raw bytes。
- **已知陷阱 5（mutation checkout）**：`main_repo()` 是 shared refs/common-repo 定位，不等于当前应被 mutation 的 checkout。真实 merge、current branch 与 conflict 查询必须在 `current_worktree()`，并先证明 shared common-dir 相同。
- **不得扩大作用面**：`plan check` / `plan lint` 的 read-only refs 语义与 `plan finalize` 的现有路径可用性保持不变；rev7 只调整 DIRTY exemption 来源校验与 `cmd_merge` 的 mutation checkout。

- **范围外（明确不做）**：不从根上支持多轮 re-freeze（例如允许 N 次 freeze
  提交）。那会改变纪律判据本身，属另一目的，另立 WP。本 WP 只加「显式豁免」。
- **历史计划不回填**：kqff 与 probe-no-degrade 已合入 `main`，不追溯改写其
  状态文件。本 WP 的能力只对后续计划生效。
- 口径权威源引用：`src/agentic_loop/plan_cmd.py:86`（`OPTIONAL_TOP_LEVEL`）、
  `:553-556`（1+1+0 判据）、`:747`（merge 的 lint fail-closed）；
  `src/agentic_loop/validate_wp_status.py:191-213`（四字段 override 形态权威源）。

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

本段与上文「范围」一节中的 allowed_paths / forbidden_paths 完全同义，
非另一份口径：只能改 allowed_paths 白名单内的路径，绝不能碰
forbidden_paths 黑名单；owner 边界对齐 CODEOWNERS，不跨 owner 写入。

## Completion definition

本段与上文「完成定义（DoD）」一节同义，非另一份口径：交付物逐项就绪、
验收测试全绿、无 forbidden_paths / 跨 owner 写入、无生产写入/网络/通知/
推送，commit message 符合规范。
