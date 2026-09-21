# CONVERGENCE-P0-5：main → 集成分支回并 runbook（只读预演，不执行合并）

> 编排者 claude ｜ 落盘日期 2026-09-20 ｜ 依据 CONVERGENCE-PLAN.md §4 第 4 项
> **本文件是只读预演产物，本批次不执行任何合并。** 实际回并属 P6 阶段，须用户批准。
> 预演工具：`git merge-tree --write-tree`（git 2.40.0），纯对象库操作，不触碰工作树/索引。

## §0 分叉实况（2026-09-20 实测，更正 CONVERGENCE-PLAN §0 N3）

| 指标 | §0 N3 记录（2026-09-20 早） | 本批次实测（2026-09-20 晚） | 差异原因 |
|---|---|---|---|
| merge-base | `0ef592e` | `0ef592e` | 一致 |
| 集成分支领先 main | 208 | **209** | +1 = 收敛计划提交 `4d6b8b6` |
| main 领先集成分支 | 38 | **45** | +7 = WP-21 链（`cb4c2ef`→`2c29725`）在 §0 核验后落入 main |
| 本地 main 领先 origin/main | 21 | **28** | +7 同上 |
| 集成分支尖端 | — | `4d6b8b6` | — |
| main 尖端 | — | `2c29725` | — |

**N3 冲突高风险判断的更正**：§0 N3 称"冲突高风险面：`src/agentic_loop/adapters/codex.py`
（main 侧 WP-16~20 vs 分支侧 WP-21~29 均改过）"。**实测证伪**：集成分支自 merge-base 起
**从未改动** `adapters/codex.py`（`git diff --name-only 0ef592e..plan/2026-09-13-parallel-throughput
-- src/agentic_loop/adapters/` 输出为空）。codex.py 是 main 单边改动（+1305/-80），合并时
直接取 main 版本，无冲突。

## §1 merge-tree 预演结果

### §1.1 命令与输出

```bash
$ git merge-tree --write-tree plan/2026-09-13-parallel-throughput main
9d5656acf3f94bf27c961f7fb6af72dc3b6c4a05
$ echo $?
0
```

- **exit 0** = 合并**无冲突**（git merge-tree 约定：0=clean，1=conflicts，<0=error）
- 输出仅一行 = 合并结果的 tree OID；若有冲突会追加冲突文件清单与 blob 信息
- `--name-only` 复跑同样仅输出 tree OID，无冲突文件列表

### §1.2 结论

**main → 集成分支的三方合并预测为干净合并，零冲突。**

这不意味着可以跳过验证（见 §4）：git 只能检测**文本冲突**，检测不到**语义冲突**
（例如 main 的 codex adapter 重写与集成分支的 gate 改动在运行时的交互）。

## §2 冲突面分析（逐区域）

### §2.1 双边改动文件（唯一重叠面）

`comm -12 <(main 侧改动文件) <(集成分支侧改动文件)` 输出**仅 1 个文件**：

| 文件 | main 侧改动 | 集成分支侧改动 | 合并结果 |
|---|---|---|---|
| `src/agentic_loop/gate/__init__.py` | +11/-1（WP-16~21 相关，`git_merge_base` 附近小幅调整） | +188/-3（WP-19 `path_is_in_worktree` + A22 `_GIT_SELECTION_VARS` 环境净化，新增 ~149 行块） | **clean**：两侧改动落在文件不同区域，三方合并不产生冲突标记 |

**验证**：合并结果 tree `9d5656ac` 对集成分支 tree 的 diff 显示 `gate/__init__.py | 12 +-`，
即只引入了 main 侧的 +11/-1，集成分支侧的 +188 保持不变——两侧改动都被保留。

### §2.2 main 单边改动（合并时整体引入，无冲突）

main 自 merge-base 改动 28 个文件，其中 27 个是集成分支未碰的：

**源码（2 个）**：
- `src/agentic_loop/adapters/codex.py`（+1305/-80）——WP-16~21 的 codex adapter 大重写：
  结构化裁决 fail-closed 恢复、Base64 prompt 归一化、行级 sub-hunk 切分、配置隔离分块、
  tool-free finalization 良性告警容忍、直连禁工具收尾。**集成分支从未改此文件**，直接取 main 版。
- `src/agentic_loop/gate/__init__.py`（见 §2.1，双边但 clean）

**测试（7 个，均为 main 新增或改写）**：
- `tests/test_codex_config_isolation_chunking.py`（+468，WP-18）
- `tests/test_codex_direct_finalization.py`（+435，WP-21）
- `tests/test_codex_finalization_benign_warning.py`（+713，WP-20）
- `tests/test_codex_gate_capability_merge.py`（+377，WP-18）
- `tests/test_codex_line_level_split.py`（+243，WP-19）
- `tests/test_codex_verdict_recovery.py`（+825，WP-16）
- `tests/test_gate_diff_start.py`（+22/-...，WP-21 相关；集成分支未改此文件，取 main 版）

**docs/plans/2026-09-14-codex-verdict-contract/（19 个）**：
codex-verdict 迭代的全部 tracked 工件（PLAN.md、PLAN-CODEX.status.json、WP-16~21 的
brief/status/answer/phase-tiers、HANDOFF-direct-finalization.md）。集成分支在此目录下
**tracked 文件数 = 0**（`git ls-tree -r plan/2026-09-13-parallel-throughput -- docs/plans/2026-09-14-codex-verdict-contract/` 为空），
故这 19 个文件是**纯新增**，无冲突。

> 注：P0-2 已删除主仓工作树里该目录的 6 份 **untracked 陈旧副本**。那 6 份不在 git 索引里，
> 与本次合并无关；合并引入的是 main 的 **tracked** 19 份，内容以 main 为准。

### §2.3 集成分支单边改动（合并时保留，无冲突）

集成分支自 merge-base 改动 178 个文件，main 均未碰（除 §2.1 的 gate/__init__.py）。
重点区域：

- `src/agentic_loop/gate/report.py`、`gate/qoder_security.py`、`gate/__main__.py`
- `src/agentic_loop/wrappers/finalize_merge.sh`、`preflight.sh`
- `src/agentic_loop/plan_cmd.py`、`validate_wp_status.py`、`autonomy.py`、`redispatch.py` 等
- `tests/` 下大量新增（test_finalize_merge_*、test_preflight_*、test_plan_* 等）
- `docs/plans/2026-09-13-parallel-throughput/` 全部 WP 工件
- `AGENTS.md`、`src/agentic_loop/templates/*`

这些文件 main 侧未改动，合并后原样保留。

### §2.4 §0 N3 点名的四个高风险区域实测

| 区域 | N3 预测 | 实测 | 结论 |
|---|---|---|---|
| `src/agentic_loop/adapters/codex.py` | 高风险（双边均改） | **集成分支从未改** | 无冲突，N3 证伪 |
| `gate/` | 高风险 | 仅 `gate/__init__.py` 双边，且区域不重叠 | clean |
| `wrappers/` | 高风险 | **main 侧零改动**（`git diff --name-only 0ef592e..main -- src/agentic_loop/wrappers/` 为空） | 无冲突，N3 证伪 |
| `docs/plans/` | 高风险 | main 侧仅改 `2026-09-14-codex-verdict-contract/`（集成分支无 tracked 文件）；集成分支仅改 `2026-09-13-parallel-throughput/`（main 未碰） | 无重叠，clean |

**四个点名区域全部无冲突。N3 的高风险判断基于"双边均改"的假设，实测该假设不成立。**

## §3 解冲突次序（预案）

**当前预演为零冲突，本节为应急预案**——若实际合并（P6 阶段，可能基于更新的 main/集成分支尖端）
出现冲突，按以下次序解决：

### 次序原则

1. **先源码后测试后文档**：源码冲突影响行为，须最先定夺；测试冲突次之；docs/plans 冲突
   通常是状态字段/brief 文本，最后处理。
2. **先双边后单边**：双边改动文件（如 gate/__init__.py）须逐块判断保留哪侧或融合；
   单边改动文件 git 已自动处理，无需人工。
3. **codex.py 若出现冲突**（仅当集成分支未来也改了 codex.py 才会发生）：**以 main 版为基**，
   因为 main 侧是 WP-16~21 的完整重写（+1305 行），集成分支侧若有改动多半是小幅适配；
   逐块把集成分支的适配补进 main 版，不反向。
4. **docs/plans/2026-09-14-codex-verdict-contract/ 若出现冲突**：以 main 版为准
   （该迭代已在 main 收敛，PLAN-CODEX=MERGED）；集成分支若引入了该目录的文件，
   属编号跨迭代混用（§0 N6），保留 main 版，集成分支版移入对应迭代目录或废弃。
5. **status.json 冲突**：按 AGENTS.md §5「On `--no-ff` the WP's own `status.json`
   conflicts with the double-signed main copy; resolve to the main copy (single source of truth)」。

### 具体步骤（若冲突）

```text
1. git merge --no-ff main            # 在集成分支上发起（P6 执行，非本批次）
2. git status --short                # 列出所有 UU/AA/DD 冲突文件
3. 按 §3 次序原则分组：源码组 / 测试组 / 文档组
4. 源码组逐文件：
   a. git diff --cc <file>            # 看双边改动
   b. 编辑解决，保留两侧有效改动
   c. git add <file>
5. 测试组逐文件：同 4，注意 test_gate_diff_start.py 这类双边可能都改了的
6. 文档组逐文件：status.json 取 main 版；brief 取更新 rev
7. git commit                        # 完成合并提交
8. 进入 §4 验证
```

## §4 验证步骤（合并后必做，P6 阶段执行）

合并完成后，**必须**按以下顺序验证，全部通过才算回并成功：

### 4.1 文本完整性

```bash
# 确认无残留冲突标记
git grep -n '^<<<<<<<\|^=======$\|^>>>>>>>' -- src/ tests/ || echo "no conflict markers"
# 确认工作树干净（除已知的 6 个禁区改动 + uv.lock）
git status --short
```

### 4.2 全量测试（基线重测，禁跨 lane 抄数）

```bash
python3.11 -m pytest tests -q
```

- **预期**：合并引入了 main 的 7 个 codex 测试文件（+3000 余行测试），总测试数会**显著增加**。
  集成分支原基线 4F/633P/4S 不再适用；须以合并后的实测为新基线。
- **关注**：main 侧 codex 测试是否依赖集成分支没有的 fixture/环境；若有失败，逐个判断是
  真回归还是环境差异。
- **4 个预存失败**（`test_finalize_merge_triple_sign.py` 的 `git checkout -q main` 前置失败）：
  CONVERGENCE-PLAN §3 注"该树清理后重测可能归零"——回并后 main 被合入集成分支，
  `agentic-loop-main-codex-merge` 工作树若仍占用 main 检出，这 4 个失败可能仍在。记录但不阻塞。

### 4.3 CLI 门禁复测（B7 教训：重装后抽检）

```bash
# plan check 应输出 PLAN_CHECK（P0-1 已验，回并后复测）
agentic plan check docs/plans/2026-09-13-parallel-throughput/PLAN-01.status.json
# dispatch-lint 行为一致性
agentic dispatch-lint docs/plans/2026-09-13-parallel-throughput/WP-26.status.json
# status 校验器（PYTHONPATH=src，CLI 无此子命令）
PYTHONPATH=src python3 -m agentic_loop.validate_wp_status docs/plans/2026-09-13-parallel-throughput/WP-29.status.json
```

### 4.4 editable 安装未漂移

```bash
# 回并后 agentic 仍须指向本仓 editable
cat /Users/admin/.local/share/uv/tools/agentic-loop/lib/python*/site-packages/*.dist-info/direct_url.json
# 预期：{"url":"file:///Users/admin/vibe/agentic_loop","dir_info":{"editable":true}}
```

若回并过程触发了 `uv tool` 重装或 direct_url.json 漂移，须重跑 `uv tool install --force --editable .`。

### 4.5 gate/__init__.py 语义验证（唯一双边文件）

```bash
# 确认两侧改动都在：main 的 +11 与集成分支的 path_is_in_worktree + _GIT_SELECTION_VARS
grep -n "path_is_in_worktree\|_GIT_SELECTION_VARS\|git_merge_base" src/agentic_loop/gate/__init__.py
# 跑相关测试
python3.11 -m pytest tests/test_worktree_detection.py tests/test_gate_diff_start.py -q
```

### 4.6 codex.py 引入后的适配验证

main 的 codex.py 是 +1305 行大重写。集成分支的 gate/wrappers 是否与新 codex adapter 兼容，
git 检测不到。须实测：

```bash
# codex adapter 相关测试（main 引入的 7 个文件）
python3.11 -m pytest tests/test_codex_*.py -q
# 若集成分支有引用 codex adapter 的代码，确认导入不破
python3.11 -c "from agentic_loop.adapters import codex; print('import ok')"
```

## §5 风险登记

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 语义冲突：main 的 codex adapter 重写与集成分支的 gate/wrappers 改动在运行时不兼容 | 中 | 高（测试失败/门禁误判） | §4.6 实测；若失败，逐个适配，不反向回退 main 的 codex.py |
| R2 | 预演基于当前尖端；P6 执行时 main/集成分支可能又有新提交，冲突面变化 | 中 | 中 | P6 执行前重跑 `git merge-tree --write-tree` 复测 |
| R3 | 合并引入 main 的 19 份 codex-verdict 迭代文档，与集成分支的编号混用（§0 N6）加剧 | 低 | 低（仅文档） | 合并后在报告里记录；不阻塞 |
| R4 | 4 个预存测试失败（test_finalize_merge_triple_sign）在回并后仍在，被误判为回并引入 | 中 | 低 | §4.2 已注明；与 `agentic-loop-main-codex-merge` 工作树占用 main 检出相关，该树清理后复测 |
| R5 | editable 安装在回并过程中漂移（B7 复发） | 低 | 高（门禁结论失效） | §4.4 复测 direct_url.json |
| R6 | merge-tree 预演与真实 `git merge` 行为差异（merge-tree 不处理 rename/copy 检测的某些边界） | 低 | 中 | P6 执行时以真实 merge 为准；预演仅作风险预判 |

## §6 与 CONVERGENCE-PLAN §1 P6 的衔接

P6 第 1 步："回并 main 进集成分支（按 P0-5 runbook 解冲突）→ 全量重测"。

本 runbook 的结论是**当前预演零冲突**，故 P6 第 1 步的"解冲突"环节预期为空操作；
但 §4 的验证步骤**全部必做**，且 §5 R2 要求 P6 执行前重跑预演（尖端可能已变）。

P6 执行序（建议）：
1. 重跑 `git merge-tree --write-tree plan/2026-09-13-parallel-throughput main`，确认仍 zero-conflict
2. `git merge --no-ff main`（在集成分支上）
3. §4.1 文本完整性
4. §4.2 全量测试（建立合并后新基线）
5. §4.3 CLI 门禁复测
6. §4.4 editable 未漂移
7. §4.5 gate/__init__.py 语义验证
8. §4.6 codex.py 适配验证
9. 全部通过 → 进入 P6 第 2 步（plan check → lint → merge → finalize）

## §7 证据索引

- `git merge-tree --write-tree plan/2026-09-13-parallel-throughput main` → `9d5656ac…`，exit 0
- `git merge-base main plan/2026-09-13-parallel-throughput` → `0ef592e`
- `git rev-list --count`：integration ahead 209 / main ahead 45 / local main ahead origin/main 28
- `git diff --name-only 0ef592e..main` → 28 文件
- `git diff --name-only 0ef592e..plan/2026-09-13-parallel-throughput` → 178 文件
- `comm -12` 重叠 → 仅 `src/agentic_loop/gate/__init__.py`
- `git diff --name-only 0ef592e..plan/2026-09-13-parallel-throughput -- src/agentic_loop/adapters/` → 空（集成分支未改 adapters）
- `git diff --name-only 0ef592e..main -- src/agentic_loop/wrappers/` → 空（main 未改 wrappers）
- `git ls-tree -r plan/2026-09-13-parallel-throughput -- docs/plans/2026-09-14-codex-verdict-contract/` → 0 文件
- `git ls-tree -r main -- docs/plans/2026-09-14-codex-verdict-contract/` → 19 文件
- `git diff --stat plan/2026-09-13-parallel-throughput 9d5656ac…` → 28 文件 +6276/-84
- 原始预演输出留存：`/tmp/agentic-p0-baseline-20260920/merge-tree-raw.txt`

---

**本文件是只读预演产物，不执行任何合并。实际回并属 P6 阶段，须用户批准（CONVERGENCE-PLAN §2 #9）。**
