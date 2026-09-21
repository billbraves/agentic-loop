# 收敛计划：2026-09-13-parallel-throughput 迭代收敛轮

> 编排者 claude ｜ 落盘日期 2026-09-20 ｜ 用户已批准启动（2026-09-20「好的，启动」+「安排好计划，今晚10点后错峰执行」）。
> P0 已批准批次安排于 2026-09-20 22:00（Asia/Shanghai）后错峰执行。
> 本文档不修改 PLAN.md 冻结本体；PLAN-01.status.json 的修订走 P0-4 批准流（草案先行，本体不动）。

## §0 交接核验结论（2026-09-20，只读核验，未碰任何文件）

**属实**：WP-29 合入链 0483f5a→17bd363→c0a179e→67791df（parents c0a179e+e6b7330）→e7497ea；
STATUS_VALID、state=MERGED、merged_commit=67791df；合入零回归（diff 仅 WP-29-scope-decision.md）；
基线 4 failed / 633 passed / 4 skipped（133s，4 个失败为 test_finalize_merge_triple_sign 的
`git checkout -q main` 前置失败）；21 棵 worktree；主仓 6 个无关改动 + uv.lock 与
untracked docs/plans/2026-09-14-codex-verdict-contract/ 未被本轮碰过；分支领先 origin 71。

**更正（交接文档有误）**：
- #52（WP-16）**已完全收敛，无需推进**：main 内 WP-16.status.json=MERGED（merged_commit=36df3ee）、
  PLAN-CODEX.status.json=MERGED（updated 2026-09-14T04:08:16Z）、a7234c7 为 plan 级 --no-ff 合并
  （parents 0ef592e+4260172，分支尖端已全量进 main）。交接被主仓 untracked 陈旧副本误导
  （WP-16=READY_FOR_REVIEW、PLAN-CODEX=ACTIVE 均为合并前快照）。→ #52 关闭。
- #26 修订：agentic-loop-codex-verdict 工作树（干净、尖端 4260172 已在 main）由「不可清」改为**可清**；
  「不可清」余 4 棵（wp25/wp26/wp18 返工中、wp17 BLOCKED 只读留痕）。

**新发现（交接未覆盖）**：
- **N1 PLAN-01 收敛阻塞**：plan 声明 WP-01~14+28，其中 WP-02/04/05/06/07 **无 status 文件**
  （plan check 报 MISSING）；WP-09~14 APPROVED 未派发；WP-15~29 不在清单；state 仍 DRAFT。
  收敛前必须对账修订（P0-4）。
- **N2 B7 复发**：安装版 agentic 是从 /Users/admin/vibe/agentic-loop-wp17-codex-isolation 装的
  **非 editable 快照**（direct_url.json 证实），plan_cmd.py:155 仍为旧 schema，
  `agentic plan check` 拒绝对象形态 work_packages；仓库源码（PYTHONPATH=src）正常。
  PLAN.md「B7 已修（editable 指向本仓）」记录失效。收敛命令链依赖 P0-1 重装。
- **N3 集成分支与 main 实质分叉**：merge-base=0ef592e；分支领先 main **208** commit，
  main 领先分支 **38** commit（含 WP-16/17/18/19/20 直接合入 main），本地 main 又领先 origin/main **21**。
  收敛=跨分叉合并，冲突高风险面：src/agentic_loop/adapters/codex.py（main 侧 WP-16~20 vs 分支侧
  WP-21~29 均改过）、gate/、wrappers/、docs/plans/。须先回并（P0-5 runbook → P6 执行）。
- **N4 陈旧 untracked 副本阻塞收敛**：主仓 docs/plans/2026-09-14-codex-verdict-contract/ 六份文件
  与 main 已提交版本内容冲突（状态字段不同），合并/切换期会 collide。P0-2 处置。
- **N5 推送口径**：origin/plan 分支已含 137 个早期 commit（历史上推送过）；本轮 71 未推；
  最终单次 push 将连带 main 上 21 个未推 commit。
- **N6 全量盘点**：MERGED×10（01/03/08/19/21/22/24/27/28/29）、APPROVED×6（09~14）、
  DRAFT×2（15/23）、BLOCKED×1（17）、CHANGES_REQUESTED×3（18/25/26）。
  WP-18 status 无 refreeze_count 字段（返工不触发三次停手门）；WP-20 status 在 main 的
  codex-verdict 目录下（编号跨迭代混用，记录在案，不动）。

## §1 阶段计划

依赖：P0 → P1 → {P2, P3} → P6；P4 全程并行（按文件所有权分 lane）；P5 为收敛后新迭代。

### P0 环境与对账（已批准批次，今晚 22:00 错峰执行，规格见 §4）
P0-1 CLI 重装 editable ＋ 复测；P0-2 六份陈旧副本 diff→备份→删除；P0-4 PLAN-01 对账**草案**；
P0-5 回并 runbook；WP-25/WP-26 停手复核文档**草稿**；缺陷台账定位。

### P1 门禁修复批（新立 WP，4 lane；一切后续派发的地基）
| 拟立 WP | 任务 | 范围要点 | lane |
|---|---|---|---|
| WP-30(拟) | #38（B47+B63） | dispatch_lint.sh 改读 evidence.brief.path（修「所有 revN brief 从未真正过段落门禁」）＋ consult 派发附执行者报告正文 | lane-lint |
| WP-31(拟) | #11+#32（B12+B30） | status 校验器块内子字段白名单 ＋ evidence.baseline 存在性与 dispatch_commit 一致性强制 | lane-status |
| WP-32(拟) | #39（B48） | 基线数须在本 WP 自己的 base commit 实测、禁跨 lane 抄数（模板规则＋lint 强制） | lane-template |
| WP-33(拟) | #27（B22） | preflight.sh 对 status 的 9 次独立 open 收敛为单一读取面（判定面＝消费面） | lane-preflight |
| 串行尾随 | #42（B52） | 收紧 SECTION_BODY_TRUNCATED 谓词——与 #38 同文件，lane-lint 内串行 | lane-lint |
| stretch | #23 | 学习回边机械化：dispatch_lint 校验新 brief DoD 覆盖与其 allowed_paths 相交的既有缺陷 | lane-lint |

注：WP-30 自身派发时门禁仍是坏的——按 WP-26 rev3/rev4 先例，编排者用真脚本判据切片手工核验
＋ WP-20-brief.md 反向对照。派发按 autonomy 政策（引擎侧加性、risk.* 全 false 可自动冻结派发）。

### P2 活跃返工道（3 WP）
- **WP-25 rev5（#12）**：B38（引导句攻击使纪律列表整体失效；修法：三块补上文语境判据——紧邻前一行
  ＋所属段标题纳入冻结常量；自检须含①引导句攻击转红②无关段落编辑仍 GREEN）＋ B39（brief §D 的
  用例内 sha256 断言落地）。re-freeze=3 → **停手复核文档＋用户批准**后才冻结。
- **WP-26 rev5（#18）**：B35（bash 面 INV-B 补读取次数判定；已验证修法：sitecustomize 包
  builtins.open 计数器＋realpath 比对＋AGENTIC_PYTHON shim，real=1/mutated=2）＋ B36（出口 9/10
  措辞区分，出口 9 补 fixture）。同上门。
- **WP-18 返工（#53）**：DispatchProof 信任根从「值对不对」转到「只能由 engine 写入」
  （child_pid/argv_hash/orchestrator_session/exit_code 实测均可自取真值、dispatched_by_engine
  是常量；collect_dispatch_proof 只校验类型）。无 refreeze 门，建议简短复核文档。
  原合入目标曾是 main（3d50ab7），本次返工改走集成分支。codex 另两条（isolation 优先级、
  forbidden_paths）已核实不成立，**不得写入返工条件**。

### P3 重估与派发波（依赖 P1 全部落地）
- **WP-29 阶段 2（#51）**：范围已获用户批准——replica_identity（INV-N3，两份模板副本逐字节同一）、
  protected_body_identity（保护段正文与冻结常量逐字节相等）、明确不承诺 active_embedding；
  不引入 Markdown parser、不整文件冻结。冻结 brief＋preflight＋派发（新 lane 分支＋新 worktree；
  与 #26 中 wp29 旧树清理的排序协调）。
- **#25 存量重估**：WP-09~14 六个 APPROVED 逐个判定前提是否已变（本轮已修 A29/A33/A34/A35/B13/B15）
  → 需 re-freeze 的逐份重冻结（此时 P1 的基线规则与 #23 DoD 覆盖检查应已生效）→ 批量派发；
  WP-15（DRAFT、无 evidence.brief.path）立 brief 或关账。
- **#3（A26→WP-23）**：WP-23 brief rev 并入 resolve_paths 环境净化（GIT_DIR/GIT_COMMON_DIR
  可改指主仓根），一并冻结派发（HANDOFF 明示合并处理，不重复立 WP）。

### P4 缺陷补钉道（与 P2/P3 并行，两条 lane）
- **env 卫生 lane**：#41（B51 adapter 派发环境净化；OPENAI_BASE_URL 误路由；**codex 须保留
  OPENAI_API_KEY 只剥 BASE_URL，kimi 剥两面**）；#31（B31 pre-push iterations_dir() 无参覆盖丢
  repo_root，链接工作树 fail-open）；#14（B14 源码路径/主仓根一致性自检＋改协议示例，
  含 B7 复发的机制化防复发）。
- **判据效力 lane**：#46（B55+B56+B58+B59 声称效力 vs 实际运行面效力；立项前须先取四条缺陷全文——
  已确认不在 WP-08-candidate.md）；#33（B32 补钉 WP-17 两处用例逃逸：E1 hunk 二次切分、
  E2 循环内 fail-closed；WP-17 本体已废弃但逃逸形态仍在）；#2（A19+A23 派发命令形态与
  「已开工」确认）。

### P5 流程层改造（收敛后另立迭代）
- #22 门禁按 blast radius 分道（可逆且局限／可逆但面广／不可逆不开）；不可逆道是**关闭的道**，
  不是会被调高的阈值。
- #34 min_independence weak→strong：**硬阻塞于独立性判据重设计**（A5/A8/A11 链，WP-17 REWORK
  未排期）——建议单独立项＋codex consult；三签可信度的根，当前无任务条目。
- 悬置登记项归口：A4（status 提交次数契约变更，待用户裁定归属）、A9/A10（独立性 strong 上限、
  identity_model 可手改伪造）。

### P6 收敛
1. 回并 main 进集成分支（按 P0-5 runbook 解冲突）→ 全量重测（**基线重测，633 是本分支口径，
   禁跨 lane 抄**）。
2. `agentic plan check` → `plan lint`（每 WP 恰好 freeze＋finalize 两次 status 提交）→
   `plan merge --no-ff`（集成分支→main）→ `plan finalize`。
3. **单次 push**（always_stop，需批准；连带 main 上 21 个未推 commit）。
4. 前置硬条件：修订后 PLAN-01 全部声明 WP=MERGED、工作树干净、P0-2/P0-3 处置毕、CLI 已重装。

## §2 待用户裁定清单（10 项）

| # | 事项 | 状态 |
|---|---|---|
| 1 | P0-1 CLI 重装 editable | **已批准**（2026-09-20） |
| 2 | P0-2 陈旧 untracked 副本按 main 版本对齐 | **已批准**（2026-09-20） |
| 3 | P0-3 六个无关未提交改动归属（侧支提交/保留/丢弃） | **已裁决 2026-09-21→提交 plan 分支**（`4b9eb37` config+3 契约重生成 / `c3ff5be` provider kimi-defs 修复）。查明＝连贯 provider 重绑定（独立性 weak→strong，#34 配置侧），非「无关」；config.toml 与 plan 的 `[[gate]]` schema entangled、`git apply --check` 无法干净移植到 main 侧支，故落 plan 分支随 P6 收敛。uv.lock 仍 untracked（不在 #3 范围）。工作树现仅剩 uv.lock |
| 4 | P0-4 PLAN-01 修订口径（WP-02/04/05/06/07 去留＋增补 18/25/26＋state→ACTIVE） | 草案产出后待批 |
| 5 | P0-6 工作树清理（可清 8＋游离 8，逐棵） | 逐棵待批（不可逆） |
| 6 | WP-25/WP-26 停手复核文档 | 草稿产出后待批 |
| 7 | WP-18 返工 brief 冻结 | 待确认 |
| 8 | WP-09~14 重估后逐份 re-freeze（**WP-11 已关闭** `ea2a198`，余 09/10/12/13/14；WP-13 rev3 草稿 `5edac94` 待 §5 契约表述修正＋用户批准才冻结） | 待批 |
| 9 | P6 收敛合并＋push | 待批 |
| 10 | P5 归属＋独立性判据重设计立项（#34 前置；**#34 配置侧已随 #3 落地** `4b9eb37`，判据重设计本身仍待立项） | 待裁决 |

## §3 风险与前提

- **最大工程风险**：N3 跨分叉合并（208 vs 38）。runbook 先行、合并后全量重测。
- B7 教训：CLI 重装后对既有门禁结论抽检复测（dispatch-lint／plan check／validate_wp_status）。
- 基线 per-lane 纪律全程生效；4 个预存失败与 main 被 agentic-loop-main-codex-merge 占用检出相关，
  该树清理后重测可能归零。
- 缺陷台账（B47/B55 等任务描述与证据路径）若在仓外（任务系统），P1 brief 起草需用户提供全文。
- re-freeze 计数口径＝brief rev 号（WP-25/26 均为 rev4＝第 3 次 re-freeze；
  规则原文 WORK_PACKAGE.md.tmpl:9「第 3 次及以后 re-freeze：冻结前必须停手复核计划，
  未经用户批准不得冻结」）。

## §4 今晚 P0 批次执行规格（22:00 错峰，已批准范围）

执行前置：按 AGENTS.md §3 恢复上下文（git status／branch／worktrees；读本文档；
**不得依赖聊天记录**）。执行环境事实：门禁脚本在 src/agentic_loop/wrappers/；
status 校验器须 `PYTHONPATH=src python3 -m agentic_loop.validate_wp_status <file>`；
测试用 python3.11。

1. **P0-1 CLI 重装**：主仓内 `uv tool install --force --editable .`。
   复测三项：① `agentic plan check docs/plans/2026-09-13-parallel-throughput/PLAN-01.status.json`
   应输出 PLAN_CHECK 行（不再 PLAN_INVALID）；② dispatch-lint 对 WP-26-brief-rev4.md 行为与
   重装前一致；③ `python3.11 -m pytest tests -q` 基线仍为 4F/633P/4S。
2. **P0-2 陈旧副本处置**：对主仓 untracked 的 docs/plans/2026-09-14-codex-verdict-contract/
   六份文件，逐份与 `git show main:<path>` diff；全部备份到 /tmp/agentic-p0-backup-20260920/；
   删除主仓内六份；`git status` 确认该目录消失。若某份含 main 版本没有的实质内容，
   在报告中高亮（备份已保留），不阻塞删除。
3. **P0-4 对账草案**：产出 CONVERGENCE-P0-4-plan-reconciliation.md——逐个判定 WP-02/04/05/06/07
   （已被后续 WP 交付？仍需？废弃？证据：各自 brief、PLAN.md §5、相关 WP status），
   给出 work_packages 修订建议（含增补 18/25/26）与 state DRAFT→ACTIVE 建议。
   **本批次不得修改 PLAN-01.status.json 本体**。
4. **P0-5 回并 runbook**：产出 CONVERGENCE-P0-5-backmerge-runbook.md——`git merge-tree` 预演
   main→集成分支冲突面（重点 adapters/codex.py、gate/、wrappers/、docs/plans/），
   解冲突次序与验证步骤。只读预演，不执行合并。
5. **停手复核文档草稿 ×2**：WP-25-plan-review-before-rev5.md、WP-26-plan-review-before-rev5.md
   （re-freeze=3 门）：三轮失败链根因、由本轮判据组成步骤生成的变异集（不得沿用上一轮缺陷形状）、
   B38/B39 与 B35/B36 修法方向及自检要求。**标注待用户批准后才冻结**。
6. **缺陷台账定位**：搜索仓内 B47/B63/B55/B56/B58/B59/B12/B30/B22/B31/B32/B48/B51/B52/
   A19/A23/A26 的任务描述与证据路径（WP-08-candidate.md 已确认无 B47+）；记录台账位置或缺口。
7. **收尾**：产出 CONVERGENCE-P0-report.md（全部验证证据、diff 摘要、异常）；
   本批次新增文档以**显式路径**提交（`git add <paths> && git commit -- <paths>`，
   提交信息前缀 📋 plan(2026-09-13-parallel-throughput)）。

**硬性禁区**（违反即停手记录，不得自行扩权）：
- 不动六个未提交改动（.agentic/config.toml、AGENTS.md、CLAUDE.md、
  docs/agentic/OPERATING_MODEL.md、src/agentic_loop/provider.py、tests/test_provider.py）与 uv.lock；
- 不清理任何工作树；不冻结/不派发任何 WP；不修改 PLAN-01.status.json；不 push；
- 不做清单外的任何状态变更。
