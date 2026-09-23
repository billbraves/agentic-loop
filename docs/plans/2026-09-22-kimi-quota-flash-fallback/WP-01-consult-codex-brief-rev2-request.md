# WP-01 kimi 额度回退 deepseek-flash — brief 第二签名咨询请求 rev2（codex，read-only）

> 请求者 claude-code（编排者，session=kqff-a3）｜2026-09-22｜咨询者 codex（consultant, gpt-5.6-sol via kirogpt，read-only sandbox，reasoning_effort=medium）
> 用途：WP-01（kimi 套餐额度不足时自动单跳回退 `deepseek-v4-flash`，配置驱动、零回归）brief **rev2** 冻结（DRAFT→APPROVED）前的独立第二签名复核。
> **这是 rev2**：rev1 你判 REWORK，给出 4 项有界阻断（CODEX_FINDINGS #1-#4）。编排者已在现有 7 个 allowed_paths 内完成有界修订，未改 architecture/adapter/gate/independence。本请求逐项回应你的 4 findings，请你复核每项是否闭环。
> 编排者**未预判**结论；请独立裁决，不要因为已修订就默认 ACCEPT。若仍有 brief 级阻断项，请 REWORK 并给具体有界 finding。

## rev1 你的 4 项 finding 与 rev2 修订对照

### Finding #1（隐患 B，rev1 判"不充分"）：默认额度过宽，歧义词误判
- **你的原话**：默认模式含无上下文的 `insufficient`/`balance`/`credit`/`exceeded`/`billing` 及较宽的 `rate.?limit`；`test count exceeded`/`insufficient permissions`/`billing module failed` 会被误判为额度错误；现有负例完全没有携带歧义词的非额度失败。要求：收窄默认 regex 为额度/账户/API 限制语境；加入歧义边界不变式 + `is_quota_error(...) is False` 断言 + wrapper fallback_factory 未调用。
- **rev2 修订**：
  - DESIGN §4.1 与 IMPLEMENTATION-PLAN B1 Step 3 的 `DEFAULT_QUOTA_PATTERNS` 已收窄为语境化正则：ambiguous 词（insufficient/exceeded/exhausted/depleted/out of/...）必须与账户名词（balance/credit/funds/quota/allowance/budget/subscription）近距共现（`\W{0,10}` / `\W{0,20}`）；`429`/`402` 必须与额度/付费语境共现（避免命中端口号/行数）；仅保留中文语义明确词（额度/配额/套餐/余额不足）与英文 `\bquota\b` 的裸匹配。删除了 rev1 的裸词 `insufficient`/`balance`/`credit`/`exceeded`/`billing`/`用量`/`余额`。
  - IMPLEMENTATION-PLAN B1 Step 1 新增 `test_ambiguous_phrases_are_not_quota_errors`，断言你点名的 `test count exceeded`/`insufficient permissions`/`billing module failed`/`credit card processor returned error` 以及 `port 429 is not available`/`balance sheet report generated`/`out of memory`/`AssertionError: rate_limit should be 5` 均判 False。
  - brief rev2「交付物清单」「附注.已知陷阱」「Acceptance tests §3」与映射表 INV-1 已加入歧义边界不变式 + "过宽误报方向"变异（放宽回裸词 → 歧义负例转红）。
- **请复核**：收窄后的语境化正则是否仍有过宽风险？歧义负例清单是否覆盖你点名的全部误判样例？INV-1 的"过宽误报"变异方向是否足以承重？

### Finding #2（隐患 D，rev1 判"不充分"）：计数/circuit-breaker 无承重测试
- **你的原话**：文字不变式正确但无承重测试；DESIGN 测试计划要求"回退成功只 +1"和"circuit-breaker 仍先于回退"，但 B4/B5 没有对应测试；允许改整个 redispatch.py 时仅靠注释 + post-review 不足。要求：B5 和 brief 增加 main() 接线级测试（初始 count=N，primary 额度失败 fallback 成功后为 N+1 不是 N+2；count>=REDISPATCH_MAX 时 primary 与 fallback 都不调用、不构造；对应 mutation 额外计数或把 fallback 派发移到 circuit-breaker 前必须转红）。
- **rev2 修订**：
  - IMPLEMENTATION-PLAN B5 Step 3 新增 2 条 main() 接线级测试：`test_wiring_fallback_success_increments_count_by_one`（INV-W1：primary 额度失败→flash 成功，最终 redispatch_count 恰为 1）与 `test_wiring_circuit_breaker_precedes_dispatch`（INV-W2：count>=REDISPATCH_MAX 时 primary/wrapper/flash-factory 调用计数全为 0）。用 monkeypatch 把 main_repo/iterations_dir/_run_validator/_read_field/_build_prompt/_git_output/resolve_wrapper/subprocess.run/_resolve_developer/get_roles/resolve_role_fallback_binding/load_quota_patterns 全部导向 tmp_path/stub，离线承重。
  - 每条绑定必须转红的 source mutation：M1（`new_count = count + 1` → `count + 2`）转红 INV-W1；M2（把 `_dispatch_with_quota_fallback` 调用移到 circuit-breaker 前）转红 INV-W2。
  - brief rev2 映射表 INV-5 + Acceptance tests §3「main() 接线」条目 + C1 mutation-probe 已固化。
- **请复核**：这 2 条接线级测试的 mock 边界是否足以真实承重 M1/M2（而非被 mock 架空）？INV-W2 用 spy 计数断言 primary/wrapper/flash 全 0，是否能捕获"fallback 派发移到 circuit-breaker 前"？

### Finding #3（oracle，rev1 判"不充分"）：无效变异 + 缺五项不变式映射
- **你的原话**：oracle 框架严谨，但（a）没有覆盖"计数只 +1/circuit-breaker 不绕过"；（b）"删除 `if not output: return False` 后空串用例必须转红"不成立——即使删除该守卫，所有现有正则在空串上仍不匹配，函数仍返回 False；（c）"判定恒 False"只验证漏报，不验证过宽模式导致的误报。要求：删除无效空串变异，改为确实改变空输出结果的源码变异；增加五项不变式到"测试/真实输入面变异/预期转红 witness"的明确映射；为正向命中增加"过宽判定"变异。
- **rev2 修订**：
  - brief rev2 Acceptance tests §3 已删除"删空串 guard 必转红"的无效变异，并显式声明该 guard 是纯短路优化、行为等价、**不构成承重变异**（呼应 §4"某步骤不可攻击须在报告里写明理由"）；空串判 False 的承重改由"过宽 pattern（如误加 `r".*"`）使 `is_quota_error("")` 转 True"方向覆盖。
  - §3 变异现覆盖漏报（恒 False/删正向 pattern/删 IGNORECASE）与**过宽误报**（放宽回裸词→歧义负例转红）两个方向。
  - 新增「不变式承重映射表」：INV-1（额度语义，含过宽误报）/INV-2（config fail-safe）/INV-3（fallback binding 零回归）/INV-4（主档零回归）/INV-5（派发编排：单跳+计数+circuit-breaker），每项列出承重测试、真实输入面变异、预期转红 witness。
- **请复核**：删除无效空串变异 + 改为过宽 pattern 方向是否正确？五项不变式映射表是否覆盖 DESIGN §8 全集、每项变异是否施于真实输入面（源文件字节/活树配置/进程边界）？

### Finding #4（范围，rev1 判"部分"）：范围守卫基线错误 + 文案 6/7
- **你的原话**：范围守卫命令用 `main...HEAD` 不正确——feature branch 从已含 DESIGN/HANDOFF/freeze 文档的 plan integration branch 切出，结果不会"只列 7 个允许文件"；应以派发时冻结的 integration tip/`git.dispatch_commit` 为基线，机器校验全部 changed paths 是 allowed_paths 的子集，而不只检查四个显式 forbidden 路径；另有文案错误 B6 写"6 个允许文件"实际列了 7 个。
- **rev2 修订**：
  - IMPLEMENTATION-PLAN B6 Step 2 与 brief rev2 DoD/「Allowed and forbidden paths」的范围守卫已改为：以 `status.git.dispatch_commit` 为基线，`git diff --name-only <dispatch_commit>...HEAD` 的 changed-path 集合与 7 项 allowed_paths 做**完整集合差**（`comm -23`，必须空，即 changed ⊆ allowed），不再用 `main...HEAD`；显式 forbidden 路径检查降为双保险。
  - "6 个允许文件"已全部订正为 7（B6 Step 2 Expected、C1 改动面核对、brief Completion definition）。
- **请复核**：dispatch_commit 基线 + 集合差判据是否正确封堵越界？是否还有 main...HEAD 残留？

## 你已确认充分、rev2 未改动的项（请确认仍成立）
- **主档零回归（隐患 A，rev1 判"充分"）**：rev2 未改 resolve_role_binding 逻辑与 B5 `test_project_config_primary_developer_stays_native`；你对 gate 的纠正（N/A 与 ACCEPT 都解析 developer binding，但 binding=None 时不生成 identity，评级语义不变）已并入 DESIGN §6 评级段。
- **单跳到底（隐患 C，rev1 判"充分"）**：rev2 未改 B4 wrapper 单跳控制流。
- **密钥安全（隐患 E，rev1 判"充分"）**：rev2 在 DESIGN §6 补了密钥消费面口径（is_quota_error/日志只消费已脱敏的 ImplementResult.output；load_quota_patterns 吞解析异常不记录配置内容；ProviderConfigError 不含 key）。

## 裁决范围与 off-ramp
- 请只裁决 **rev2 是否可冻结**（4 findings 是否闭环 + 未改项是否仍成立）。
- **反芝诺 off-ramp（呼应章程 §6）**：若你认为 4 findings 已在 7 个 allowed_paths 内有界闭环，剩余问题属可由执行者在实现期解决、并由 post-implementation 双签门（`agentic gate`）复核的实现细节，请据此 ACCEPT 并在 RATIONALE 注明，避免 brief 无限细化。brief 级阻断项仅指：不变式本身错误/空洞、负面约束漏掉某条可伪造/可漂移路径、oracle 四证据不足以证承重、或范围留下跨 plan/跨 owner 缺口。

## 请实际读取核验（kqff worktree read-only）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md`（**rev2 裁决对象**，顶部有 rev2 修订摘要）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md`（§4.1 收窄 patterns、§6 密钥消费面/评级）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md`（B1 Step 1/3、B5 Step 3 wiring、B6 Step 2 范围守卫、Self-Review）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json`（evidence.brief.rev=2 + sha256）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-consult-codex-rev1-answer.md`（你的 rev1 裁决原文，对照闭环）
- `src/agentic_loop/redispatch.py`（main() 现状：circuit-breaker 393-411、dispatch 496、计数 515-525）
- `src/agentic_loop/resolve_paths.py`（resolve_role_binding 现状）
- `src/agentic_loop/provider_binding.py`（ProviderBinding 字段：provider/anthropic_base_url/openai_base_url/identity_model/cli_selector/api_key_env）

## 输出格式
- `CODEX_DECISION: ACCEPT|REWORK|CONSULT`
- 对 4 findings 各给「闭环/未闭环/部分」＋简短证据（引文件路径:行号或 brief 章节）
- `CODEX_RATIONALE:` 裁定理由（1-3 段）
- 若 REWORK，`CODEX_FINDINGS:` 给具体、有界的阻断项（哪一节、改成什么），而非泛论
