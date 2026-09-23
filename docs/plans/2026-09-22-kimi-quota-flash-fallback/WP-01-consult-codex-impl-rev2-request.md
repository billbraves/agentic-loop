<!-- 本制品 = 发给 codex 的 consult 请求头（§0-§8）。完整 prompt 另含 §8 rework delta diff
     (git diff 42e6d85...4035f06) + §9 full delivery diff
     (git diff f89d36c...4035f06)，均可由 git 在 worktree 复现，故不内联。
     session 01a0cb7e-e89f-7042-99d8-f505029d49a5 | CODEX_EXIT=0 | verdict=ACCEPT（见 WP-01-consult-codex-impl-rev2-answer.md）。 -->

# 独立顾问复核请求 — kqff WP-01「实现后双签 · REWORK 复签」（post-impl merge-gate consult, impl rev2）

## 0. 你的角色与硬边界
你是本仓 AGENTS.md §2 定义的 **Architecture and Incident Consultant（codex, provider kirogpt）**。
这是一次 **实现后独立双签复核的 REWORK 复签**（merge-gate 第二签名，impl rev2），针对你 **rev1 判 REWORK 后、kimi 已 rework** 的 kqff WP-01。
你以 `--sandbox read-only` 运行：**只读、只分析**。禁止：改任何文件 / merge / push / 动锁 / 写 status / 运行会写盘的命令。
你的最终消息必须是**且仅是**一个 JSON 裁决对象（见 §7 OUTPUT CONTRACT）。**这是全新会话，你无 rev1 记忆**——本报告 §3 逐字重述你的 rev1 verdict 供你核对闭环。

## 1. plan 目标与硬约束
`plan/2026-09-22-kimi-quota-flash-fallback`（kqff）：让 `agentic redispatch` 在 **kimi 套餐额度不足导致派发失败**时，**自动单跳回退** `deepseek-v4-flash`（provider 段名 `deepseekflash`）。
硬约束（任一被破坏即阻断）：
- **配置驱动**：额度模式可由 `.agentic/config.toml` 覆盖，缺省 fail-safe 回落内置默认（`DEFAULT_QUOTA_PATTERNS`）。**注**：fallback provider **没有**内置默认——未配置 = 额度失败即 STOP = 零回归（设计意图，见 §3 #2）。
- **零回归 / 主档语义不变**：主档 developer binding 仍须 `("kimi", None)`；独立性评级语义完全不变；不得动 `[providers.kirogpt]`。
- **额度检测不得误报**：歧义词无账户语境（`test count exceeded` / `insufficient permissions` / `billing module failed` / 非账户 `credit`）必须判 **False**，且 wrapper 不构造 fallback。
- **单跳到底**：额度失败恰好重派一次 flash；flash 也额度失败即 STOP 交人工，绝不无限重试。
- **回退不写 status / 不动锁 / 不计数**：回退成功 `redispatch_count` 只 +1（INV-W1）；circuit-breaker（`count>=REDISPATCH_MAX`）必须先于任何派发/构造（INV-W2）。

## 2. 交付坐标（可自行只读核验）
- base（scope-guard 基线）`f89d36cedb9b0c79d9574511329e8b83cd6c86f3`
- **rework 交付 HEAD `4035f06d535d0675b559b8f10f52ec9ac47af1be`**（在 rev1 的 5 次 feat 提交之上新增 **1 次** rework feat 提交，共 6 commits，**未 push**）
- rev1 交付 HEAD（你 rev1 复核对象）`42e6d85f6c6751c754b1985a1a1ff580e7099e68`
- branch `feature/kqff-wp01-quota-fallback`；worktree `/Users/admin/vibe/.worktrees/kqff-wp01`
- **完整最终交付** diff（`f89d36c...4035f06`）：**仅 7 个 allowed 文件**（+713/−2），无任何 forbidden —— 见文末「§9 FULL DELIVERY DIFF」。
- **rework delta** diff（`42e6d85...4035f06`）：**仅 5 个文件**（+99/−5；2 源 `resolve_paths.py`/`quota_fallback.py` + 3 测试），`redispatch.py`/`config.toml` **本轮未改** —— 见文末「§8 REWORK DELTA DIFF」。
- 冻结基线：brief **rev7**（sha256 `a5b72c39…`，你 rev7 brief 复签 = ACCEPT，session 01a0cb50）；其 `## Rework rev7 闭环 spec`（§R1–§R4）是本轮 rework 的唯一权威 delta。
- **不要运行 pytest**：read-only sandbox 下写 `__pycache__`/`.pytest_cache` 会失败；测试与变异证据编排者已亲验，见 §5。

## 3. 你的 rev1 REWORK verdict（8 findings）+ 编排者裁定 + rework 闭环（逐条核对此节）

你 rev1 判 **REWORK**（session 01a0c9dd），8 findings。编排者独立核实后裁定 + 用户定夺（Q1=修 #1 + 硬化 #8；Q2=批准 re-freeze erratum），rework 如下闭环：

- **#1（major，实现阻断）INV-3 对非法 provider 配置并非一律 None 不抛** → **已修（§R1，NARROW）**。`resolve_paths.py` 把 `build_binding(...)` 调用点的 `except ProviderConfigError` **拓宽为 `except Exception`**（**窄作用域**：try 块仅包 `build_binding`；`get_roles_raw(repo)` 仍在 try **外**未动）。**范围决策（NARROW，用户定夺 + 你 rev7 brief 复签独立采纳）**：本 WP 新增崩溃面只是 `selectors` 非 dict → `build_binding` 内 `AttributeError`；**畸形 config 文件（TOML）不在范围内**——它在 `get_roles_raw`（`resolve_paths.py:401`，try 外）逃逸，且 primary `resolve_role_binding`（`:361`）同样未捕获，是两条路径**共享的既有失败**、非本 WP 新增（你 rev7 独立验证派发链在解析 fallback 前必经 primary binding 解析 `redispatch.py:480,532,538`，只 BROADEN fallback 无保护作用反造成不对称）。docstring 同步收窄；新增 2 承重测试 `test_none_when_selectors_is_{string,list}_no_raise`；**未加畸形 TOML 用例**（范围外）。
- **#2（major）缺省 fallback provider 未回落内置默认** → **非缺陷，未改（裁定）**。此为编排者 rev1 consult prompt 措辞错误：brief 交付物清单 + DESIGN 明写**只有 quota patterns 有内置默认，fallback provider 没有**；未配 = 额度失败即 STOP = **零回归**（设计意图）。实现正确。
- **#3（major）quality-gate 未闭环** → **流程/布局，非代码（裁定）**。gate 的 changed-set 含工作树 dirty/untracked（编排者按 §4.3 回填的 status + 制品），触发「outside allowed scope」；**7 个代码文件本身全绿**（范围守卫 PASS 可证）。C2 gate 从干净状态源跑（status 于 finalize 一次性提交，方案1 等价变通），非 kimi rework 范围。
- **#4（minor）INV-1 台账「删 `\bquota\b`→红」不成立** → **已修（brief rev7 §R3 台账勘误）**。实证 `quota exceeded` 亦被语境正则命中，删裸词 `\bquota\b` 仍绿（冗余）；真正承重裸词是 `额度`（删之 `test_matches_chinese_quota_terms` 转红）。台账已更正（brief 文档级，kimi 未改 brief）。
- **#5（minor）success 短路无独立承重** → **已修（brief rev7 §R3 + 新测试）**。新增 `test_success_with_quota_like_output_no_fallback`（primary dispatched=True + output 含额度词 `"build ok; note: weekly quota reset scheduled"` → 短路优先、`built==[]`、`prov is None`）；删短路则转红 = success 腿独立承重。`test_success_no_fallback`（output `"done"`）标注为等价 witness。
- **#6（minor）flash 精确串禁网不可实测** → **残余风险（裁定，未改）**。保留冻结值 `deepseek-v4-flash`/`deepseek/v4-flash` + config「实现前须核实」注释；列为 **C4/生产启用前显式前置**（非生产凭据最小 probe）。
- **#7（note）其余零回归/单跳/日志边界成立** → **确认（与 C1/C1' 一致，未改）**。
- **#8（minor，用户批准一并硬化）ReDoS 面 + 静默吞配置故障** → **已修（§R2，采你 rev6 F2 off-ramp）**。**(a) §R2a 尾窗已删除**：你 rev6 brief 复签 F2 实证尾窗（`_MAX_SCAN_CHARS`）**只界长度不界时间**（`(a+)+$` 31 字符串即 0.25s 超时）+ **引入检测回归**（头部额度串 + >64KB 尾随 → 漏检），且 config patterns 本 operator-trusted → **rev7 删除整个 §R2a**，保留全文 `re.search`，仅模块 docstring 注明 custom patterns operator-trusted/禁不可信注入。**(b) §R2b 脱敏诊断已加**：`load_quota_patterns` 的 `except Exception: pass` → 回落 DEFAULT 前打**一行脱敏诊断**（固定文案 + `type(exc).__name__`，绝不含 config 原文/路径/密钥）；新增 `test_load_patterns_emits_redacted_diagnostic_on_fault`（哨兵 `SECRET_SENTINEL_DO_NOT_LEAK` 不在 stderr）。

## 4. 冻结 brief 的验收标的：五项不变式 + 两条接线不变式（INV-3 已按 rev7 NARROW 更新）
- **INV-1 额度语义正确判定**：语境命中→True，歧义词无账户语境→False。承重裸词是 `额度`（rev7 #4 勘误：`\bquota\b` 对现有 fixture 冗余，受语境正则覆盖）。
- **INV-2 fail-safe 三承重点**：(a1) 畸形 TOML 回落默认（`load_quota_patterns` 的 `except Exception`）；(a2) 空列表/错误类型回落默认（isinstance/非空守卫）；(b) 语法非法正则跳过不抛（`is_quota_error` 的 `except re.error: continue`）。
- **INV-3（rev7 NARROW）fallback binding 解析对 provider 配置形状零抛**：role 非 dict / 无 `fallback_provider` / provider 段缺失或非 dict / `selectors` 非 dict（字符串/列表）/ `build_binding` 内任意异常 → 一律 `except Exception` 回落 None + 脱敏诊断，**绝不抛进派发主链**。**范围界定**：畸形 config **文件**（TOML）不在此不变式内（`get_roles_raw` try 外逃逸，与 primary 共享的既有失败，范围外）。
- **INV-4 主档零回归**：`resolve_role_binding("developer")` 仍返回 `("kimi", None)`；rework 的 NARROW 修法**不得**触碰 primary。
- **INV-5 派发编排**：单跳回退 + 计数/circuit-breaker 接线（INV-W1 回退成功只 +1；INV-W2 circuit-breaker 先于派发）。rev7 #5：success 腿由 `test_success_with_quota_like_output_no_fallback` 独立承重、dry_run 腿由 `test_dry_run_does_not_fallback_even_on_quota_output` 承重。

## 5. 编排者 C1' 独立复核（第一签名 on rework，claude/Reviewer）— 结论 ACCEPT
不信 chat/log，亲验（详见 worktree `WP-01-review-claude-rev2.md`）：
- **git**：rework delta `42e6d85...4035f06` = **恰好 5 allowed 文件 +99/−5**，无 forbidden/docs/plans/`redispatch.py`/`config.toml`；一次 feat 提交（显式路径）；编排者制品（2 M + 8 ??）仍未提交、未被 kimi 触碰。
- **测试**：focused 3 文件 **30 passed**（collect-only 计数 **12/7/11** 精确匹配 §R4）；全量 **803 passed / 4 failed / 4 skipped（177.88s）**——4 失败**全部**预存 `test_finalize_merge_triple_sign.py`（根因 `git checkout -q main` 非零退出 = main 被 sibling worktree 占用的环境基线），**零新增失败**；803 = 799(rev1)+4(rework 新测试)。
- **C1' probe**（临时 repo，只读，OVERALL PASS）：**INV-3** `selectors="SECRET_SENTINEL_DO_NOT_LEAK"`（字符串）→ `resolve_role_fallback_binding` = **None，未抛**；**INV-4** 同 config 下 `resolve_role_binding("developer")` = **`('kimi', None)`** 不变；**§R1 脱敏** stderr = `resolve_role_fallback_binding: provider config invalid (AttributeError); falling back to no quota fallback`（哨兵 absent、固定前缀）；**§R3 承前提** `is_quota_error("build ok; note: weekly quota reset scheduled")` = **True**（删短路则转红 = 真承重）；`resolve_paths.py:16 import sys` 存在（except 块 `print(file=sys.stderr)` 无 NameError）。
- **§R2a 确未实现**：`git grep -nE '_MAX_SCAN_CHARS|tail.?window|65536'` 于 `quota_fallback.py` = 空；`is_quota_error` 全文 `re.search` 未改。

## 6. 请你回答的具体问题（在 findings/rationale 中逐条给证据，引用 §8/§9 具体行/hunk）
- **Q1（#1 闭环）**：§R1 的 `except Exception`（窄作用域，仅包 `build_binding`，`get_roles_raw` 在 try 外未动）是否**充分闭环**你 rev1 的 #1？**NARROW 范围决策**（畸形 TOML 属范围外、与 primary 共享的既有失败）对 **merge gate** 是否可接受，还是仍须在本 WP 内 BROADEN？
- **Q2（#8 硬化）**：§R2b 脱敏诊断（固定文案 + 类名）是否**充分**？§R2a 尾窗删除（采你 rev6 F2 off-ramp，改 operator-trusted docstring）是否**正确处置**（无检测回归、无行为变更）？
- **Q3（#4/#5）**：§R3 台账勘误 + `test_success_with_quota_like_output_no_fallback` 是否使 success 腿**独立承重**（编排者实证 `is_quota_error("...weekly quota reset...")=True`，删短路→红）？
- **Q4（零回归）**：独立确认主档 `("kimi", None)`、`[providers.kirogpt]` 零残留、独立性评级语义不变、全量仅 4 预存失败零新增、`resolve_role_fallback_binding` 各非法输入均 None 不抛。
- **Q5（范围）**：rework delta 5 文件是否全在 allowed_paths、无 forbidden/docs/plans/ 触碰？`redispatch.py`/`config.toml` 本轮未改是否与 §R 一致？
- **Q6（新引入风险）**：rework 是否引入**任何新的 blocker/major**？特别核：(a) `except Exception` 是否**过宽**到吞掉本应暴露的真实编程错误（而非仅配置形状错误）？(b) 两处脱敏诊断是否可能泄漏敏感信息？(c) `test_load_patterns_emits_redacted_diagnostic_on_fault` 末行 `"api_key" not in err.lower() or "api_key_env" not in err` 是弱 **OR**（编排者判为非阻断 nit）——你是否同意非阻断，还是须收紧为 AND？
- **Q7（#2/#3/#6 裁定）**：你是否接受编排者对 #2（设计意图非缺陷）、#3（流程/布局非代码，C2 gate 从干净源跑）、#6（残余风险，生产前 probe）的裁定？

## 7. OUTPUT CONTRACT（你的最终消息必须是且仅是一个 JSON 对象，无前后缀散文）
```json
{"decision":"ACCEPT|REWORK|CONSULT","rationale":"<引用你实际核验的证据：具体 文件:行 / diff hunk / 不变式编号 / finding 编号>","findings":[{"severity":"blocker|major|minor|note","title":"...","detail":"...","evidence":"file:line 或 diff hunk 引用"}]}
```
- `decision` 严格三选一；严重度序 **REWORK > CONSULT > ACCEPT**（任一 blocker/major 未闭环 → 不得 ACCEPT）。
- **禁止伪签**（本仓 WP-21 已立此判据）：rationale/findings 若照抄本 prompt、零审查证据 → 视为无效签名。你必须体现对 §8/§9 diff 的独立核验（引用具体行/hunk），并**逐条核对 §3 的 8 findings 是否真闭环**。
- 逐条覆盖 Q1–Q7。若 #1 的 NARROW 范围决策对 merge gate 可接受且其余 findings 闭环、零回归成立 → 给 ACCEPT（这是凑齐双签的第二签名）；若发现任何未闭环的 blocker/major → REWORK 并指明。

## §8 REWORK DELTA DIFF（base 42e6d85 → HEAD 4035f06，5 文件 +99/−5，紧随其后）
