# WP-01: kimi 额度不足自动回退 deepseek-flash（单跳，配置驱动）

> 冻结日期 2026-09-22 | **rev 7**（re-freeze，回应 codex **rev6 brief 复签 consult REWORK** 的 F1/F2/F3：F1 §R1 不变式收窄对齐实现 / F2 删 §R2a 尾窗（采 codex off-ramp）/ F3 §R4 计数重算；用户已批准本次 re-freeze 与 F1 取 NARROW）| 编排者 claude-code (orchestrator, session=kqff-b) | 执行者 kimi (developer)。
> 所属 Plan：PLAN-01（集成到 `plan/2026-09-22-kimi-quota-flash-fallback`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（规则见「Re-freeze 规则」一节）。
>
> **rev7 修订摘要（对应 codex rev6 brief 复签 consult REWORK 的 F1/F2/F3；用户已批准本次 re-freeze + F1 取 NARROW）**：
> - **F1（§R1 不变式收窄，成立）** codex 指出 §R1「任意配置形状含畸形 TOML 绝不抛」强于实现/测试（只覆盖 `build_binding` 的 selectors 形状）。编排者核实：畸形 TOML 确在 `get_roles_raw`（`resolve_paths.py:401`，try 外）逃逸，**但 primary `resolve_role_binding`（`:361`）同样在 try 外调 `get_roles_raw`** → 畸形 TOML 是两条路径**共享的既有失败模式、非本 WP 新增崩溃面**（本 WP 新增的只是 `selectors` 非 dict → `build_binding` `AttributeError`，因 primary 对 developer 无 provider 键时 `:374` 提前返回、永不调 `build_binding`）。**用户定夺取 NARROW**：§R1 不变式与 docstring 收窄为「对 **provider 配置形状**（本 WP 经 `build_binding` 新增的崩溃面）绝不抛」；畸形 config 文件（TOML）显式标注为与 primary 共享的既有失败、本 WP 范围外（如需硬化应另立跨两个 resolver 的 WP，避免单边不对称）。实现仅把 `build_binding` 捕获拓宽为 `except Exception`（窄作用域 + 脱敏诊断）；测试 selectors string/list，**不加**畸形 TOML 用例。理由：契合 Q1 范围、避免 primary/fallback 不对称、BROADEN 对派发链实际无效（primary 必先崩，给出「派发链已防畸形 TOML」假信号）。
> - **F2（删 §R2a 尾窗，成立，采 codex off-ramp）** 编排者核实 codex ReDoS probe：31 字符串即在 0.25s 内超时（`(a+)+$` 型灾难回溯远小于 64KB 即发生）→ 尾窗只界**长度**不界**时间**，未闭合 ReDoS；且把「额度串仅在头部 + 尾随日志 >64KB」的既有 True 改成 False = **引入检测回归**。config.toml patterns 本为 **operator-trusted**（能写 config 者可为更恶之事），威胁模型不成立。**rev7 删除整个 §R2a**（`_MAX_SCAN_CHARS` + 2 尾窗测试 + 「闭合 ReDoS」表述），保留全文 `re.search`，模块 docstring 标注 custom patterns 为 operator-trusted、禁不可信注入（信任边界 + 文档，而非行为变更）。#8 硬化仅剩 §R2b 脱敏诊断。此举**恢复零回归**（codex 第 6 点）。
> - **F3（§R4 计数重算，成立）** rev6 §R4 写 `test_quota_fallback.py 11→13（+§R2a 2）` 漏算 §R2b 的 +1（`test_load_patterns_emits_redacted_diagnostic_on_fault`）→ 按 rev6 原文应 14、合计 32（DoD 同错）。rev7 删 §R2a（−2）后按最终测试集重算：`test_quota_fallback.py 11→12`（+§R2b 1）、`test_resolve_fallback_binding.py 5→7`（+§R1 2）、`test_redispatch_quota_fallback.py 10→11`（+§R3 1），合计新增 **26→30**。
> - **codex 判成立、rev7 原样保留**：§R2b（脱敏诊断）、§R3（#4/#5 台账勘误 + success 腿独立承重，codex 实证新测试确实使 success 腿承重）、零回归边界（codex 确认 #2 已消解、INV-4/单跳/计数/forbidden 未改；删 §R2a 后零回归恢复）。**注**：§R3 的 #4/#5 勘误自 rev6 引入、rev7 不改，故下文「rev6 §R3」「rev6 勘误 #4/#5」标签为历史沿革，内容不变。
>
> **rev6 修订摘要（对应 codex 实现后双签 consult REWORK 的 8 findings；用户已批准本次 re-freeze，满足「第 3 次及以后 re-freeze 须用户批准」规则）**：
> - **#1（major，真缺陷，实现阻断）** `resolve_role_fallback_binding` 的 fail-safe 只 `except ProviderConfigError`，未覆盖 `build_binding` 在 `selectors` 为非 dict（如误配成字符串）时抛的 `AttributeError`，违反 docstring「NEVER raises into the dispatch path」与交付物清单「provider 段缺失或非法 → 返回 `None`，绝不抛到派发主链」+ INV-3。编排者独立 probe 坐实：`selectors="deepseek/v4-flash"`（字符串）→ fallback 抛 `AttributeError`，而同配置 primary `resolve_role_binding` 仍返回 `("kimi", None)` 不受影响 → 本 WP **新增崩溃面**。修：拓宽 fail-safe 至任意异常/形状 → None，并补形状负例测试。见「Rework rev7 闭环 spec」§R1（rev7 F1 已收窄至 provider 配置形状）、映射表 INV-3。
> - **#8（minor，非阻断，用户批准一并硬化）** (a) config 可注入任意正则，`is_quota_error` 对全文 `re.search` 有配置级 ReDoS 面 → 限界被扫描输出（尾窗，**rev7 F2 已删除此项**——尾窗不界时间且引入检测回归，见 §R2a）；(b) `load_quota_patterns` 的 `except Exception: pass` 静默吞配置故障、缺诊断 → 补**脱敏**一行诊断（仅异常类名，绝不含 config 内容/密钥）。见 §R2。
> - **#4/#5（minor，文档级 oracle 台账勘误）** 承重映射表两处台账与实测不符：(#4) INV-1「删正向 pattern（如 `\bquota\b`）→ 红」**不成立**——`quota exceeded` 亦被语境正则 `(balance|credit|…|quota|…)\W{0,20}(insufficient|exceeded|…)` 命中，删 `\bquota\b` 仍绿（冗余）；真正承重的裸词是 `额度`（删之 `test_matches_chinese_quota_terms` 转红）。(#5) INV-5「删短路 → `test_success_no_fallback` 转红」**不成立**——success 腿输出 `"done"` 非额度串，删短路仍绿（等价 witness）；仅 dry_run 腿承重。修：更正台账 + 新增 `test_success_with_quota_like_output_no_fallback`（成功但输出含额度词）使 success 腿独立承重。见 §R3、映射表 INV-1/INV-5。
> - **#2（不成立，非本 brief 缺陷）** codex 判「缺省 fallback provider 未回落内置默认」为 major，实为编排者 consult prompt 措辞错误：本 brief 交付物清单 + DESIGN 明写**只有 quota patterns 有内置默认（DEFAULT_QUOTA_PATTERNS），fallback provider 没有**，未配 = 额度失败即 STOP = 零回归（设计意图）。实现正确，rev6 不改此项，仅更正 consult prompt。
> - **#3（流程/布局，非代码）** quality-gate 的 changed set 含工作树 dirty/untracked，编排者回填的 status/制品触发「outside allowed scope」；7 个代码文件本身全绿。C2 前从干净状态源跑 gate 记真实绿证据（方案1 等价变通），非 kimi rework 范围。
> - **#6（残余风险）** flash 精确 model id/selector 禁网不可实测；保留附注「生产启用前须非生产凭据 probe」为 C4/生产前显式前置。
> - **#7（确认零回归）** codex 确认主 binding `(kimi,None)`、kirogpt 无增删、单跳不写 status/锁/count、日志脱敏 → 与 C1 复核一致，rev6 不动。
>
> **rev5 修订摘要（对应 codex rev4 CODEX_FINDINGS，1 项纯文档计数校正）**：
> - **#3（rev4 判部分闭环项）** codex rev4 确认 finding #1（畸形 TOML 测试，实证 `tomllib.loads` 抛 `TOMLDecodeError`）与 #2（INV-2 三拆绑 (a1)/(a2)/(b) 各绑专属 witness）**完全闭环**，唯测试计数与实际 `def test_` 数不符。已据 codex 精确 grep（B1=7、B2 追加=4→`test_quota_fallback.py` 合计 11、B3=5、B4/B5=10、全量新增=26；编排者独立 grep 复核一致）校正：DoD「新增 ~21」→「新增 26」；IMPLEMENTATION-PLAN B1 Step 4「8 passed」→「7 passed」、B2 Step 4「12 passed」→「11 passed」、B6 Step 1「~21」→「26」。纯文档计数，未动源码/架构/adapter/gate。
>
> **rev4 修订摘要（对应 codex rev3 CODEX_FINDINGS，1 项 brief 级 oracle 缺口，历史）**：
> - **#1** INV-2(a) 的「删 `load_quota_patterns` 的 `except Exception`」承重变异不可执行——现有 `test_load_patterns_fails_safe_on_bad_override` 只测空列表/错误类型（合法 TOML，走 isinstance fall-through，不触发 `except Exception`）。已新增 `test_load_patterns_fails_safe_on_malformed_toml`（畸形 TOML → `tomllib.load` 抛 `TOMLDecodeError` → `except Exception` 回落 DEFAULT），删 `except Exception` 则该用例转红；INV-2(a) 拆绑为 (a1) 删 `except Exception` → 畸形 TOML 用例红、(a2) 删 isinstance/非空守卫 → 空列表/错误类型用例红。见映射表 INV-2、B2 Step 1、Acceptance tests §3、C1 mutation-probe。
>
> **rev3 修订摘要（逐项对应 codex rev2 CODEX_FINDINGS，2 项 brief 级 oracle 缺口，历史）**：
> - **#3** INV-2 承重变异原指向不存在的 `load_quota_patterns` 坏正则 `try/except`（B2 只读 config、不编译正则）；已拆分 fail-safe 双层——config 回落默认由 `load_quota_patterns` 的 `try/except Exception`+isinstance 守卫承重，坏正则跳过由 `is_quota_error` 的 `except re.error: continue` 承重；B1 Step 1 新增 `test_bad_regex_pattern_is_skipped_not_raised`（`patterns=["[", r"\bquota\b"]`），承重变异改为删 `is_quota_error` 的 `except re.error`。见映射表 INV-2、Acceptance tests §3、C1 mutation-probe。
> - **#4** 范围守卫原只 `comm -23` 观察输出（comm 越界仍退出 0，空/无效基线时 sort 可能假绿）；已改机器化 fail-closed——`set -euo pipefail` + 断言 `dispatch_commit` 非空且 `git cat-file -e` 有效 + `git diff` 失败即终止 + `comm -23` 写 unexpected 文件后 `[ -s ]` 非空即 `exit 1` + forbidden diff 非空即 `exit 1`，全绿打印 `SCOPE_GUARD_PASS`。见 DoD 与「Allowed and forbidden paths」。
>
> **rev2 修订摘要（逐项对应 codex rev1 CODEX_FINDINGS，历史）**：
> - **#1** 额度模式收窄为语境化正则 + 新增歧义边界不变式（`test count exceeded`/`insufficient permissions`/`billing module failed`/非账户 `credit` 均判 False，且 wrapper 不构造 fallback）。见「交付物清单」「附注」「Acceptance tests §3」与映射表 INV-1。
> - **#2** 新增 `main()` 接线级承重测试：回退成功只 +1（INV-W1）、circuit-breaker 先于派发（INV-W2），各绑定必须转红的 source mutation（M1/M2）。见映射表 INV-5。
> - **#3** 删除无效空串变异，改为过宽判定/IGNORECASE 等真实承重变异；补五项不变式→测试→变异映射表。见「Acceptance tests」。
> - **#4** 范围守卫改用 `status.git.dispatch_commit` 基线 + changed⊆allowed 集合差（不再用 `main...HEAD`）；"6 个允许文件"订正为 7。见 DoD 与「Allowed and forbidden paths」。

## Re-freeze 规则（编排者冻结前自检）

- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。
- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。

## Rework rev7 闭环 spec（权威 delta；kimi 在既有 5 提交之上续做，不重启、不重编既有 fixture/status）

> 本节是 rev7 相对已交付 HEAD `42e6d85` 的**唯一新增/修改要求**。kimi 先 `git status`/`git diff --stat` 核既有改动，在其上续做；既有 B1-B5 提交与通过的用例保持不变，只按本节增补。改动仍限 allowed_paths 内（源码 2：`resolve_paths.py`/`quota_fallback.py`；测试 3：`test_resolve_fallback_binding.py`/`test_quota_fallback.py`/`test_redispatch_quota_fallback.py`）；`redispatch.py`/`config.toml` 本轮无需改。

### §R1 — finding #1：拓宽 fallback fail-safe（实现阻断，必修）

- **不变式（INV-3 强化，rev7 F1 收窄）**：`resolve_role_fallback_binding(role, repo)` 对**任意 provider 配置形状**都**绝不抛异常**，一律回落 `None`——包括：`selectors` 为非 dict（字符串/列表/整数）、provider 段缺必需字段、provider 段本身为非 dict、`build_binding` 内任意异常。**范围界定（rev7 F1）**：本不变式只覆盖 **provider 配置形状**（本 WP 经 `build_binding` 新增的崩溃面）；**config 文件畸形 TOML 不在范围内**——它在 `get_roles_raw`（`resolve_paths.py:401`，位于 try 之外）逃逸，且 primary `resolve_role_binding`（`:361`）同样未捕获，是两条路径**共享的既有失败模式**、非本 WP 新增（如需硬化应另立跨两个 resolver 的 WP，避免单边不对称）。docstring「NEVER raises into the dispatch path」rev7 同步**收窄措辞**为「never raises for provider-config shape errors; a malformed config FILE is a pre-existing failure shared with resolve_role_binding, out of scope」，kimi 据此更新 docstring。
- **实现要求（rev7 F1 收窄）**：把 `build_binding(...)` 调用点的 `except ProviderConfigError` 拓宽为 `except Exception` → `None`（**窄作用域**：仅包 `build_binding` 调用，**不**上扩到 `get_roles_raw`——畸形 TOML 属范围外既有失败，见上）。捕获 `Exception` 而非 `BaseException`；回落 `None` 前打印**一行脱敏诊断**（仅固定文案 + `type(exc).__name__`，绝不含 config 原文/路径/密钥，与 §R2b 同口径）。必须覆盖 `selectors` 非 dict 触发 `build_binding` 内 `AttributeError` 的路径（现 `except ProviderConfigError` 漏它）。**不得**削弱 primary `resolve_role_binding` 行为（INV-4 主档零回归不变），**不得**改 `get_roles_raw`/`_load_config`（畸形 TOML 行为保持与 primary 一致）。
- **新增承重测试**（`tests/test_resolve_fallback_binding.py`）：
  - `test_none_when_selectors_is_string_no_raise`：provider 段 `selectors = "deepseek/v4-flash"`（字符串，非 table）+ role 带 `fallback_provider` → 返回 `None`，不抛。（finding #1 精确 repro）
  - `test_none_when_selectors_is_list_no_raise`：`selectors = ["kimi"]`（列表）→ `None`，不抛。
- **承重变异（更新 INV-3）**：把拓宽后的 `except Exception` 删掉/收窄回 `except ProviderConfigError` → 上述两个形状负例转红（`AttributeError` 逸出）。既有 `test_none_when_provider_cfg_invalid_no_raise`（缺 anthropic_base_url → ProviderConfigError）仍须绿。**rev7 不加畸形 TOML 用例**（范围外，见不变式界定）。

### §R2 — finding #8：脱敏诊断（非阻断，用户批准一并硬化；rev7 F2 删尾窗）

- **§R2a（rev7 F2 已删除，勿实现）** rev6 曾要求 `is_quota_error` 尾窗限界（`_MAX_SCAN_CHARS=65536`）防配置级 ReDoS。codex F2 实证此法**只界长度不界时间**（灾难回溯在 31 字符串即超时）、且**引入检测回归**（头部额度串 + >64KB 尾随日志 → 漏检）。config patterns 本为 operator-trusted，威胁模型不成立。**rev7 删除 §R2a 全部要求**：不加 `_MAX_SCAN_CHARS`、不加尾窗测试、不改 `is_quota_error` 扫描行为（保留全文 `re.search`）。**文档要求**：在 `quota_fallback.py` 模块 docstring 注明「custom patterns 来自项目 config，视为 operator-trusted；不得注入不可信正则」（以信任边界 + 文档替代尾窗行为变更）。
- **§R2b `load_quota_patterns` 脱敏诊断（保留）**：现 `except Exception: pass` 静默吞配置故障。要求：回落 DEFAULT 前向 `stderr` 打印**一行脱敏诊断**，仅含固定文案 + 异常**类名**（`type(exc).__name__`），**绝不含** config 原文、路径或任何 `api_key`/密钥值。
  - 新增测试 `test_load_patterns_emits_redacted_diagnostic_on_fault`（capsys）：畸形 TOML（内含哨兵串 `SECRET_SENTINEL_DO_NOT_LEAK`）→ 回落 DEFAULT + stderr 出现诊断行；断言哨兵串**不在** stderr（脱敏）。既有 `test_load_patterns_fails_safe_on_malformed_toml` 仍须绿。（codex 建议加固，非阻断：可再断言 stderr 恰一行 + 含固定前缀 + 不含 config 路径/`api_key`。）

### §R3 — findings #4/#5：承重映射表 oracle 台账勘误 + success 腿独立承重

- **#4 台账更正（INV-1）**：映射表与 §3 中「删某正向 pattern（如 `\bquota\b`）→ 对应正向红」为**错误台账**。实测：`quota exceeded` 亦被语境正则 `(balance|credit|…|quota|…)\W{0,20}(insufficient|exceeded|…)` 命中，删裸词 `\bquota\b` 后 `test_matches_english_quota_terms` **仍绿**（`\bquota\b` 冗余）。正确承重裸词是 `额度`：删 `额度` → `test_matches_chinese_quota_terms`（`"错误：账户额度不足"`）转红。台账示例统一改用 `额度`，并注明 `\bquota\b` 冗余（受语境正则覆盖）。
- **#5 台账更正（INV-5）+ 新增承重测试**：映射表与 §3 中「删短路 `if dry_run or result.dispatched: return` → `test_success_no_fallback` 转红」为**错误台账**。实测：`test_success_no_fallback` 的 success 输出 `"done"` 非额度串，删短路后 `is_quota_error("done")` 仍 False → 不回退 → **仍绿**（等价 witness）；仅 `test_dry_run_does_not_fallback_even_on_quota_output`（dry_run 腿）承重转红。修：
  - 新增 `test_success_with_quota_like_output_no_fallback`（`tests/test_redispatch_quota_fallback.py`）：primary `dispatched=True` 但 `output` 含额度词（如 `"build ok; note: weekly quota reset scheduled"`）→ 短路守卫必须优先于 `is_quota_error`，`built==[]`、`prov is None`。**删短路 → 本用例转红**（`is_quota_error` 命中额度词会误构造回退），使 success 腿独立承重。
  - 台账「删短路」转红 witness 更正为：`test_dry_run_does_not_fallback_even_on_quota_output`（dry_run 腿）**+** `test_success_with_quota_like_output_no_fallback`（success 腿，rev6 新增）；`test_success_no_fallback` 标注为等价 witness（非承重）。

### §R4 — DoD 测试计数 + 提交（rev7）

- focused 三文件用例数（rev7 F3 重算）：`test_quota_fallback.py` 11 → **12**（+§R2b 1；§R2a 已删不计）；`test_resolve_fallback_binding.py` 5 → **7**（+§R1 2）；`test_redispatch_quota_fallback.py` 10 → **11**（+§R3 1）。合计新增 26 → **30**。
- 全量 `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests -q` 仍只允许 4 个**预存** `test_finalize_merge_triple_sign.py` 失败；任何新增失败视为回归必修。
- 提交：本轮 rework 在既有 5 提交之上新增**一次** feat 提交（显式路径，仅 5 个改动文件：2 源 + 3 测试）；status 工作树累积仍不单独提交（§4.3 只在 finalize 提交）。commit message：`rework(r1): close codex impl-rev1 REWORK #1/#8 + brief #4/#5 erratum`。

## 目标（一句话）

让 `agentic redispatch` 派发 developer 时，若原生 kimi 派发失败且输出命中额度模式，自动用配置的 `fallback_provider` 重派一次（单跳），失败即 STOP；对现有裸 kimi 配置零回归，主档 binding 与独立性评级语义完全不变。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/quota_fallback.py` — Create：纯函数额度检测 + 模式加载
  - `src/agentic_loop/resolve_paths.py` — Modify：新增 `resolve_role_fallback_binding`
  - `src/agentic_loop/redispatch.py` — Modify：新增 `_dispatch_with_quota_fallback` + `main()` 接入
  - `.agentic/config.toml` — Modify：追加 `[providers.deepseekflash]` + `[roles] developer` 加 `fallback_provider`
  - `tests/test_quota_fallback.py` — Create：`is_quota_error` / `load_quota_patterns` 单测
  - `tests/test_resolve_fallback_binding.py` — Create：`resolve_role_fallback_binding` 单测（含零回归负例）
  - `tests/test_redispatch_quota_fallback.py` — Create：派发回退编排单测（stub adapter，无真实 kimi/网络）

- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/independence.py` — 独立性评级不受本 WP 影响
  - `src/agentic_loop/gate/` — 双签门禁不属本 WP 范围
  - `src/agentic_loop/adapters/kimi.py` — 既有 `_temp_config` 注入机制已够用，不改 adapter
  - `uv.lock` — 无依赖变更
  - `docs/agentic/OPERATING_MODEL.md` — 章程不改
  - `AGENTS.md`
  - `CLAUDE.md`
  - `src/agentic_loop/templates/` — 模板不改（DESIGN §11 明确范围外）
  - `.agentic/locks/`
  - `.env`
  - `.context/`

- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入；本 WP 无跨 owner 文件。

## 输入

- 依赖的上游 WP 产出：无（本 plan 单 WP，base 直接是 `main` 7c318f4）。
- 参考文档（**权威源**，按文件读，不凭记忆替代）：
  - `docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md` §4-§8（架构、组件、数据流、错误处理与安全边界、config、测试计划）
  - `docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md` Phase B（B1-B6，含每步完整代码、命令、预期输出）
  - `docs/plans/2026-09-22-kimi-quota-flash-fallback/HANDOFF.md`（环境/纪律提醒）

## 交付物清单

- [ ] `src/agentic_loop/quota_fallback.py`（B1+B2）— 纯函数 `is_quota_error(output, patterns=None)` + `load_quota_patterns(repo=None)`；`DEFAULT_QUOTA_PATTERNS` 覆盖中英常见额度措辞与 HTTP 429/402；坏正则跳过而非崩溃；无 I/O 副作用（除 `load_quota_patterns` 读 config + rev7 §R2b 回落时的**脱敏** stderr 诊断）；rev7 F2：`is_quota_error` **保留全文扫描**（删尾窗），模块 docstring 注明 custom patterns 为 operator-trusted、禁不可信注入。
- [ ] `src/agentic_loop/resolve_paths.py`（B3）— 新增 `resolve_role_fallback_binding(role, repo=None)`：读 `roles.<role>` 字典的**可选** `fallback_provider` 键 → 复用 `build_binding`；键缺失/role 非 dict/provider 段缺失或非法 → 返回 `None`（零回归，绝不抛到派发主链）；**rev7 §R1（F1 收窄）：把 `build_binding` 捕获拓宽为 `except Exception`（窄作用域）→ 覆盖 provider 配置形状非法（含 `selectors` 非 dict）→ None + 脱敏诊断；畸形 config 文件（TOML）属范围外既有共享失败，不动 `get_roles_raw`/`_load_config`；docstring 同步收窄**。
- [ ] `src/agentic_loop/redispatch.py`（B4+B5）— 新增 `_dispatch_with_quota_fallback(adapter, worktree, brief, prompt, dry_run, *, fallback_binding=None, fallback_factory=None, quota_patterns=None) -> tuple[ImplementResult, str | None]`；`main()` 派发点改调本函数；成功/dry_run/非额度失败/未配回退 → 不触发回退；额度失败且配了回退 → 构造 flash `KimiAdapter` 重派一次；flash 也额度失败 → 单跳到底 STOP。
- [ ] `.agentic/config.toml`（B5）— `[providers.deepseekflash]`（anthropic_base_url / api_key_env / identity_model + selectors.kimi）；`[roles] developer` 由裸 string 改 `{ adapter = "kimi", fallback_provider = "deepseekflash" }`。
- [ ] `tests/test_quota_fallback.py`（B1+B2）— 中/英/数字码各取样正向命中；负向：普通报错/成功输出/空串，**以及歧义负例**（`test count exceeded`/`insufficient permissions`/`billing module failed`/`credit card processor returned error`/`port 429 is not available`/`out of memory` 等非账户语境均判 False，codex rev1 #1）；`load_quota_patterns` config 覆盖生效 + 缺省/坏配置回落默认（fail-safe，含**畸形 TOML** 回落 `test_load_patterns_fails_safe_on_malformed_toml`，codex rev3 #1）；**坏正则由 `is_quota_error` 的 `except re.error` 跳过不抛**（`test_bad_regex_pattern_is_skipped_not_raised`，codex rev2 #3——承重变异点是 is_quota_error 而非 load_quota_patterns）。**rev7 §R2b 新增**：`test_load_patterns_emits_redacted_diagnostic_on_fault`（脱敏诊断）。**rev7 F2 删除**：rev6 的 2 个尾窗测试（`test_is_quota_error_detects_quota_at_tail_of_oversized_output` / `test_is_quota_error_scan_is_bounded_to_tail_window`）不加。
- [ ] `tests/test_resolve_fallback_binding.py`（B3）— 正向 flash binding 解析；负向：role 非 dict / 无 fallback_provider / provider 段缺失 / provider 配置非法（均返回 None，不抛异常）；**rev6 §R1 新增形状负例**：`test_none_when_selectors_is_string_no_raise` / `test_none_when_selectors_is_list_no_raise`（selectors 非 dict → None 不抛）。
- [ ] `tests/test_redispatch_quota_fallback.py`（B4+B5）— 成功不回退；非额度失败不回退；额度失败重派 flash 成功；额度失败未配回退即 STOP；单跳 flash 也额度失败即 STOP；dry_run 直通；主档 `resolve_role_binding("developer")` 仍返回 `("kimi", None)`（评级语义零回归）；项目 config 解析出 flash fallback；**main() 接线级**（codex rev1 #2）：回退成功后 `redispatch_count` 恰 +1（INV-W1）、`count>=REDISPATCH_MAX` 时 circuit-breaker 先于派发使 primary/fallback 都不调且 flash 不构造（INV-W2）。**rev6 §R3 新增**：`test_success_with_quota_like_output_no_fallback`（成功但输出含额度词 → 短路优先，不回退；删短路则转红，使 success 腿独立承重）。

## 完成定义（DoD）

- [ ] 交付物逐项就绪（7 个文件，与 allowed_paths 一一对应）
- [ ] `agentic quality-gate docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json` 全绿
- [ ] 全量测试 `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests -q` 仅 4 个**预存** `test_finalize_merge_triple_sign.py` 失败（基线，main 被 sibling worktree 占用所致），其余全绿，新增 30 个用例通过（rev7 §R4：test_quota_fallback.py 12 + test_resolve_fallback_binding.py 7 + test_redispatch_quota_fallback.py 11 = 30）；任何**新增**失败视为回归，必须修复
- [ ] 范围守卫（B6 Step 2，codex rev1 #4 + rev2 #4 fail-closed）：`set -euo pipefail` 下以 `status.git.dispatch_commit` 为基线（**断言非空且 `git cat-file -e` 有效**，`git diff` 失败即终止），`git diff --name-only <dispatch_commit>...HEAD` 的 changed-path 集合与 7 项 allowed_paths 的集合差**写入 unexpected 文件后 `[ -s ]` 非空即 `exit 1`**（机器化 fail-closed，changed ⊆ allowed，捕获任何越界）；显式 forbidden 路径（independence/gate/kimi.py/uv.lock/OPERATING_MODEL/AGENTS/CLAUDE）diff 非空即 `exit 1`；全绿打印 `SCOPE_GUARD_PASS`（退出 0）。**不用 `main...HEAD`**（含 A 阶段治理提交）
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] commit message 符合规范（B1-B5 各一次 feat 提交，显式路径；status 的工作树累积不单独提交，按章程 §4.3 只在 freeze/finalize 提交）

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

> 若需偏离默认（如生产写入），须编排者 + 独立顾问双重审核并在此记录授权原因。
> 本 WP 单测全部用 stub adapter / tmp_path fixture 覆盖，**绝不**调真实 kimi CLI 或 DeepSeek API。
> 派发本 WP 时若 kimi 原生套餐已耗尽，按 DESIGN §10.1 用 `deepseek-v4-flash` 的手动 `--config-file` 派发（用户已授权 flash 优先），此时不依赖本 WP 自身的回退能力。

## 附注

- **已知陷阱**：
  - 运行测试**必须** `env -u AGENTIC_PYTHON`，否则 AGENTIC_PYTHON 泄漏进 `test_gate_runner_shell` 子进程绕过 python3 stub → 假失败（HANDOFF 环境提醒）。
  - `python3.11` 是 /opt/homebrew 版本，**无 agentic_loop 包**；模块校验/测试都要 `PYTHONPATH=src`（`docs/KNOWN-ISSUE-bare-python3.md`）。
  - `developer` 由裸 string 改 dict 后，`resolve_role_binding("developer")` 仍须返回 `("kimi", None)`（无 `provider` 键 → 主档零注入），**否则评级语义会变**——本 WP 显式断言此不变式。
  - `_dispatch_with_quota_fallback` 内的 `fallback_factory` 默认构造 `KimiAdapter(kimi_bin=os.environ.get("KIMI_BIN", "kimi"), binding=b)`；测试须用 stub factory 注入，避免真实 kimi 调用。
  - **不要**为回退额外增加 `redispatch_count`：计数语义由 `main()` 在最终成功后 +1；回退是「换 provider 重派」而非 rework（DESIGN §5 步骤 7）。
  - **额度模式必须语境化（codex rev1 #1）**：`DEFAULT_QUOTA_PATTERNS` 不得含裸词 `insufficient`/`balance`/`credit`/`exceeded`/`billing`/`rate.?limit`；ambiguous 词须与账户/额度名词近距共现，`429`/`402` 须与额度/付费语境共现（避免命中端口号/行数）。`test_ambiguous_phrases_are_not_quota_errors` 是「过宽判定」方向的承重锁。
  - **计数/circuit-breaker 接线必须有承重测试（codex rev1 #2）**：`main()` 仅在最终成功后 `count + 1`（回退成功也只 +1，INV-W1）；circuit-breaker（`count >= REDISPATCH_MAX`）必须先于任何派发/构造（INV-W2）。B5 Step 3 的 2 条 wiring 测试用 monkeypatch 离线承重，绑定 mutation M1（`count+2`）/M2（wrapper 调用前移），C1 mutation-probe 复核。
  - flash `identity_model` / `selectors.kimi` 精确串实现前须核实（DESIGN §10.1）；如与 `deepseek-v4-flash` / `deepseek/v4-flash` 有出入，按实测更新 `.agentic/config.toml` 并同步更新 `tests/test_redispatch_quota_fallback.py::test_project_config_resolves_flash_fallback` 的断言字面值。
- **口径权威源引用**：
  - `src/agentic_loop/redispatch.py:_dispatch` — 全框架唯一派发入口（DESIGN §3 已核实）
  - `src/agentic_loop/adapters/kimi.py:_temp_config` — 既有 flash 注入机制，**不改**（DESIGN §3）
  - `src/agentic_loop/resolve_paths.py:resolve_role_binding` — 对称参考点（DESIGN §4.2）
  - `.agentic/config.toml [roles] developer` — 主档语义零回归的判据源

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」中的验收测试要求同义，非另一份口径。

每一份 WP 的每条负面断言都必须提供 oracle 校验四项证据：

1. **正向可达性对照**：在同一 fixture 上做一次不带注入/变异的正向运行，必须到达终点，证明前置条件确实可达终点。
   - 本 WP 具体化：`is_quota_error("quota exceeded")` → True 的同时，`is_quota_error("ModuleNotFoundError")` → False；`_dispatch_with_quota_fallback` 在 primary 成功路径**不**构造回退 adapter（`built == []` 且 `prov is None`），在 primary 额度失败路径**恰好**重派一次（`fb.calls == 1`）。

2. **原因特异 witness**：负向运行必须给出原因特异的 witness（异常标记、状态或精确事件），证明失败被正确归因。
   - 本 WP 具体化：非额度失败**不**触发回退（`res.dispatched is False`、`prov is None`、`built == []`）；未配 fallback 时**原样返回**失败（`res.dispatched is False`、`prov is None`，日志 `quota detected but no fallback_provider configured`）；单跳 flash 也额度失败时**不再三跳**（`fb.calls == 1`、日志 `single-hop exhausted -> STOP`）；`dry_run` 直通不回退（`prov is None`、`built == []`）。

3. **代表性禁止变异转红**：至少一个代表性禁止变异（如改掉锚点标题、删去关键守卫）必须使测试转红。变异须同时覆盖**漏报**与**过宽误报**两个方向（codex rev1 #3）。
   - 本 WP 具体化（每条均「还原 → 转红」双向验证）：
     - **漏报方向**：把 `is_quota_error` 的额度判定改成恒 False → `test_quota_failure_retries_with_flash_success` 转红；删掉某个**承重**正向 pattern（如 `额度`）→ `test_matches_chinese_quota_terms` 转红（**rev6 勘误 #4**：原例 `\bquota\b` 冗余——`quota exceeded` 亦被语境正则命中，删之仍绿）；删掉 `re.IGNORECASE` → `test_case_insensitive`（`QUOTA EXCEEDED`/`Insufficient Balance`）转红。
     - **过宽误报方向（codex rev1 #1/#3）**：把语境化正则放宽回裸词（如把 `(insufficient|exceeded|...)\W{0,10}(balance|credit|...)` 改成裸 `insufficient`）→ `test_ambiguous_phrases_are_not_quota_errors` 转红（`insufficient permissions` 等被误判为额度错误）。
     - **守卫删除**：把 `resolve_role_fallback_binding` 拓宽后的 `except Exception`（rev7 §R1 F1 收窄仅包 build_binding，原为 `except ProviderConfigError`）删掉或收窄回 `ProviderConfigError` → `test_none_when_provider_cfg_invalid_no_raise` + `test_none_when_selectors_is_string_no_raise` + `test_none_when_selectors_is_list_no_raise` 转红（异常/`AttributeError` 逸出）；把 `_dispatch_with_quota_fallback` 内的 `if dry_run or result.dispatched: return result, None` 短路删掉 → `test_dry_run_does_not_fallback_even_on_quota_output`（dry_run 腿）+ `test_success_with_quota_like_output_no_fallback`（success 腿，rev6 §R3 新增）转红（**rev6 勘误 #5**：`test_success_no_fallback` 输出 `"done"` 非额度串，删短路仍绿，属等价 witness 非承重）；把单跳守卫改成循环重试 → `test_single_hop_flash_also_quota_fails` 转红（`fb.calls > 1`）；把 `is_quota_error` 的 `except re.error: continue` 删掉 → `test_bad_regex_pattern_is_skipped_not_raised` 转红（坏正则抛 `re.error` 而非跳过，codex rev2 #3——此守卫在 is_quota_error，非 load_quota_patterns）；把 `load_quota_patterns` 的 `except Exception` 删掉 → `test_load_patterns_fails_safe_on_malformed_toml` 转红（畸形 TOML 的 `TOMLDecodeError` 抛出而非回落默认，codex rev3 #1）。
     - **main() 接线（codex rev1 #2）**：把 `new_count = count + 1` 改成 `count + 2`（M1）→ `test_wiring_fallback_success_increments_count_by_one` 转红；把 `_dispatch_with_quota_fallback` 调用移到 circuit-breaker（`count >= redispatch_max` return）之前（M2）→ `test_wiring_circuit_breaker_precedes_dispatch` 转红。
   - **不可攻击步骤声明（§4 要求）**：`is_quota_error` 开头的 `if not output: return False` 是纯短路优化——删去它后空串仍走到正则循环，而所有语境化正则在空串上本就不匹配，函数仍返回 False，行为等价。故该守卫**不构成承重变异**；rev1 中"删它必转红"的例子无效，已删除（codex rev1 #3）。空串判 False 的承重改由"过宽 pattern（如误加 `r".*"` 使空串也命中）会让 `is_quota_error("")` 转 True"这一变异方向覆盖。

4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。变异必须施加于判据真实的输入面（文件字节 / 进程边界 / 外部状态），不得只改判据已持有的内存表示。判别方式：把被修的缺陷还原成原状，该用例必须转红；仍绿则该用例不承重。同类输入面的等价载体（如临时副本）满足本项；若变异会写到被判据保护的制品本身，须优先选用不写该制品的等价载体。
   - 本 WP 具体化：变异施于 `src/agentic_loop/quota_fallback.py` / `resolve_paths.py` / `redispatch.py` 源文件字节（不是内存对象）；每条断言都由「还原 → 转红」双向验证；config-driven 判据（`load_quota_patterns` / `resolve_role_fallback_binding`）的变异施于 `tmp_path` 下的 `.agentic/config.toml` 临时副本，不改活树配置；主档零回归判据（`test_project_config_primary_developer_stays_native`）的变异施于活树 `.agentic/config.toml`（B5 提交后的最终形态），变异后必须逐字节还原并 `git diff` 空输出核验。五项不变式 → 测试 → 真实输入面变异 → 预期转红 witness 的完整映射见本节末「不变式承重映射表」。

注意：第 1 项证明「前置可达」，第 2 项证明「失败归因」，**两者不能互相替代**——「无注入时能到终点」并不排除「带注入时死在别处」。

### 不变式承重映射表（codex rev1 #3：五项不变式 → 测试 → 真实输入面变异 → 预期转红 witness）

| # | 不变式 | 承重测试 | 真实输入面变异（源文件字节 / 进程边界 / 活树配置） | 预期转红 witness |
|---|--------|----------|------------------------------------------------------|------------------|
| INV-1 | 额度语义正确判定：语境命中为 True，歧义词无账户语境为 False（隐患 B） | `test_matches_chinese_quota_terms` / `test_matches_english_quota_terms` / `test_case_insensitive` / `test_ambiguous_phrases_are_not_quota_errors` | 删 `re.IGNORECASE`；放宽语境正则为裸词 `insufficient`；删某**承重**正向 pattern（如 `额度`；**rev6 勘误 #4**：`\bquota\b` 冗余，删之仍绿） | 大小写用例红；歧义负例红（`insufficient permissions` 误判）；`test_matches_chinese_quota_terms` 红 |
| INV-2 | fail-safe 三承重点：畸形 TOML 回落默认（`load_quota_patterns` 的 `except Exception`）；空列表/错误类型回落默认（`load_quota_patterns` 的 isinstance/非空守卫）；语法非法正则跳过不抛（`is_quota_error` 的 `except re.error`，非 `load_quota_patterns`——后者不编译正则） | `test_load_patterns_fails_safe_on_malformed_toml` / `test_load_patterns_fails_safe_on_bad_override` / `test_load_patterns_reads_override` / `test_bad_regex_pattern_is_skipped_not_raised` | (a1) 删 `load_quota_patterns` 的 `except Exception`；(a2) 删 `load_quota_patterns` 的 isinstance/非空守卫；(b) 删 `is_quota_error` 的 `except re.error: continue` | (a1) 畸形 TOML 用例红（`TOMLDecodeError` 抛出而非回落）；(a2) 空列表/错误类型用例红（不回落默认）；(b) 坏正则用例红（`re.error` 抛出而非跳过，`patterns=["[", r"\bquota\b"]`） |
| INV-3 | fallback binding 解析零回归：缺失/非法/role 非 dict/**provider 配置形状非法（含 selectors 非 dict，rev7 §R1 F1 收窄；畸形 TOML 属范围外既有共享失败）** → None 不抛 | `test_resolves_flash_binding` / `test_none_when_no_fallback_provider` / `test_none_when_role_is_dict_without_fallback` / `test_none_when_provider_section_missing` / `test_none_when_provider_cfg_invalid_no_raise` / `test_none_when_selectors_is_string_no_raise` / `test_none_when_selectors_is_list_no_raise`（rev7 §R1） | 删/收窄 `resolve_role_fallback_binding` 拓宽后的 `except Exception`（rev7 §R1 F1 收窄仅包 build_binding，原 `except ProviderConfigError` 漏 selectors 非 dict 的 `AttributeError`）；删 role 非 dict 守卫 | invalid 用例红（抛异常）；selectors 形状负例红（`AttributeError` 逸出）；对应负向红 |
| INV-4 | 主档零回归：`developer` 主 binding 仍 `("kimi", None)`，评级语义不变（隐患 A） | `test_project_config_primary_developer_stays_native` | 给活树 `.agentic/config.toml` 的 `developer` 加 `provider` 键（变异后逐字节还原 + `git diff` 空核验） | `assert binding is None` 红 |
| INV-5 | 派发编排：单跳回退（成功/非额度/未配/dry_run 不回退；额度失败恰好重派一次；flash 也失败即 STOP，隐患 C）+ 计数/circuit-breaker 接线（回退成功只 +1，circuit-breaker 先于派发，隐患 D） | `test_success_no_fallback`（等价 witness，rev6 勘误 #5）/ `test_success_with_quota_like_output_no_fallback`（rev6 §R3）/ `test_non_quota_failure_no_fallback` / `test_quota_failure_retries_with_flash_success` / `test_quota_failure_no_fallback_configured` / `test_single_hop_flash_also_quota_fails` / `test_dry_run_does_not_fallback_even_on_quota_output` / `test_wiring_fallback_success_increments_count_by_one` / `test_wiring_circuit_breaker_precedes_dispatch` | 删 `if dry_run or result.dispatched: return` 短路；改单跳为循环；`count+1`→`count+2`（M1）；wrapper 调用移到 circuit-breaker 前（M2） | dry_run 腿 + success 腿（`test_success_with_quota_like_output_no_fallback`，rev6 §R3）红；`test_success_no_fallback` 等价 witness 仍绿（rev6 勘误 #5）；single_hop 红（`fb.calls>1`）；INV-W1 红（count=2）；INV-W2 红（calls 非零） |

> 说明：INV-5 把 codex 隐患 C（单跳到底）与隐患 D（计数不双计 + circuit-breaker 先于回退）合并为「派发编排」一项，因其变异面同在 `redispatch.py` 的 wrapper + `main()` 接线。五项不变式（INV-1..INV-5）即 DESIGN §8 测试计划要求的全集；oracle 四证据（§1-§4）经此表覆盖每一项，漏报与过宽误报两个变异方向均在 INV-1 列出。

## Allowed and forbidden paths

本段与上文「范围」一节中的 allowed_paths / forbidden_paths 完全同义，非另一份口径：只能改 allowed_paths 白名单内的 7 个路径（3 源 + 3 测试 + 1 config），绝不能碰 forbidden_paths 黑名单（`independence.py` / `gate/` / `adapters/kimi.py` / `uv.lock` / 章程与契约文件 / `templates/` / 锁与凭据路径）；owner 边界对齐 CODEOWNERS，不跨 owner 写入。

范围守卫命令（B6 Step 2，codex rev1 #4 + rev2 #4 fail-closed：dispatch_commit 基线 + 集合差，`set -euo pipefail` + 非空即 `exit 1`，不用 main...HEAD）：

```
set -euo pipefail
WT=/Users/admin/vibe/.worktrees/kqff-wp01
STATUS=docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json
BASE=$(python3 -c "import json; print(json.load(open('$WT/$STATUS'))['git']['dispatch_commit'])")
test -n "$BASE" || { echo "SCOPE_GUARD_FAIL: dispatch_commit 为空"; exit 1; }
git -C "$WT" cat-file -e "${BASE}^{commit}" || { echo "SCOPE_GUARD_FAIL: 基线非有效 commit"; exit 1; }
git -C "$WT" diff --name-only "${BASE}...HEAD" | sort -u > /tmp/kqff-wp01-changed.txt
# /tmp/kqff-wp01-allowed.txt = 7 项 allowed_paths（排序去重）
comm -23 /tmp/kqff-wp01-changed.txt /tmp/kqff-wp01-allowed.txt > /tmp/kqff-wp01-unexpected.txt
if [ -s /tmp/kqff-wp01-unexpected.txt ]; then echo "SCOPE_GUARD_FAIL: 越界文件："; cat /tmp/kqff-wp01-unexpected.txt; exit 1; fi
git -C "$WT" diff "${BASE}...HEAD" -- \
  src/agentic_loop/independence.py src/agentic_loop/gate/ \
  src/agentic_loop/adapters/kimi.py uv.lock \
  docs/agentic/OPERATING_MODEL.md AGENTS.md CLAUDE.md > /tmp/kqff-wp01-forbidden.diff
if [ -s /tmp/kqff-wp01-forbidden.diff ]; then echo "SCOPE_GUARD_FAIL: forbidden 被改："; cat /tmp/kqff-wp01-forbidden.diff; exit 1; fi
echo "SCOPE_GUARD_PASS"
```

基线是派发时冻结的 `git.dispatch_commit`（集成分支 tip），**不是** `main...HEAD`——后者含 A 阶段 DESIGN/HANDOFF/freeze 治理提交，不会"只列 7 个允许文件"。判据（codex rev2 #4 fail-closed）：changed ⊆ allowed（unexpected 文件空）+ 显式 forbidden diff 空（#38 边界与信任根评级未触）；`set -euo pipefail` + 基线非空/`git cat-file -e` 断言 + `comm`/forbidden 结果非空即 `exit 1`，全绿打印 `SCOPE_GUARD_PASS`（机器可判，不靠人眼读输出）。

## Completion definition

本段与上文「完成定义（DoD）」一节同义，非另一份口径：交付物逐项就绪（7 个文件）、验收测试全绿（focused 3 测试文件 + 全量 pytest 仅 4 预存失败）、范围守卫空输出（forbidden_paths 零改动）、`agentic quality-gate` 全绿、无生产写入/网络/通知/推送，commit message 符合规范（B1-B5 各一次 feat 提交，显式路径；status 的工作树累积不单独提交）。
