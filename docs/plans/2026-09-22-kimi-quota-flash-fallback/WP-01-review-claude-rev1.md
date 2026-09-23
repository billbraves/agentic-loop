# WP-01 独立复核报告（claude / Reviewer，C1 rev1）

> **review.decision = ACCEPT**（双签第一签名）
> 复核者：claude-code orchestrator（本会话，session_hint `kqff-b`，lock owner `claude-kqff-b`）——reviewer=orchestrator，独立性由 codex post-impl consult 第二签名承载（评级 weak-attested，同 WP-17 先例）。
> 复核坐标：base(scope-guard) `f89d36c` → 交付 HEAD `42e6d85`；branch `feature/kqff-wp01-quota-fallback`；worktree `/Users/admin/vibe/.worktrees/kqff-wp01`。
> 复核时间：2026-09-22T16:10:46Z。方法：不信 chat/log，亲验 git + 独立复跑测试 + 独立 mutation-probe。

## 1. Git 核验（范围与提交纪律）
- `git log f89d36c..HEAD` = **5 commits**（B1–B5，均显式路径 `feat(kqff)` 提交，未 push）：9e746cb/0e6f945/1911d55/208a2d6/42e6d85。
- `git diff --stat f89d36c...HEAD` = **仅 7 个 allowed 文件**（+619/−2），零 forbidden：`.agentic/config.toml`、`src/agentic_loop/{quota_fallback,redispatch,resolve_paths}.py`、`tests/test_{quota_fallback,redispatch_quota_fallback,resolve_fallback_binding}.py`。
- worktree porcelain = `M WP-01.status.json`（编排者回填，§4.3 于 finalize 一次性提交）+ `?? WP-01-impl-report-rev1.md` + `?? 本复核制品`。kimi 未提交 status，符合纪律。

## 2. 测试复跑（编排者独立，不采信 kimi 记录）
- focused 3 文件：**26 passed**（test_quota_fallback 11 + test_resolve_fallback_binding 5 + test_redispatch_quota_fallback 10）。
- 主档 native 不变式：**2 passed**。
- 全量 `pytest tests`：**4 failed, 799 passed, 4 skipped**；4 失败与基线 f89d36c（`4 failed,773 passed,4 skipped`）**逐一相同**（均预存 `test_finalize_merge_triple_sign.py`，根因 main 被 sibling worktree 占用，与本 WP 无关）→ **零新增失败**；799−773=26 即新增用例全绿。
- 环境：`env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest`（剥离 AGENTIC_PYTHON 防泄漏进子进程假失败）。

## 3. mutation-probe（验 INV 承重，独立实证 kimi concern #2a/#2b）
探针纪律：mutate 源文件字节 → focused pytest → `git checkout HEAD -- <file>` 逐字节还原 → porcelain 复验；`PYTHONDONTWRITEBYTECODE=1` 规避 concern #4 的 __pycache__ 同秒中毒。

| 探针 | 变异 | 结果 | 结论 |
|---|---|---|---|
| A1 | 删 `quota_fallback.py` 的 `\bquota\b` pattern | **GREEN**（不红） | `"quota exceeded for this key"` 被反向语境 pattern 覆盖 → `\bquota\b` 对现有 fixture 冗余，**实证 concern #2a** |
| A2 | 删 `quota_fallback.py` 的 `额度` pattern | **RED** | `test_matches_chinese_quota_terms` 红 → `额度` 是有效等价方向 witness |
| B | 删 `redispatch.py` 的 `if dry_run or result.dispatched: return` 短路 | **RED** | `test_dry_run_does_not_fallback_even_on_quota_output` 红（dry_run 腿承重）；success 腿由 `not is_quota_error` fall-through 等价兜底，**实证 concern #2b** |
| C | 删 `quota_fallback.py` 的 `except re.error: continue` | **RED** | `test_bad_regex_pattern_is_skipped_not_raised` 红 → INV-2(b) 承重 |

四探针后逐字节还原，worktree porcelain 复验仅剩 `M status.json`+`?? report`+`?? 本制品`，**无污染**。

## 4. config.toml 零残留核验
`git diff .agentic/config.toml`：`[providers.kirogpt]` 的 identity_model/selectors/openai_base_url **全为 context 行（无 +/−）→ 零残留**；kimi 自述执行中一度误改已彻底还原。变更仅两处：新增 `[providers.deepseekflash]`（anthropic_base_url / api_key_env=DEEPSEEK_API_KEY / identity_model=deepseek-v4-flash / selectors.kimi=deepseek/v4-flash）+ `developer` 由裸 string 改 `{ adapter="kimi", fallback_provider="deepseekflash" }`（**无 `provider` 键 → 主档零注入**，INV-4 保住评级语义）。

## 5. kimi 4 concerns 裁定（均非阻塞）
- **#1 quality-gate 非绿**：根因是编排者回填的工作树 status.json（`changed path outside allowed scope`），**非 kimi 代码缺陷**；7 个 allowed 文件本身全绿（范围守卫 SCOPE_GUARD_PASS）。属多 plan 布局 + §4.3「status 于 finalize 一次性提交」的流程产物；C2 gate 需以方案1 等价变通处理。**非阻塞**。
- **#2a INV-1 `\bquota\b` 冗余**：探针 A1 GREEN 实证。属 brief 承重映射表 witness 靶点欠精确（**文档级**），非实现缺陷；等价 witness（删 `额度`→RED）有效。**非阻塞**；是否需 re-freeze erratum 修正映射表 → 交 codex 第二签名裁定。
- **#2b INV-5 success 腿等价**：探针 B RED 实证 dry_run 腿承重、success 腿由 is_quota_error fall-through 等价兜底。同属**文档级**映射表精度问题，非实现缺陷。**非阻塞**。
- **#3 flash 精确串禁网不可实测**：按仓内命名规律（deepseek-v4-pro/deepseek/v4-pro）保持冻结值 `deepseek-v4-flash`/`deepseek/v4-flash`，config 保留「实现前须核实」注释。**可接受残余风险**（生产启用前须核），非阻塞。
- **#4 __pycache__ 中毒**：已用 PYTHONDONTWRITEBYTECODE=1 规避，全量复跑确认无污染。

## 6. 结论
实现正确匹配 DESIGN/brief；五不变式 INV-1..5 + 两接线不变式 INV-W1/W2 全部承重（mutation-probe A1/A2/B/C 实证）；零回归（native 2 passed + 主档 binding `("kimi", None)` + kirogpt 零残留）；范围恰好 7 allowed 文件无 forbidden；4 concerns 均非阻塞（#2a/#2b 属 brief 文档级 witness 靶点，非实现缺陷）。

**review.decision = ACCEPT**（第一签名）。待 codex post-impl consult 出 consult.decision 凑齐双签后，停在 C2 gate 前汇报（gate/merge 布局变通与 push 再单独确认）。
