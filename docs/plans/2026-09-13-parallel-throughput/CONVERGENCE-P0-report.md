# CONVERGENCE-P0-report：P0 已批准批次执行报告

> 编排者 claude ｜ 执行日期 2026-09-20（22:00 后错峰）｜ 依据 CONVERGENCE-PLAN.md §4
> 用户批准：2026-09-20「好的，启动」+「安排好计划，今晚10点后错峰执行」
> 工作目录：`/Users/admin/vibe/agentic_loop`（主仓，分支 `plan/2026-09-13-parallel-throughput`，尖端 `4d6b8b6`）
> 权威规格：`docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-PLAN.md` §4（提交于 `4d6b8b6`）

## §A 执行总览

| # | 任务 | 状态 | 产物/证据 |
|---|---|---|---|
| 0 | 上下文恢复（AGENTS.md §3） | ✅ 完成 | git status/branch/worktree/log 实测；通读 CONVERGENCE-PLAN.md §0/§4 |
| 1 | P0-1 CLI 重装 + 复测三项 | ✅ 完成 | editable 重装；plan check 转 PLAN_CHECK；dispatch-lint 一致；pytest 4F/633P/4S |
| 2 | P0-2 陈旧副本处置 | ✅ 完成 | 6 份 diff+备份+删除；目录消失 |
| 3 | P0-4 对账草案 | ✅ 完成 | `CONVERGENCE-P0-4-plan-reconciliation.md`（290 行） |
| 4 | P0-5 回并 runbook | ✅ 完成 | `CONVERGENCE-P0-5-backmerge-runbook.md`（263 行）；merge-tree 预演零冲突 |
| 5 | WP-25/WP-26 停手复核草稿 ×2 | ✅ 核实已存 | `WP-25/26-plan-review-before-rev5.md`（commit `cc22212`，2026-09-18），内容盖面，本批不重写 |
| 6 | 缺陷台账定位 | ✅ 完成 | 16/17 已定位；B32 为唯一缺口（见 §G） |
| 7 | 收尾报告 + 显式路径提交 | ✅ 完成 | 本文件 + 提交（见 §H） |

**七项全部执行，无失败项，无静默跳过，无扩权补救。**

## §B 第 0 步：上下文恢复证据

```
分支：plan/2026-09-13-parallel-throughput（领先 origin 72 个提交）
尖端：4d6b8b6（收敛计划落盘提交）
worktree：21 棵（主仓 + 20 棵 linked，含 wp17 BLOCKED 只读、wp18/25/26 返工中、
          agentic-loop-codex-verdict 尖端 4260172 已在 main）
未提交改动（禁区，未碰）：.agentic/config.toml、AGENTS.md、CLAUDE.md、
          docs/agentic/OPERATING_MODEL.md、src/agentic_loop/provider.py、tests/test_provider.py
untracked（禁区，未碰）：uv.lock
untracked（P0-2 处置对象）：docs/plans/2026-09-14-codex-verdict-contract/（6 份）
```

CONVERGENCE-PLAN.md §0 核验结论与 §4 执行规格已通读；本批次严格按 §4 七项执行。

## §C P0-1 CLI 重装证据

### C.1 重装前基线（B7 复发确证）

- `direct_url.json` = `{"url":"file:///Users/admin/vibe/agentic-loop-wp17-codex-isolation","dir_info":{}}`
  ——**非 editable**，指向 wp17 工作树快照（B7 复发现象，§0 N2 属实）。
- `agentic plan check PLAN-01.status.json` → `PLAN_INVALID: PLAN-01.status.json: work_packages must be a list of non-empty strings`
  ——旧 schema 拒绝对象形态 work_packages（§0 N2 属实）。
- `agentic dispatch-lint WP-26.status.json` → `DISPATCH_LINT_PASS`（B16 现象：实际 lint 的是
  `WP-26-brief.md` rev1 而非 rev4，因 `dispatch_lint.sh:60` 按固定命名拼接，不读 `evidence.brief.path`）。
- 基线文件留存：`/tmp/agentic-p0-baseline-20260920/plan-check-pre.txt`、`dispatch-lint-wp26-pre.txt`。

### C.2 重装

```
$ uv tool install --force --editable .
Resolved 1 package in 6ms
   Building agentic-loop @ file:///Users/admin/vibe/agentic_loop
      Built agentic-loop @ file:///Users/admin/vibe/agentic_loop
 + agentic-loop==0.8.13 (from file:///Users/admin/vibe/agentic_loop)
Installed 1 executable: agentic
```

### C.3 复测三项（全部通过）

**① plan check 转 PLAN_CHECK（不再 PLAN_INVALID）**：
```
PLAN_CHECK plan_id=PLAN-01 state=DRAFT base_branch=plan/2026-09-13-parallel-throughput target_branch=main
PLAN_CHECK: wp WP-01 MERGED
PLAN_CHECK: wp WP-02 MISSING
... （WP-04/05/06/07 MISSING；WP-09~14 APPROVED；WP-28 MERGED）
PLAN_CHECK: merge NOT detected (plan/2026-09-13-parallel-throughput not merged into main)
PLAN_CHECK: not converged (11 WP(s) pending or , merge not done)
exit=0
```
- `direct_url.json` 复测 = `{"url":"file:///Users/admin/vibe/agentic_loop","dir_info":{"editable":true}}` ——**B7 已修**。
- 小瑕疵记录：末行 `pending or , merge not done` 中 `or` 后疑缺词（`missing`？），非本批范围，备查。

**② dispatch-lint 行为与重装前一致**：`DISPATCH_LINT_PASS`，exit=0（与基线逐字一致）。

**③ pytest 基线仍为 4F/633P/4S**：
```
4 failed, 633 passed, 4 skipped in 96.88s (0:01:36)
FAILED tests/test_finalize_merge_triple_sign.py::test_v3_triple_sign_pass_finalizes
FAILED tests/test_finalize_merge_triple_sign.py::test_v3_qoder_override_approved_finalizes_record_preserved
FAILED tests/test_finalize_merge_triple_sign.py::test_v3_missing_qoder_block_rejected
FAILED tests/test_finalize_merge_triple_sign.py::test_v2_without_qoder_finalizes_double_sign
```
- 4 个失败均为 `test_finalize_merge_triple_sign` 的 `git checkout -q main` 前置失败
  （`subprocess.CalledProcessError: Command '['git','checkout','-q','main']' returned non-zero exit status 1`），
  与 §0 基线一致；根因是 `agentic-loop-main-codex-merge` 工作树占用 main 检出（§3 注：该树清理后可能归零）。
- 证据留存：`/tmp/agentic-p0-baseline-20260920/pytest-post.txt`。

## §D P0-2 陈旧副本处置证据

### D.1 逐份 diff（vs `git show main:<path>`）

| 文件 | diff 结果 | 实质内容差异 |
|---|---|---|
| `PLAN.md` | **逐字相同**（diff exit 0，0 行） | 无 |
| `WP-16-brief.md` | **逐字相同**（0 行） | 无 |
| `WP-16-codex-merge-gate.answer.md` | **逐字相同**（0 行） | 无 |
| `phase-tiers.json` | **逐字相同**（0 行） | 无 |
| `PLAN-CODEX.status.json` | 差异 29 行 | 本地为**合并前快照**：`state=ACTIVE`/`merged_commit=""`/work_packages 对象形态/updated 02:55；main 为收敛后：`state=MERGED`/`merged_commit=a7234c7`/work_packages 字符串形态/updated 04:08。**本地无 main 缺失的实质内容** |
| `WP-16.status.json` | 差异 75 行 | 本地为**合并前快照**：`state=READY_FOR_REVIEW`、含 `native_gate_blocker` 块；main 为 `state=MERGED`/`merged_commit=36df3ee`/`finalized_at`，且本地 `native_gate_blocker` 的 reason/config_discrepancy/evidence/next_action **已被 main 的 `native_gate_resolution.historical_precheck` 块完整含盖**。**本地无 main 缺失的实质内容** |

**高亮判定**：两份差异文件均为 main 收敛前的旧快照，其全部实质信息已被 main 版本含盖（结构不同但内容等价）。
**无任何一份含 main 版本缺失的实质内容**，删除无信息损失。

### D.2 备份

全部 6 份原件 + 6 份 diff 已备份至 `/tmp/agentic-p0-backup-20260920/2026-09-14-codex-verdict-contract/`：
```
PLAN-CODEX.status.json (566B) + .diff (940B)
PLAN.md (1827B) + .diff (0B)
WP-16-brief.md (5292B) + .diff (0B)
WP-16-codex-merge-gate.answer.md (643B) + .diff (0B)
WP-16.status.json (7237B) + .diff (3989B)
phase-tiers.json (70B) + .diff (0B)
```

### D.3 删除与确认

- 6 份文件经 DeleteFile 逐个删除；空目录经 `rmdir` 清理。
- `git status --short` 复测：`docs/plans/2026-09-14-codex-verdict-contract/` **已从 untracked 列表消失**。
- `ls docs/plans/` 复测：仅剩 `2026-09-13-parallel-throughput`，目标目录**物理消失**。

## §E P0-4 对账草案摘要

产物：`CONVERGENCE-P0-4-plan-reconciliation.md`（290 行，**草案，未改 PLAN-01.status.json 本体**）。

五个 MISSING WP 判定：

| WP | 判定 | 关键证据 |
|---|---|---|
| WP-02 | **废弃** | `gate/plan.py` 不存在；`quality-gate.sh:57` 重复注释仍在，§5 已接受"靠测试维持" |
| WP-04 | **废弃** | C1 由 `b4733058`(2026-09-10，早于 plan 冻结)预交付；交叉检查未交付，价值被 WP-26/WP-30 路径稀释 |
| WP-05 | **废弃** | `plan_cmd.py` 无 `merge --lane`；被 AGENTS.md §4.3"一 plan 一合并"模型超越 |
| WP-06 | **废弃** | worktree 隔离由 `c555daf`(2026-08-13)预交付 + WP-19/WP-27 加固 |
| WP-07 | **废弃** | `.agentic/lessons.md` 不存在；依赖链（04+05+06）断裂；价值已转移到 AGENTS.md/模板/复核文档 |

work_packages 修订建议：移除 5（02/04/05/06/07）+ 保留 10（01/03/08/09~14/28）+ 增补 12
（15/17/18/19/21/22/23/24/25/26/27/29）= **合计 22 个 WP**；WP-20 不增补（编号跨迭代混用，§0 N6）。
state 建议：DRAFT→ACTIVE（集成分支已存在、各 WP base_branch 已指向它、plan 事实已 ACTIVE），
须与 work_packages 修订同批落地，待用户批准（§2 #4）。

## §F P0-5 回并 runbook 摘要

产物：`CONVERGENCE-P0-5-backmerge-runbook.md`（263 行，**只读预演，未执行合并**）。

**核心发现（更正 §0 N3）**：`git merge-tree --write-tree plan/2026-09-13-parallel-throughput main`
→ tree `9d5656ac…`，**exit 0 = 零冲突**。

- 分叉实况：merge-base `0ef592e`；集成分支领先 **209**（§0 记 208，+1 为收敛计划提交）；
  main 领先 **45**（§0 记 38，+7 为 WP-21 链 `cb4c2ef`→`2c29725`）；本地 main 领先 origin/main **28**。
- **N3 高风险判断证伪**：集成分支自 merge-base **从未改动** `adapters/codex.py`（main 单边 +1305/-80）；
  `wrappers/` main 侧零改动；唯一双边文件是 `gate/__init__.py`（main +11/-1 vs 集成分支 +188/-3，区域不重叠，clean）。
- 合并将引入 main 的 28 文件（codex.py 重写 + 7 个 codex 测试 + 19 份 codex-verdict 迭代文档）。
- runbook 含：解冲突次序预案（§3）、合并后 6 步验证（§4：文本完整性/全量重测/CLI 门禁/editable 未漂移/
  gate 语义/codex 适配）、6 项风险登记（§5）、与 P6 衔接（§6）。

## §G 缺陷台账定位（任务 6，供 P1 brief 起草）

**主台账**：`WP-08-candidate.md`（3300 行，含 A0–A35 + B1–B34，**无 B47 及以后编号**，§0 已确认）。
**B47+ 散台账**：分布于 `B47-measurement.md`、WP-28/WP-29 系列文档与 status.json。

### G.1 已定位（16 项，含任务描述 + 证据路径）

| 缺陷 | 任务# | 台账位置（描述） | 证据路径 |
|---|---|---|---|
| B12 | #11 | `WP-08-candidate.md:2237`（## B12 派发基线未落盘+提示写错） | 同文件 §B12 |
| B22 | #27 | `WP-08-candidate.md:2850`（## B22 判定面与消费面分离，WP-27 观察） | 同文件 §B22；`B47-measurement.md:66` |
| B30 | #32 | `WP-08-candidate.md:3142`（## B30 门禁读 consult.decision vs 编排者写 verdict） | 同文件 §B30 |
| B31 | #31 | `WP-08-candidate.md:3174`（## B31 pre-push iterations_dir() 覆盖丢主仓路径） | 同文件 §B31；`WP-25-brief-rev4.md:175-177` |
| A19 | #2 | `WP-08-candidate.md:1132`（### A19 无首次派发命令，DispatchProof 无从产生） | 同文件 §A19 |
| A23 | #2 | `WP-08-candidate.md:1225`（### A23 派发无"执行者开工"验收位） | 同文件 §A23 |
| A26 | #3 | `WP-08-candidate.md:1354`（### A26 入口在净化判据前已信任调用者仓库选择） | 同文件 §A26；并入 WP-23 |
| B47 | #38 | `B47-measurement.md`（专文 67 行：段落门禁从未读 revN brief） | `WP-29-plan-review-before-rev7.md:123`；`WP-29-review-rev6.md:85` |
| B48 | #39 | `WP-28-review-rev3.md:102`（基线 619 抄成 WP-28 lane 数） | `WP-29-brief-rev2.md:125`；`WP-29-scope-decision.md:477`；`WP-29.status.json` |
| B51 | #41 | `WP-29.status.json:348/468/711`（env 覆盖 --config-file base_url） | `WP-28.status.json:16`；CONVERGENCE-PLAN §1 P4 |
| B52 | #42 | `WP-28-review-rev4.md:60`（## 非阻断发现—登记为 B52，SECTION_BODY_TRUNCATED 谓词归因过宽） | `WP-28-brief-rev5.md:220`；`WP-28-consult-codex-rev6-request.md:55` |
| B55 | #46 | `WP-29.status.json` evidence.brief_rev3.orchestrator_defects_found_in_rev2.B55（结构化全文：brief 不得断言执行者 base commit 不具备的判据保护） | `WP-29-plan-review-before-rev4.md:18`；`WP-29-review-stage1-rev3.md:73` |
| B56 | #46 | `WP-29.status.json` …B56（结构化全文：每格"实测"须写明测哪个判据版本） | `WP-29-plan-review-before-rev4.md:17`；`WP-29-review-stage1-rev3.md:63` |
| B58 | #46 | `WP-29-plan-review-before-rev5.md:51`（复核者未验自己的 binary，shell grep 是 ugrep 函数壳→假红） | `WP-29-brief-rev6.md:209`；`WP-29-brief-rev7.md:210`；`WP-29-review-rev7.md:35` |
| B59 | #46 | `WP-29-plan-review-before-rev5.md:52`（brief 把"手段"写进判据，而非"目的+可接受手段集"） | `WP-29-consult-rev5.md:37`；`WP-29-consult-rev4-verdict.md:38` |
| B63 | #50 | `WP-29-consult-rev7-codex.md:17`（## 第 1 次派发作废—二签名漏附执行者报告正文） | `WP-29.status.json:1113/1242/1245` |

**更正 CONVERGENCE-PLAN §1 P4 #46 的一处判断**：该条称 B55/B56/B58/B59"立项前须先取四条缺陷全文——
已确认不在 WP-08-candidate.md"。实测：**四条全文均在仓内**（B55/B56 在 WP-29.status.json 结构化字段，
B58/B59 在 WP-29 系列复核文档），只是不在 WP-08-candidate.md。P1 起草 #46 时**无须向用户索取全文**，
可直接引用上述路径。

### G.2 缺口（1 项）

| 缺陷 | 任务# | 缺口 | 处置建议 |
|---|---|---|---|
| **B32** | #33 | **仓内无任务描述与证据路径**。仅 `CONVERGENCE-PLAN.md:95` 一行提及："#33（B32 补钉 WP-17 两处用例逃逸：E1 hunk 二次切分、E2 循环内 fail-closed；WP-17 本体已废弃但逃逸形态仍在）"。`WP-17.report.md`/`WP-17-brief.md`/`WP-17.status.json` 均无 `B32`/`E1`/`E2`/`hunk 二次切分`/`循环内 fail-closed` 字样 | P1 起草 #33 brief 前，**须请用户提供 B32 全文**（疑在仓外任务系统），或指明 E1/E2 逃逸的具体用例文件与复现命令。与 §3"缺陷台账若在仓外，P1 brief 起草需用户提供全文"一致 |

### G.3 任务号 → 缺陷映射（P1 起草索引）

```
#38 = B47 + B63        #11+#32 = B12 + B30      #39 = B48
#27 = B22              #42 = B52                #41 = B51
#31 = B31              #46 = B55+B56+B58+B59    #33 = B32（缺口）
#2  = A19 + A23        #3  = A26 → WP-23
```

## §H 收尾提交

### H.1 提交前核验

- `git status --short` 确认：6 个禁区改动仍为 ` M`（未碰），`uv.lock` 仍为 `??`（未碰），
  **无 `MM` 条目、无他会话暂存路径**。
- 本批次新增文件（仅 3 份，均在 plan 目录）：
  - `docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-4-plan-reconciliation.md`
  - `docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-5-backmerge-runbook.md`
  - `docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-report.md`（本文件）
- WP-25/WP-26 停手复核文档**非本批新增**（commit `cc22212` 已提交），不在本次提交路径内。

### H.2 提交命令（显式路径）

```bash
git add docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-4-plan-reconciliation.md \
        docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-5-backmerge-runbook.md \
        docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-report.md
git commit -m "📋 plan(2026-09-13-parallel-throughput): P0 批次执行报告与产物" -- \
        docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-4-plan-reconciliation.md \
        docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-5-backmerge-runbook.md \
        docs/plans/2026-09-13-parallel-throughput/CONVERGENCE-P0-report.md
```

（实际提交结果见本文件落盘后的 git log；提交仅含上述 3 个显式路径，不牵动禁区文件与 uv.lock。）

## §I 异常与未完成项

1. **无失败项**：§4 七项全部执行成功，无静默跳过、无扩权补救。
2. **shell PATH 事故（已自愈，记录备查）**：P0-2 首轮 diff 脚本误用 zsh 特殊变量 `path` 作循环变量，
   导致 PATH 被覆盖、`tee`/`cp`/`ls` 一度 command not found。改用 `rel` 变量名 + 显式 `export PATH` 后恢复。
   **未影响任何文件内容**，备份与删除均在 PATH 恢复后正确完成。
3. **沙箱写权限**：备份目标 `/tmp/agentic-p0-backup-20260920/` 在工作区外，需跳出沙箱写入（已获准）。
4. **B32 缺口**（§G.2）：唯一未完成项，属"台账在仓外"的预期情形，已记录处置建议，不阻塞 P0。
5. **`agentic plan check` 输出小瑕疵**（§C.3）：`pending or , merge` 疑缺词，非本批范围，备查。
6. **4 个预存测试失败**（§C.3）：与 `agentic-loop-main-codex-merge` 工作树占用 main 检出相关，
   非 P0 引入；§3 注该树清理后可能归零，留待 P6 工作树清理后复测。

## §J 晨间待审清单（对应 CONVERGENCE-PLAN §2 第 3/4/5/6/7 项裁定点）

> 以下为 P0 批次产出后**待用户晨间裁定**的事项，按 §2 编号。本批次**未冻结、未派发、未改本体、未 push**。

| §2 # | 裁定点 | P0 产出 | 待用户决定 |
|---|---|---|---|
| **#3** | P0-3 六个无关未提交改动归属（侧支提交/保留/丢弃） | 本批次**未碰**（禁区）；6 文件仍 ` M`，uv.lock 仍 `??` | 逐个裁定：侧支提交 / 保留 / 丢弃。**不可逆，须逐棵批** |
| **#4** | P0-4 PLAN-01 修订口径 | `CONVERGENCE-P0-4-plan-reconciliation.md` 草案：移除 5（02/04/05/06/07）+ 增补 12（15/17/18/19/21/22/23/24/25/26/27/29）+ state DRAFT→ACTIVE | 批准修订口径 → 由 P3（或专门 plan 修订 WP）落地编辑 PLAN-01.status.json 本体 |
| **#5** | P0-6 工作树清理（可清 8 + 游离 8，逐棵） | 本批次**未清理任何工作树**（禁区）；21 棵全在 | 逐棵裁定清理次序。**不可逆，须逐棵批**；注意 #5 与 §C.3 的 4 个预存失败相关（清理 `agentic-loop-main-codex-merge` 后可能归零） |
| **#6** | WP-25/WP-26 停手复核文档 | 两份草稿**已存**（commit `cc22212`，2026-09-18），内容盖面（三轮失败链根因/变异集按判据组成维度生成/B38-B39 与 B35-B36 修法/自检要求/待批准标注齐全） | 审阅两份草稿 → 批准后方可冻结 rev5 并派发（re-freeze=3 门，**未经批准不得冻结**） |
| **#7** | WP-18 返工 brief 冻结 | 本批次**未冻结/未派发**（禁区）；WP-18 仍 CHANGES_REQUESTED | 确认返工口径（DispatchProof 信任根从"值对不对"转到"只能由 engine 写入"；codex 另两条已核实不成立，不得写入返工条件）→ 批准冻结 |

**补充待审（非 §2 编号，但 P0 产出触及）**：
- **P0-5 回并 runbook**（`CONVERGENCE-P0-5-backmerge-runbook.md`）：merge-tree 预演**零冲突**，更正 §0 N3
  高风险判断。P6 实际回并须用户批准（§2 #9），且执行前重跑预演（尖端可能已变）。
- **B32 缺口**（§G.2）：P1 起草 #33 brief 前须请用户提供 B32 全文或指明 E1/E2 逃逸的具体用例与复现命令。

## §K 硬性禁区遵守声明

本批次全程遵守 CONVERGENCE-PLAN §4 硬性禁区，逐条声明：

- ✅ **未动**六个未提交改动（.agentic/config.toml、AGENTS.md、CLAUDE.md、docs/agentic/OPERATING_MODEL.md、
  src/agentic_loop/provider.py、tests/test_provider.py）与 uv.lock —— git status 复测仍为原状。
- ✅ **未清理**任何工作树 —— 21 棵 worktree 全在。
- ✅ **未冻结/未派发**任何 WP。
- ✅ **未修改** PLAN-01.status.json 本体（P0-4 仅产出草案）。
- ✅ **未 push**。
- ✅ **未做** §4 清单外的任何状态变更（P0-2 的 rmdir 空目录属"删除主仓内六份/确认目录消失"的完整意图）。

---

**P0 已批准批次执行完毕。七项全部落地，证据齐全，无失败、无扩权。待用户晨间裁定 §J 清单。**
