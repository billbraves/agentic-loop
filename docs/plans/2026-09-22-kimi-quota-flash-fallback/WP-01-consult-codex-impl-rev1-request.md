# 独立顾问复核请求 — kqff WP-01「实现后双签」（post-impl merge-gate consult, rev1）

## 0. 你的角色与硬边界
你是本仓 AGENTS.md §2 定义的 **Architecture and Incident Consultant（codex, provider kirogpt）**。
这是一次 **实现后独立双签复核**（merge-gate 第二签名），针对**已交付**的 kqff WP-01。
你以 `--sandbox read-only` 运行：**只读、只分析**。禁止：改任何文件 / merge / push / 动锁 / 写 status / 运行会写盘的命令。
你的最终消息必须是**且仅是**一个 JSON 裁决对象（见 §6 OUTPUT CONTRACT）。

## 1. plan 目标与硬约束
`plan/2026-09-22-kimi-quota-flash-fallback`（kqff）：让 `agentic redispatch` 在 **kimi 套餐额度不足导致派发失败**时，**自动单跳回退** `deepseek-v4-flash`（provider 段名 `deepseekflash`）。
硬约束（任一被破坏即阻断）：
- **配置驱动**：额度模式与 fallback provider 均可由 `.agentic/config.toml` 覆盖，缺省 fail-safe 回落内置默认。
- **零回归 / 主档语义不变**：主档 developer binding 仍须 `("kimi", None)`；独立性评级语义完全不变；不得动 `[providers.kirogpt]`。
- **额度检测不得误报**：歧义词无账户语境（`test count exceeded` / `insufficient permissions` / `billing module failed` / 非账户 `credit`）必须判 **False**，且 wrapper 不构造 fallback。
- **单跳到底**：额度失败恰好重派一次 flash；flash 也额度失败即 STOP 交人工，绝不无限重试。
- **回退不写 status / 不动锁 / 不计数**：回退成功 `redispatch_count` 只 +1；circuit-breaker（`count>=REDISPATCH_MAX`）必须先于任何派发/构造。

## 2. 交付坐标（可自行只读核验）
- base（scope-guard 基线）`f89d36cedb9b0c79d9574511329e8b83cd6c86f3`
- 交付 HEAD `42e6d85f6c6751c754b1985a1a1ff580e7099e68`（5 次显式路径 feat 提交 B1–B5，**未 push**）
- branch `feature/kqff-wp01-quota-fallback`；worktree `/Users/admin/vibe/.worktrees/kqff-wp01`
- diff 范围：**仅 7 个 allowed 文件**（+619/−2），无任何 forbidden：
  `.agentic/config.toml`、`src/agentic_loop/{quota_fallback,redispatch,resolve_paths}.py`、
  `tests/test_{quota_fallback,redispatch_quota_fallback,resolve_fallback_binding}.py`
- 完整 diff 见文末「§7 DELIVERY DIFF」（703 行，base→HEAD 全量）。
- **不要运行 pytest**：read-only sandbox 下写 `__pycache__`/`.pytest_cache` 会失败；测试与变异证据编排者已亲验，见 §4/§5。

## 3. 冻结 brief 的验收标的：五项不变式 + 两条接线不变式
（不变式是验收标的本体；编号台账只作破口清单。承重变异均施于**源文件字节 / 活树配置**，「还原→转红」双向验证。）

- **INV-1 额度语义正确判定**：语境命中→True，歧义词无账户语境→False。承重测试 `test_matches_chinese_quota_terms`/`test_matches_english_quota_terms`/`test_case_insensitive`/`test_ambiguous_phrases_are_not_quota_errors`。变异：删 `re.IGNORECASE`→大小写用例红；语境正则放宽为裸词 `insufficient`→歧义负例红；删某正向 pattern→对应正向红。
- **INV-2 fail-safe 三承重点**：(a1) 畸形 TOML 回落默认（`load_quota_patterns` 的 `except Exception`）；(a2) 空列表/错误类型回落默认（isinstance/非空守卫）；(b) 语法非法正则跳过不抛（`is_quota_error` 的 `except re.error: continue`，**非** `load_quota_patterns`——后者不编译正则）。各绑专属 witness 用例。
- **INV-3 fallback binding 解析零回归**：role 非 dict / 无 `fallback_provider` / provider 段缺失 / 配置非法（`except ProviderConfigError`）→ 一律返回 None，**绝不抛**。
- **INV-4 主档零回归**：`developer` 由裸 string 改 dict 后，`resolve_role_binding("developer")` 仍返回 `("kimi", None)`（无 `provider` 键→主档零注入），否则评级语义会变。承重测试 `test_project_config_primary_developer_stays_native`；变异施于**活树** config，逐字节还原 + `git diff` 空核验。
- **INV-5 派发编排**：单跳回退（成功/非额度/未配/dry_run 不回退；额度失败恰好重派一次；flash 也失败即 STOP）+ 计数/circuit-breaker 接线（回退成功只 +1 = **INV-W1**；circuit-breaker 先于派发 = **INV-W2**）。变异：删 `if dry_run or result.dispatched: return` 短路；改单跳为循环；`count+1`→`count+2`（M1）；wrapper 调用移到 circuit-breaker 前（M2）。

## 4. 编排者 C1 独立复核（第一签名，claude/Reviewer）— 结论 ACCEPT
不信 chat/log，亲验：
- git：`log f89d36c..HEAD` = 5 commits；`diff --stat` = 仅 7 allowed 文件（+619/−2），无 forbidden；worktree porcelain 仅 `M WP-01.status.json`（编排者回填）+ `?? WP-01-impl-report-rev1.md`。
- 测试：focused 3 文件 **26 passed**（11+5+10）；主档 native 不变式 **2 passed**；全量 `4 failed, 799 passed, 4 skipped`——4 失败与基线 f89d36c（`4 failed,773 passed,4 skipped`）**逐一相同**（均为预存 `test_finalize_merge_triple_sign.py`，根因 main 被 sibling worktree 占用），**零新增失败**；799−773=26 即新增用例全绿。
- config：`git diff .agentic/config.toml` 亲验 `[providers.kirogpt]` 的 identity_model/selectors/openai_base_url **全为 context 行（无 +/−）→ 零残留**；kimi 自述执行中一度误改已彻底还原。
- **mutation-probe（编排者独立复跑，PYTHONDONTWRITEBYTECODE=1 规避 concern #4）**：
  - **A1** 删 `\bquota\b` → **GREEN**（不红）：实证 `"quota exceeded for this key"` 被反向语境 pattern 覆盖，`\bquota\b` 对现有 fixture 冗余 → **证实 kimi concern #2a**。
  - **A2** 删 `额度` → **RED**：`test_matches_chinese_quota_terms` 红 → `额度` 是有效的等价方向 witness。
  - **B** 删 `if dry_run or result.dispatched: return` 短路 → **RED**：`test_dry_run_does_not_fallback_even_on_quota_output` 红（dry_run 腿承重）；success 腿由 `not is_quota_error` fall-through 等价兜底 → **证实 kimi concern #2b**。
  - **C** 删 `except re.error: continue` → **RED**：`test_bad_regex_pattern_is_skipped_not_raised` 红（INV-2(b) 承重）。
  - 四探针后 `git checkout HEAD -- <file>` 逐字节还原，worktree porcelain 复验仅剩上述 M/??，无污染。

## 5. kimi 交接的 4 项 concerns（逐字捕获，请你独立裁定，不要照抄我的判断）
1. **`agentic quality-gate` 当前非绿，根因不是我的改动**：`STATUS_VALID` 之后报 `QUALITY_GATE_FAIL: changed path outside allowed scope: docs/plans/.../WP-01.status.json`。该 `M` 是派发时**编排者侧对工作树 status.json 的回填**（dispatch_commit 等），kimi 按纪律不提交/不改写 status。等编排者按 §4.3 在 freeze/finalize 处理 status 后 gate 即可过；7 个 allowed 文件本身全绿（范围守卫 PASS 可证）。
2. **两处承重变异与 brief 映射表的预期 witness 有偏差（判据本体，kimi 不自行改判据）**：
   - INV-1「删 `\bquota\b` → 对应正向红」实测**不红**：`"quota exceeded for this key"` 同时被反向语境 pattern `(balance|...|quota|...)\W{0,20}(...|exceeded|...)` 覆盖，`\bquota\b` 对现有 fixture 冗余。改用同方向等价变异「删 `额度`」实测转红。建议 codex review 时确认是否接受该等价 witness，或删冗余 pattern（后者需 re-freeze，kimi 未动）。
   - INV-5「删 dry_run/dispatched 短路 → success/dry_run 红」实测**只有 dry_run 红**：`test_success_no_fallback` 输出 `"done"` 不命中额度模式，删短路后走 `not is_quota_error → return (result, None)` 殊途同归，该 fixture 上行为等价。dry_run 腿承重有效；success 腿若需承重需换额度命中型成功 fixture（不可能）或承认该腿由「额度判定误报」风险另行覆盖。
3. **flash 精确串（DESIGN §10.1）**：禁网约束下无法对 DeepSeek 活 API / kimi 模型注册表实测；已按仓内既有约定核实（`init_cmd.py`/QUICKSTART 的 `deepseek-v4-pro`/`deepseek/v4-pro` 命名规律），保持冻结值 `deepseek-v4-flash`/`deepseek/v4-flash`，config 注释保留「实现前须核实」标注。
4. **执行中发现并记录**：快速「变异→还原」循环曾致 `__pycache__` 同尺寸同秒 pyc 中毒（`count+2` 字节码残留致还原后假红）；清 `__pycache__` 后恢复全绿，最终全量已复跑确认。供后续 mutation-probe（C1）参考。

## 6. 请你回答的具体问题（在 findings/rationale 中逐条给证据）
- **Q1（concern #2a）**：`\bquota\b` 对现有 fixture 是否**真冗余**？删 `额度`→RED 的**等价 witness 是否可接受**？brief INV-1 承重映射表是否**需要 re-freeze erratum**（修正「删 `\bquota\b`→红」这一预期），还是实现原样即可 ACCEPT？这是阻断项吗？
- **Q2（concern #2b）**：success 腿由 `not is_quota_error` fall-through 等价兜底（而非短路本身承重）是否可接受？INV-5 映射表「success/dry_run 红」是否需修正为「dry_run 红；success 腿等价」？阻断吗？
- **Q3（concern #1）**：确认 quality-gate 非绿纯属**编排者 status 回填 + 多 plan 布局**的流程产物，**非代码缺陷**；C2 gate 是否可在「status 于 finalize 一次性提交」后转绿？
- **Q4（concern #3）**：flash 精确串禁网不可实测——保持冻结值 + config「实现前须核实」注释，是否为**可接受的残余风险**，还是需在生产启用前追加动作？
- **Q5（零回归）**：独立确认主档 developer binding 仍 `("kimi", None)`、独立性评级语义不变、`[providers.kirogpt]` 零残留、`resolve_role_fallback_binding` 各非法输入均 None 不抛。
- **Q6（架构/安全/时间-数据语义）**：单跳回退设计、fail-safe 模式加载（`except Exception` 是否过宽到吞掉真实配置错误？）、`ProviderConfigError` 处理、额度正则的 ReDoS/灾难性回溯风险、`REDISPATCH_QUOTA_FALLBACK` 日志是否泄漏敏感信息——有无**阻断性**问题？

## 7. OUTPUT CONTRACT（你的最终消息必须是且仅是一个 JSON 对象，无前后缀散文）
```json
{"decision":"ACCEPT|REWORK|CONSULT","rationale":"<引用你实际核验的证据：具体 文件:行 / diff hunk / 不变式编号>","findings":[{"severity":"blocker|major|minor|note","title":"...","detail":"...","evidence":"file:line 或 diff hunk 引用"}]}
```
- `decision` 严格三选一；严重度序 **REWORK > CONSULT > ACCEPT**（任一 blocker/major 未闭环 → 不得 ACCEPT）。
- **禁止伪签**（本仓 WP-21 已立此判据）：rationale/findings 若照抄本 prompt、零审查证据 → 视为无效签名。你必须体现对 §7 diff 的独立核验（引用具体行/hunk）。
- 逐条覆盖 Q1–Q6；对 concern #2a/#2b 明确给出「等价 witness 可接受 / 需 re-freeze erratum / 阻断」三选一结论。

## §7 DELIVERY DIFF（base f89d36c → HEAD 42e6d85，全量 703 行，紧随其后）


<!-- 派发时此处追加了 703 行 delivery diff（git diff f89d36c...42e6d85），可从 worktree 复现，故不冗余入库。 -->
